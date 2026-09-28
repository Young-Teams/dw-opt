#!/usr/bin/env python3
"""Run Design Compiler for existing RTL and preserve its raw results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Keep the bundled helper import from creating __pycache__ inside the Skill.
sys.dont_write_bytecode = True
from hdl_filelist import check_duplicates, merge_defines, read_filelists

SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = SKILL_DIR / "assets" / "templates"
ASAP7_DIR = SKILL_DIR / "assets" / "libs" / "asap7-rvt-tt-ccs"
DEFAULT_DBS = [
    ASAP7_DIR / f"asap7sc7p5t_{group}_RVT_TT_ccs_{date}.db"
    for group, date in [
        ("INVBUF", "211120"), ("SIMPLE", "211120"), ("AO", "211120"),
        ("OA", "211120"), ("SEQ", "220123"),
    ]
]
DEFAULT_IMAGE = "ignis-cr-cn-beijing.cr.volces.com/ignis/synopsys-eda:2018.09"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    if not normalized:
        raise ValueError("design names must contain a letter or digit")
    return normalized


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(value: str | Path, workspace: Path) -> Path:
    path = Path(value).expanduser()
    return (workspace / path).resolve() if not path.is_absolute() else path.resolve()


def tcl_braced(value: str | Path) -> str:
    text = str(value).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return "{" + text + "}"


def tcl_list(values: list[str] | list[Path]) -> str:
    """Keep source and library lists readable in the generated Tcl."""
    if not values:
        return "[list]"
    lines = " \\\n".join(f"    {tcl_braced(value)}" for value in values)
    return "[list \\\n" + lines + " \\\n]"


def render_template(path: Path, values: dict[str, str]) -> str:
    """Replace explicit markers once, without interpreting Tcl syntax."""
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise ValueError(f"unknown template marker {match.group(0)} in {path}")
        return values[name]

    return re.sub(r"@([A-Z_]+)@", replace, path.read_text(encoding="utf-8"))


def discover_target_dbs(workspace: Path, explicit: list[str] | None) -> list[Path]:
    if explicit:
        return [resolve_path(value, workspace) for value in explicit]
    env_value = os.environ.get("SYN_DC_TARGET_DB")
    if env_value:
        return [resolve_path(value, workspace) for value in env_value.split(os.pathsep)]
    return [path.resolve() for path in DEFAULT_DBS]


def dc_version(command: list[str], *, cwd: Path, env: dict[str, str]) -> str | None:
    result = subprocess.run(
        command + ["-version"], cwd=cwd, env=env, timeout=60,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    match = re.search(r"dc_shell version\s+-\s+([^\s]+)", result.stdout)
    return match.group(1) if match else None


def docker_command(
    image: str, *, workspace: Path, output_root: Path, run_dir: Path,
    input_files: list[Path], include_dirs: list[Path],
) -> list[str]:
    """Use the server's existing image with identical host/container paths."""
    license_server = os.environ.get("SNPSLMD_LICENSE_FILE") or os.environ.get(
        "LM_LICENSE_FILE", "27000@192.168.3.150"
    )
    command = ["docker", "run", "--rm", "--network", "host"]
    license_host = os.environ.get(
        "SYN_DC_LICENSE_HOST", "iv-yeu4tcs9ogbw80enl3vc:192.168.3.150"
    )
    if license_host:
        command += ["--add-host", license_host]
    for name, value in {
        "LM_LICENSE_FILE": license_server, "SNPSLMD_LICENSE_FILE": license_server,
    }.items():
        command += ["--env", f"{name}={value}"]
    # Mount input directories read-only; overlay the result root read-write.
    parents = {workspace, SKILL_DIR, *(path.parent for path in input_files), *include_dirs}
    mounted: list[Path] = []
    for parent in sorted(parents, key=lambda p: (len(p.parts), str(p))):
        if parent == output_root or parent.is_relative_to(output_root):
            continue
        if any(parent.is_relative_to(existing) for existing in mounted):
            continue
        command += ["--volume", f"{parent}:{parent}:ro"]
        mounted.append(parent)
    command += ["--volume", f"{output_root}:{output_root}:rw"]
    return command + ["--workdir", str(run_dir), image, "dc_shell"]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_common_setup(
    path: Path,
    *,
    template: Path,
    workspace: Path,
    design: str,
    top: str,
    rtl_files: list[Path],
    include_dirs: list[Path],
    defines: list[str],
    sdc: Path,
    target_dbs: list[Path],
    run_dir: Path,
    alib_dir: Path,
    max_paths: int,
) -> None:
    content = render_template(template, {
        "DESIGN_NAME": tcl_braced(design),
        "TOP_MODULE": tcl_braced(top),
        "WORKSPACE_DIR": tcl_braced(workspace),
        "RUN_DIR": tcl_braced(run_dir),
        "ALIB_DIR": tcl_braced(alib_dir),
        "RTL_FILES": tcl_list(rtl_files),
        "INCLUDE_DIRS": tcl_list(include_dirs),
        "HDL_DEFINES": tcl_list(defines),
        "SDC_FILE": tcl_braced(sdc),
        "TARGET_DBS": tcl_list(target_dbs),
        "MAX_PATHS": str(max_paths),
    })
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Project workspace containing experiments/")
    parser.add_argument("--design", required=True, help="Stable circuit/design name")
    parser.add_argument("--top", required=True, help="RTL top module passed to elaborate")
    parser.add_argument("--rtl", nargs="+", default=[], help="RTL files before filelist sources")
    parser.add_argument("--filelist", "-f", action="append", default=[], help="HDL filelist; repeat for multiple lists")
    parser.add_argument("--filelist-base", choices=["workspace", "filelist"], default="workspace",
                        help="Base for paths in top-level filelists; defaults to workspace")
    parser.add_argument("--include-dir", action="append", default=[], help="Repeat for each HDL include directory")
    parser.add_argument("--define", action="append", default=[], help="Repeat for each NAME or NAME=VALUE macro")
    parser.add_argument("--sdc", required=True, help="Project SDC with all clock/timing constraints in target-library units")
    parser.add_argument("--run-tcl", help="Project or bundled DC flow Tcl; defaults to the Skill's default template")
    parser.add_argument("--target-db", nargs="+", help="Target .db file(s); overrides SYN_DC_TARGET_DB and the default ASAP7 set")
    parser.add_argument("--output-root", help="Defaults to workspace/experiments")
    parser.add_argument("--max-paths", type=int, default=10, help="Number of worst max-delay paths")
    parser.add_argument("--dc-shell", help="Explicit local dc_shell executable or absolute path")
    parser.add_argument("--backend", choices=["auto", "native", "docker"], default="auto",
                        help="auto skips the host eda-tool wrapper and uses the managed Docker flow")
    parser.add_argument("--docker-image", default=os.environ.get("SYN_DC_DOCKER_IMAGE", DEFAULT_IMAGE),
                        help="Docker image used when no local dc_shell is available")
    args = parser.parse_args()

    if args.max_paths < 1:
        parser.error("--max-paths must be at least 1")

    workspace = Path(args.workspace).expanduser().resolve()
    filelists = [resolve_path(value, workspace) for value in args.filelist]
    try:
        expanded = read_filelists(filelists, workspace, args.filelist_base)
        rtl_files = [resolve_path(value, workspace) for value in args.rtl] + expanded["sources"]
        check_duplicates(rtl_files)
        defines = merge_defines(expanded["defines"] + args.define)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if not rtl_files:
        parser.error("provide --rtl or --filelist with at least one source file")
    include_dirs = list(dict.fromkeys(expanded["include_dirs"] + [resolve_path(v, workspace) for v in args.include_dir]))
    for path in include_dirs:
        if not path.is_dir():
            parser.error(f"include directory does not exist: {path}")
    target_dbs = discover_target_dbs(workspace, args.target_db)
    setup_source = TEMPLATE_DIR / ".synopsys_dc.setup"
    dc_setup_source = TEMPLATE_DIR / "dc_setup.tcl"
    report_helpers_source = TEMPLATE_DIR / "report_helpers.tcl"
    common_setup_template = TEMPLATE_DIR / "common_setup.tcl.tpl"
    run_tcl_source = (
        resolve_path(args.run_tcl, workspace)
        if args.run_tcl
        else TEMPLATE_DIR / "run_dc.tcl"
    )
    output_root = (
        resolve_path(args.output_root, workspace)
        if args.output_root
        else workspace / "experiments"
    )

    sdc = resolve_path(args.sdc, workspace)
    for path in [*rtl_files, *target_dbs, setup_source, dc_setup_source,
                 common_setup_template, run_tcl_source, report_helpers_source, sdc]:
        if not path.is_file():
            parser.error(f"required input file is missing: {path}")

    sdc_input = {
        "mode": "provided",
        "path": str(sdc),
        "sha256": sha256_file(sdc),
    }

    if args.backend == "docker" and args.dc_shell:
        parser.error("--backend docker cannot be combined with --dc-shell")
    dc_shell = shutil.which(args.dc_shell or "dc_shell") if args.backend != "docker" else None
    if args.dc_shell and not dc_shell:
        parser.error(f"dc_shell executable is not available: {args.dc_shell}")
    # The server's eda-tool launcher is a container transport, not a native install.
    # Keep inputs, outputs and image provenance under this runner's Docker flow.
    if dc_shell and Path(dc_shell).resolve() == Path("/usr/local/bin/eda-tool"):
        if args.backend == "native" or args.dc_shell:
            parser.error("dc_shell is the EDA container wrapper; use --backend docker without --dc-shell")
        dc_shell = None
    if args.backend == "native" and not dc_shell:
        parser.error("--backend native requires a native dc_shell executable")
    if not dc_shell and not shutil.which("docker"):
        parser.error("neither dc_shell nor docker is available")
    image_id = None
    if not dc_shell:
        inspection = subprocess.run(
            ["docker", "image", "inspect", args.docker_image, "--format", "{{.Id}}"],
            capture_output=True, text=True, check=False,
        )
        if inspection.returncode:
            parser.error(f"Docker image is not available locally: {args.docker_image}")
        image_id = inspection.stdout.strip()

    inputs = {
        "top": args.top,
        "rtl": [{"path": str(path), "sha256": sha256_file(path)} for path in rtl_files],
        "filelists": expanded["filelists"],
        "include_dirs": list(map(str, include_dirs)),
        "defines": defines,
        "filelist_parser_sha256": sha256_file(Path(__file__).with_name("hdl_filelist.py")),
        "sdc": sdc_input,
        "target_dbs": [{"path": str(db), "sha256": sha256_file(db)} for db in target_dbs],
        "run_tcl": {"path": str(run_tcl_source), "sha256": sha256_file(run_tcl_source)},
        "setup": {"path": str(setup_source), "sha256": sha256_file(setup_source)},
        "dc_setup": {"path": str(dc_setup_source), "sha256": sha256_file(dc_setup_source)},
        "report_helpers": {"path": str(report_helpers_source), "sha256": sha256_file(report_helpers_source)},
        "common_setup_template": {
            "path": str(common_setup_template), "sha256": sha256_file(common_setup_template),
        },
        "max_paths": args.max_paths,
        "execution": {"mode": "native" if dc_shell else "docker", "image_id": image_id},
    }
    library_dirs = {db.parent for db in target_dbs}
    if len(library_dirs) == 1:
        provenance = next(iter(library_dirs)) / "provenance.json"
        if provenance.is_file():
            inputs["library_provenance"] = {"path": str(provenance), "sha256": sha256_file(provenance)}
    fingerprint = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    run_id = f"{run_timestamp()}__{fingerprint[:8]}"
    run_dir = output_root / slug(args.design) / "dc" / run_id
    alib_dir = output_root / ".cache" / "dc" / "alib"

    config_dir = run_dir / "config"
    log_dir = run_dir / "logs"
    for directory in [config_dir, log_dir, run_dir / "reports", run_dir / "mapped", run_dir / "work"]:
        directory.mkdir(parents=True, exist_ok=False if directory == config_dir else True)

    shutil.copy2(setup_source, run_dir / ".synopsys_dc.setup")
    dc_setup = config_dir / "dc_setup.tcl"
    shutil.copy2(dc_setup_source, dc_setup)
    run_tcl = config_dir / "run_dc.tcl"
    shutil.copy2(run_tcl_source, run_tcl)
    report_helpers = config_dir / "report_helpers.tcl"
    shutil.copy2(report_helpers_source, report_helpers)
    common_setup = config_dir / "common_setup.tcl"
    write_common_setup(
        common_setup,
        template=common_setup_template,
        workspace=workspace,
        design=args.design,
        top=args.top,
        rtl_files=rtl_files,
        include_dirs=include_dirs,
        defines=defines,
        sdc=sdc,
        target_dbs=target_dbs,
        run_dir=run_dir,
        alib_dir=alib_dir,
        max_paths=args.max_paths,
    )

    environment = os.environ.copy()
    base_command = [dc_shell] if dc_shell else docker_command(
        image_id or args.docker_image, workspace=workspace, output_root=output_root,
        run_dir=run_dir,
        input_files=[*rtl_files, *target_dbs, sdc, run_tcl_source],
        include_dirs=include_dirs,
    )
    tool_version = dc_version(base_command, cwd=run_dir, env=environment)
    command = base_command + ["-f", str(run_tcl)]
    manifest_sdc = dict(sdc_input)
    manifest_sdc["source_path"] = str(sdc)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "fingerprint": fingerprint,
        "created_at": utc_now(),
        "design": args.design,
        "backend": "dc",
        "top": args.top,
        "tool_version": tool_version,
        "rtl": inputs["rtl"],
        "filelists": inputs["filelists"],
        "include_dirs": inputs["include_dirs"],
        "defines": inputs["defines"],
        "filelist_parser_sha256": inputs["filelist_parser_sha256"],
        "sdc": manifest_sdc,
        "target_db": inputs["target_dbs"][0],
        "target_dbs": inputs["target_dbs"],
        "execution": {"mode": "native" if dc_shell else "docker",
                      "image": None if dc_shell else args.docker_image, "image_id": image_id},
        "run_tcl": {
            "path": str(run_tcl),
            "source_path": str(run_tcl_source),
            "sha256": inputs["run_tcl"]["sha256"],
        },
        "setup": {**inputs["setup"], "run_path": str(run_dir / ".synopsys_dc.setup")},
        "dc_setup": {
            "path": str(dc_setup),
            "source_path": str(dc_setup_source),
            "sha256": inputs["dc_setup"]["sha256"],
        },
        "common_setup": {
            "path": str(common_setup),
            "sha256": sha256_file(common_setup),
            "template": str(common_setup_template),
            "template_sha256": inputs["common_setup_template"]["sha256"],
        },
        "report_helpers": {
            "path": str(report_helpers),
            "source_path": str(report_helpers_source),
            "sha256": inputs["report_helpers"]["sha256"],
        },
        "alib_cache": str(alib_dir),
        "max_paths": args.max_paths,
        "command": command,
    }
    if "library_provenance" in inputs:
        manifest["library_provenance"] = inputs["library_provenance"]
    write_json(run_dir / "manifest.json", manifest)

    status = {"state": "running", "started_at": utc_now(), "dc_exit_code": None}
    write_json(run_dir / "status.json", status)

    log_path = log_dir / "dc.log"
    with log_path.open("w", encoding="utf-8") as log_file:
        result = subprocess.run(
            command,
            cwd=run_dir,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    errors = re.findall(r"^Error:.*$", log_path.read_text(errors="replace"), re.MULTILINE)
    expected = [run_dir / "mapped" / name for name in
                [f"{args.top}_netlist.v", f"{args.top}.ddc", f"{args.top}.sdc"]]
    expected += [run_dir / "reports" / name for name in
                 ["qor.rpt", "area.rpt", "timing.rpt", "clocks.tsv", "units.rpt"]]
    missing = [str(path) for path in expected if not path.is_file() or not path.stat().st_size]
    succeeded = result.returncode == 0 and not errors and not missing
    status = {
        "state": "success" if succeeded else "failed",
        "started_at": status["started_at"],
        "finished_at": utc_now(),
        "dc_exit_code": result.returncode,
        "log": str(log_path),
        "errors": errors,
        "missing_outputs": missing,
    }
    write_json(run_dir / "status.json", status)

    output = {
        "status": status["state"],
        "run_dir": str(run_dir),
        "manifest": str(run_dir / "manifest.json"),
        "log": str(log_path),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if succeeded else (result.returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())
