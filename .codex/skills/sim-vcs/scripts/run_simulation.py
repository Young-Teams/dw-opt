#!/usr/bin/env python3
"""Compile and simulate existing Verilog/SystemVerilog testbenches with VCS."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
from hdl_filelist import check_duplicates, merge_defines, read_filelists

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = "ignis-cr-cn-beijing.cr.volces.com/ignis/synopsys-eda:2018.09"
ERROR_PATTERN = re.compile(
    r"^\s*(?:Error(?:-\[|:)|Fatal(?:-\[|:)|UVM_(?:ERROR|FATAL)\s+@|TEST_FAIL\b|TEST_FAILED\b)",
    re.MULTILINE,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256(path)}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve(value: str, workspace: Path) -> Path:
    path = Path(value).expanduser()
    return (workspace / path).resolve() if not path.is_absolute() else path.resolve()


def docker_prefix(image: str, name: str, cwd: Path, run: Path, parents: set[Path]) -> list[str]:
    license_server = os.environ.get("SNPSLMD_LICENSE_FILE") or os.environ.get(
        "LM_LICENSE_FILE", "27000@192.168.3.150"
    )
    command = ["docker", "run", "--rm", "--name", name, "--network", "host"]
    host = os.environ.get("SIM_VCS_LICENSE_HOST", "iv-yeu4tcs9ogbw80enl3vc:192.168.3.150")
    if host:
        command += ["--add-host", host]
    command += ["-e", f"LM_LICENSE_FILE={license_server}", "-e", f"SNPSLMD_LICENSE_FILE={license_server}"]
    mounted: list[Path] = []
    for parent in sorted(parents, key=lambda p: (len(p.parts), str(p))):
        if parent.is_relative_to(run) or any(parent.is_relative_to(p) for p in mounted):
            continue
        command += ["--volume", f"{parent}:{parent}:ro"]
        mounted.append(parent)
    command += ["--volume", f"{run}:{run}:rw", "--workdir", str(cwd), image]
    return command


def run_stage(command: list[str], cwd: Path, log: Path, timeout: float, container: str | None) -> dict:
    """Wait for the entire stage; stop owned processes before permitting cleanup."""
    result = {"started_at": now(), "exit_code": None, "timed_out": False, "interrupted": False,
              "error": None, "safe_to_clean": True}
    with log.open("w", encoding="utf-8") as stream:
        try:
            process = subprocess.Popen(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        except OSError as exc:
            result["error"] = str(exc)
        else:
            try:
                result["exit_code"] = process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
                result["timed_out"] = isinstance(exc, subprocess.TimeoutExpired)
                result["interrupted"] = isinstance(exc, KeyboardInterrupt)
                if container:
                    try:
                        stopped = subprocess.run(["docker", "rm", "-f", container],
                                                 capture_output=True, text=True, timeout=20)
                        result["safe_to_clean"] = stopped.returncode == 0 or "No such container" in stopped.stderr
                    except (OSError, subprocess.TimeoutExpired):
                        result["safe_to_clean"] = False
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                result["exit_code"] = process.wait()
                stream.write("\nSIM_VCS: stage interrupted or wall-clock timeout reached.\n")
    result["finished_at"] = now()
    text = log.read_text(encoding="utf-8", errors="replace")
    result["log_errors"] = [line for line in text.splitlines() if ERROR_PATTERN.match(line)]
    result["success"] = result["exit_code"] == 0 and not any(
        result[key] for key in ["timed_out", "interrupted", "error", "log_errors"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Base directory for relative input paths")
    parser.add_argument("--design", required=True, help="Output category: experiments/<design>/sim/")
    parser.add_argument("--top", required=True, help="Testbench top module, not the DUT module")
    parser.add_argument("--tb", nargs="+", default=[], help="TB files after filelist sources; omit if already listed")
    parser.add_argument("--rtl", nargs="+", default=[], help="RTL/model/package files, compiled before TB files")
    parser.add_argument("--filelist", "-f", action="append", default=[], help="HDL filelist, optionally including TB; repeatable")
    parser.add_argument("--filelist-base", choices=["workspace", "filelist"], default="workspace",
                        help="Base for paths in top-level filelists; defaults to workspace")
    parser.add_argument("--include-dir", action="append", default=[], help="Repeat for each include directory")
    parser.add_argument("--define", action="append", default=[], help="Repeat for each NAME or NAME=VALUE macro")
    parser.add_argument("--plusarg", action="append", default=[], help="Runtime NAME or NAME=VALUE, optional leading +")
    parser.add_argument("--data", nargs="+", default=[], help="Input data copied into outputs/ by basename")
    parser.add_argument("--timescale", default="1ns/1ps", help="Default for modules without a timescale directive")
    parser.add_argument("--wave-format", choices=["both", "fsdb", "vcd"], default="both")
    parser.add_argument("--pass-pattern", help="Optional regular expression required in the simulation log")
    parser.add_argument("--compile-timeout", type=float, default=300.0, help="Compilation wall-clock limit in seconds")
    parser.add_argument("--sim-timeout", type=float, default=300.0, help="Simulation wall-clock limit in seconds")
    parser.add_argument("--clean-intermediates", action="store_true", help="Delete this Run's work/ and runtime ucli.key after completion")
    parser.add_argument("--output-root", help="Defaults to workspace/experiments")
    parser.add_argument("--vcs", help="Explicit local VCS executable")
    parser.add_argument("--backend", choices=["auto", "native", "docker"], default="auto",
                        help="auto skips the host eda-tool wrapper and uses the managed Docker flow")
    parser.add_argument("--docker-image", default=os.environ.get("SIM_VCS_DOCKER_IMAGE", DEFAULT_IMAGE),
                        help="Fallback image when local VCS is unavailable")
    args = parser.parse_args()
    for timeout in [args.compile_timeout, args.sim_timeout]:
        if not math.isfinite(timeout) or timeout <= 0:
            parser.error("timeouts must be finite and greater than zero")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", args.top):
        parser.error("--top must be a simple Verilog module identifier")
    if not re.fullmatch(r"(?:1|10|100)(?:s|ms|us|ns|ps|fs)/(?:1|10|100)(?:s|ms|us|ns|ps|fs)", args.timescale):
        parser.error("invalid --timescale; example: 1ns/1ps")
    try:
        pass_pattern = re.compile(args.pass_pattern, re.MULTILINE) if args.pass_pattern else None
    except re.error as exc:
        parser.error(f"invalid --pass-pattern: {exc}")
    design = re.sub(r"[^A-Za-z0-9._-]+", "-", args.design.strip()).strip("-._")
    if not design:
        parser.error("--design must contain a letter or digit")
    workspace = Path(args.workspace).expanduser().resolve()
    rtl, tb, data = ([resolve(v, workspace) for v in values] for values in [args.rtl, args.tb, args.data])
    filelists = [resolve(v, workspace) for v in args.filelist]
    try:
        expanded = read_filelists(filelists, workspace, args.filelist_base)
        sources = rtl + expanded["sources"] + tb
        check_duplicates(sources)
        defines = merge_defines(expanded["defines"] + args.define)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if not sources:
        parser.error("provide --tb/--rtl or --filelist with source files containing the TB top")
    include_dirs = list(dict.fromkeys(expanded["include_dirs"] + [resolve(v, workspace) for v in args.include_dir]))
    if not workspace.is_dir():
        parser.error(f"workspace does not exist: {workspace}")
    for path in [*sources, *data]:
        if not path.is_file():
            parser.error(f"input file does not exist: {path}")
    for path in include_dirs:
        if not path.is_dir():
            parser.error(f"include directory does not exist: {path}")
    if len({p.name for p in data}) != len(data):
        parser.error("--data files must have distinct basenames")
    if any(p.name == "ucli.key" for p in data):
        parser.error("ucli.key is reserved for the simulator")
    output_root = resolve(args.output_root, workspace) if args.output_root else workspace / "experiments"
    if output_root.is_relative_to(SKILL_DIR):
        parser.error("experiment outputs must be outside the Skill directory")

    if args.backend == "docker" and args.vcs:
        parser.error("--backend docker cannot be combined with --vcs")
    vcs = shutil.which(args.vcs or "vcs") if args.backend != "docker" else None
    if args.vcs and not vcs:
        parser.error(f"local VCS is unavailable: {args.vcs}")
    # A wrapper compiles inside a container; simv and Verdi PLI must run there too.
    if vcs and Path(vcs).resolve() == Path("/usr/local/bin/eda-tool"):
        if args.backend == "native" or args.vcs:
            parser.error("vcs is the EDA container wrapper; use --backend docker without --vcs")
        vcs = None
    if args.backend == "native" and not vcs:
        parser.error("--backend native requires a native VCS executable")
    image_id = None
    tool_env = os.environ.copy()
    if not vcs:
        if not shutil.which("docker"):
            parser.error("neither vcs nor docker is available")
        inspection = subprocess.run(["docker", "image", "inspect", args.docker_image], capture_output=True, text=True)
        if inspection.returncode:
            parser.error(f"Docker image is not available locally: {args.docker_image}")
        info = json.loads(inspection.stdout)[0]
        image_id = info["Id"]
        tool_env = dict(entry.split("=", 1) for entry in info["Config"].get("Env", []) if "=" in entry)
    pli: list[str] = []
    formats = ["fsdb", "vcd"] if args.wave_format == "both" else [args.wave_format]
    if "fsdb" in formats:
        home = tool_env.get("VERDI_HOME")
        tab = tool_env.get("VERDI_PLI_TAB") or (f"{home}/share/PLI/VCS/LINUX64/novas.tab" if home else None)
        lib = tool_env.get("VERDI_PLI_LIB") or (f"{home}/share/PLI/VCS/LINUX64/pli.a" if home else None)
        if not home or not tab or not lib:
            parser.error("FSDB needs VERDI_HOME and Verdi PLI paths; configure these or use --wave-format vcd")
        pli = ["-P", tab, lib]

    inputs = {
        "top": args.top, "rtl": [record(p) for p in rtl], "tb": [record(p) for p in tb],
        "sources": [record(p) for p in sources], "filelists": expanded["filelists"],
        "filelist_parser_sha256": sha256(Path(__file__).with_name("hdl_filelist.py")),
        "data": [record(p) for p in data], "include_dirs": list(map(str, include_dirs)),
        "defines": defines, "plusargs": args.plusarg, "timescale": args.timescale,
        "wave_format": args.wave_format, "pass_pattern": args.pass_pattern,
        "compile_timeout": args.compile_timeout, "sim_timeout": args.sim_timeout,
        "runner_sha256": sha256(Path(__file__)), "execution": {
            "mode": "native" if vcs else "docker", "image_id": image_id, "vcs": vcs,
            "pli": pli,
        },
    }
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "__" + fingerprint[:8]
    run = output_root / design / "sim" / run_id
    run.mkdir(parents=True, exist_ok=False)
    work, logs, waves, outputs = (run / name for name in ["work", "logs", "waves", "outputs"])
    for directory in [work, logs, waves, outputs]:
        directory.mkdir()
    for path in data:
        shutil.copy2(path, outputs / path.name)
    wave_paths = {fmt: waves / f"{args.top}.{fmt}" for fmt in formats}
    binary = work / "simv"
    compile_args = [vcs or "vcs", "-full64", "-sverilog", f"-timescale={args.timescale}",
                    "-debug_access+all", "-top", args.top, f"-Mdir={work / 'csrc'}",
                    "-o", str(binary), *pli]
    if "fsdb" in formats:
        compile_args += ["+vcs+fsdbon"]
    if "vcd" in formats:
        compile_args += [f"+vcs+dumpvars+{wave_paths['vcd']}"]
    compile_args += [f"+incdir+{path}" for path in include_dirs]
    compile_args += [f"+define+{value}" for value in defines]
    compile_args += list(map(str, sources))
    sim_args = [str(binary)]
    if "fsdb" in formats:
        sim_args += [f"+fsdbfile+{wave_paths['fsdb']}"]
    sim_args += [value if value.startswith("+") else "+" + value for value in args.plusarg]
    compile_name = None if vcs else "sim-vcs-" + run_id.lower().replace(".", "-").replace("_", "-") + "-build"
    sim_name = None if vcs else compile_name.removesuffix("-build") + "-run"
    parents = {workspace, *(p.parent for p in sources + data), *include_dirs}
    compile_command = compile_args if vcs else docker_prefix(image_id, compile_name, work, run, parents) + compile_args
    sim_command = sim_args if vcs else docker_prefix(image_id, sim_name, outputs, run, parents) + sim_args
    manifest = {"schema_version": 1, "backend": "vcs", "design": args.design, "run_id": run_id,
                "fingerprint": fingerprint, "created_at": now(), "inputs": inputs,
                "image": None if vcs else args.docker_image, "clean_intermediates": args.clean_intermediates,
                "commands": {"compile": compile_command, "simulation": sim_command},
                "working_directories": {"compile": str(work), "simulation": str(outputs)},
                "requested_wave": str(wave_paths[formats[0]]),
                "requested_waves": {fmt: str(path) for fmt, path in wave_paths.items()}, "tool_version": None}
    write_json(run / "manifest.json", manifest)
    status = {"state": "running", "stage": "compile", "started_at": now(),
              "compile": None, "simulation": None, "cleanup_requested": args.clean_intermediates,
              "cleanup_performed": False, "removed": []}
    write_json(run / "status.json", status)
    compile_log, sim_log = logs / "compile.log", logs / "simulation.log"
    sim_log.write_text("Simulation has not started.\n")
    status["compile"] = run_stage(compile_command, work, compile_log, args.compile_timeout, compile_name)
    errors = []
    if status["compile"]["success"] and binary.is_file() and os.access(binary, os.X_OK):
        status["stage"] = "simulation"
        write_json(run / "status.json", status)
        status["simulation"] = run_stage(sim_command, outputs, sim_log, args.sim_timeout, sim_name)
    else:
        errors.append("Compilation failed or did not produce an executable simv; see logs/compile.log")
        sim_log.write_text("Simulation skipped because compilation failed.\n")
    sim_text = sim_log.read_text(errors="replace")
    if status["simulation"] and not status["simulation"]["success"]:
        errors.append("Simulation failed, was interrupted, or timed out; see logs/simulation.log")
    pass_matched = bool(pass_pattern.search(sim_text)) if pass_pattern else None
    if pass_pattern and not pass_matched:
        errors.append("Required --pass-pattern was not found in the simulation log")
    # TB-owned dump statements may choose a different filename. Retain and report
    # those waves in outputs/ as well; never delete them during work/ cleanup.
    wave_files = [p for base in [waves, outputs] for p in sorted(base.rglob("*"))
                  if p.is_file() and p.suffix.lower() in {".fsdb", ".vcd", ".vpd"} and p.stat().st_size > 0]
    missing_formats = [fmt for fmt in formats if not any(p.suffix.lower() == "." + fmt for p in wave_files)]
    if status["simulation"] and missing_formats:
        errors.append("Simulation did not produce nonempty waveform format(s): " + ", ".join(missing_formats))
    status["waves"] = [{"path": str(p), "bytes": p.stat().st_size} for p in wave_files]
    status["pass_pattern_matched"] = pass_matched
    status["test_result"] = "failed" if errors else ("passed" if pass_pattern else "not_checked")
    status["errors"] = errors
    safe = all(stage is None or stage["safe_to_clean"] for stage in [status["compile"], status["simulation"]])
    if args.clean_intermediates and safe:
        try:
            shutil.rmtree(work)
            status["removed"].append("work/")
            key = outputs / "ucli.key"
            if key.exists() or key.is_symlink():
                key.unlink()
                status["removed"].append("outputs/ucli.key")
            status["cleanup_performed"] = True
        except OSError as exc:
            errors.append(f"Intermediate cleanup failed: {exc}")
    elif args.clean_intermediates:
        errors.append("Cleanup skipped because container termination could not be confirmed")
    status["intermediates_retained"] = work.exists()
    status["state"] = "failed" if errors else "success"
    status["stage"] = "finished"
    status["finished_at"] = now()
    version = re.search(r"(?:Compiler version|Version)\s+([A-Za-z0-9_.-]+)",
                        sim_text + "\n" + compile_log.read_text(errors="replace"))
    manifest["tool_version"] = version.group(1) if version else None
    write_json(run / "manifest.json", manifest)
    write_json(run / "status.json", status)
    print(json.dumps({"status": status["state"], "run_dir": str(run), "manifest": str(run / "manifest.json"),
                      "compile_log": str(compile_log), "simulation_log": str(sim_log),
                      "waves": status["waves"], "intermediates_retained": work.exists()}, indent=2, ensure_ascii=False))
    return 0 if status["state"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
