#!/usr/bin/env python3
"""Parse one syn-dc run into compact JSON and Markdown reports."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def read_text(path: Path) -> str:
    """Return an empty string when an optional DC report was not produced."""
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def find_float(text: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}\s*:\s*({NUMBER})", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def find_area_value(text: str, label: str) -> float | None:
    match = re.search(
        rf"^\s*{re.escape(label)}\s*:\s*({NUMBER}|undefined)",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match or match.group(1).lower() == "undefined":
        return None
    return float(match.group(1))


def parse_clocks(path: Path, time_scale_ns: float = 1.0) -> list[dict[str, Any]]:
    clocks: list[dict[str, Any]] = []
    lines = read_text(path).splitlines()
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        fields += [""] * (4 - len(fields))
        period = float(fields[1]) * time_scale_ns
        waveform = [
            float(value) * time_scale_ns
            for value in re.split(r"[,\s]+", fields[2].strip())
            if value
        ]
        clocks.append(
            {
                "name": fields[0],
                "period_ns": period,
                "frequency_mhz": 1000.0 / period if period else None,
                "waveform_ns": waveform,
                "sources": [value for value in fields[3].split(",") if value],
            }
        )
    return clocks


def last_float(block: str, label: str) -> float | None:
    values = re.findall(rf"{re.escape(label)}\s+({NUMBER})", block, re.IGNORECASE)
    return float(values[-1]) if values else None


def first_float(block: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}\s+({NUMBER})", block, re.IGNORECASE)
    return float(match.group(1)) if match else None


def parse_timing_paths(text: str, limit: int) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    blocks = re.split(r"(?=^\s*Startpoint:)", text, flags=re.MULTILINE)
    for block in blocks:
        startpoint = re.search(r"^\s*Startpoint:\s*(\S+)", block, re.MULTILINE)
        endpoint = re.search(r"^\s*Endpoint:\s*(\S+)", block, re.MULTILINE)
        if not startpoint or not endpoint:
            continue

        path_group = re.search(r"^\s*Path Group:\s*(.+?)\s*$", block, re.MULTILINE)
        path_type = re.search(r"^\s*Path Type:\s*(.+?)\s*$", block, re.MULTILINE)
        slack = re.search(rf"^\s*slack\s+\([^)]*\)\s+({NUMBER})", block, re.MULTILINE)

        paths.append(
            {
                "rank": len(paths) + 1,
                "startpoint": startpoint.group(1),
                "endpoint": endpoint.group(1),
                "path_group": path_group.group(1) if path_group else None,
                "path_type": path_type.group(1) if path_type else None,
                # DC later repeats arrival with a minus sign while calculating slack;
                # the first occurrence is the actual positive path arrival time.
                "data_arrival_time_ns": first_float(block, "data arrival time"),
                "data_required_time_ns": last_float(block, "data required time"),
                "slack_ns": float(slack.group(1)) if slack else None,
            }
        )
        if len(paths) >= limit:
            break
    return paths


def markdown_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value).replace("|", "\\|")


def render_summary(metrics: dict[str, Any]) -> str:
    run = metrics["run"]
    area = metrics["area"]
    timing = metrics["timing"]
    lines = [
        "# DC synthesis summary",
        "",
        f"- Status: {metrics['status']}",
        f"- Design: {run['design']}",
        f"- Run ID: {run['run_id']}",
        f"- Tool: {run.get('tool_version') or 'Design Compiler'}",
        f"- SDC: {metrics['constraints']['sdc']}",
        "",
        "## Effective clocks",
        "",
        "| Clock | Period (ns) | Frequency (MHz) | Waveform (ns) | Sources |",
        "|---|---:|---:|---|---|",
    ]
    for clock in metrics["constraints"]["clocks"]:
        lines.append(
            "| {name} | {period} | {frequency} | {waveform} | {sources} |".format(
                name=markdown_value(clock["name"]),
                period=markdown_value(clock["period_ns"]),
                frequency=markdown_value(clock["frequency_mhz"]),
                waveform=markdown_value(", ".join(map(str, clock["waveform_ns"]))),
                sources=markdown_value(", ".join(clock["sources"])),
            )
        )

    lines += [
        "",
        "## Area",
        "",
        f"- Cell area: {markdown_value(area['cell_area'])}",
        f"- Combinational area: {markdown_value(area['combinational_area'])}",
        f"- Noncombinational area: {markdown_value(area['noncombinational_area'])}",
        f"- Macro/black-box area: {markdown_value(area['macro_black_box_area'])}",
        "",
        "## Timing",
        "",
        f"- Critical path delay: {markdown_value(timing['critical_path_delay_ns'])} ns",
        f"- Critical path slack: {markdown_value(timing['critical_path_slack_ns'])} ns",
        f"- WNS: {markdown_value(timing['wns_ns'])} ns",
        f"- Requested paths: {timing['max_paths_requested']}",
        f"- Reported paths: {timing['paths_reported']}",
        "",
        "## Critical paths",
        "",
        "| Rank | Startpoint | Endpoint | Group | Arrival (ns) | Required (ns) | Slack (ns) |",
        "|---:|---|---|---|---:|---:|---:|",
    ]
    for path in timing["critical_paths"]:
        lines.append(
            "| {rank} | {start} | {end} | {group} | {arrival} | {required} | {slack} |".format(
                rank=path["rank"],
                start=markdown_value(path["startpoint"]),
                end=markdown_value(path["endpoint"]),
                group=markdown_value(path["path_group"]),
                arrival=markdown_value(path["data_arrival_time_ns"]),
                required=markdown_value(path["data_required_time_ns"]),
                slack=markdown_value(path["slack_ns"]),
            )
        )

    lines += [
        "",
        "Raw DC reports are stored in `reports/`; mapped outputs are stored in `mapped/`.",
        "",
    ]
    return "\n".join(lines)


def parse_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    status_path = run_dir / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    report_dir = run_dir / "reports"

    qor_text = read_text(report_dir / "qor.rpt")
    area_text = read_text(report_dir / "area.rpt")
    timing_text = read_text(report_dir / "timing.rpt")
    units_path = report_dir / "units.rpt"
    time_scale_ns = 1.0  # Legacy manifests without target_dbs used ns libraries.
    if units_path.exists():
        unit_match = re.search(rf"Time_unit\s*:\s*({NUMBER})\s+Second", read_text(units_path))
        if not unit_match or float(unit_match.group(1)) <= 0:
            raise ValueError(f"Missing or invalid DC time unit in {units_path}")
        time_scale_ns = float(unit_match.group(1)) * 1e9
    elif "target_dbs" in manifest:
        raise ValueError(f"Missing {units_path}; target-library time units cannot be assumed")
    max_paths = int(manifest["max_paths"])
    critical_paths = parse_timing_paths(timing_text, max_paths)
    for path in critical_paths:
        for key in ("data_arrival_time_ns", "data_required_time_ns", "slack_ns"):
            if path[key] is not None:
                path[key] *= time_scale_ns

    critical_slack = find_float(qor_text, "Critical Path Slack")
    if critical_slack is not None:
        critical_slack *= time_scale_ns
    critical_delay = find_float(qor_text, "Critical Path Length")
    if critical_delay is not None:
        critical_delay *= time_scale_ns
    wns = min(0.0, critical_slack) if critical_slack is not None else None
    metrics = {
        "schema_version": 1,
        "status": status.get("state", "unknown"),
        "run": {
            "run_id": manifest["run_id"],
            "design": manifest["design"],
            "backend": "dc",
            "tool_version": manifest.get("tool_version"),
            "fingerprint": manifest["fingerprint"],
        },
        "constraints": {
            "sdc": manifest["sdc"]["path"],
            "sdc_sha256": manifest["sdc"]["sha256"],
            "clocks": parse_clocks(report_dir / "clocks.tsv", time_scale_ns),
        },
        "area": {
            "cell_area": find_area_value(area_text, "Total cell area"),
            "combinational_area": find_area_value(area_text, "Combinational area"),
            "noncombinational_area": find_area_value(area_text, "Noncombinational area"),
            "macro_black_box_area": find_area_value(area_text, "Macro/Black Box area"),
        },
        "timing": {
            "critical_path_delay_ns": critical_delay,
            "critical_path_slack_ns": critical_slack,
            "wns_ns": wns,
            "max_paths_requested": max_paths,
            "paths_reported": len(critical_paths),
            "critical_paths": critical_paths,
        },
    }

    (run_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(render_summary(metrics), encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()
    metrics = parse_run(args.run_dir)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
