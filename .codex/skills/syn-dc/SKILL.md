---
name: syn-dc
description: Use when RTL code needs Synopsys Design Compiler (DC) logic synthesis and timing analysis with generated reports.
---

# Synopsys Design Compiler synthesis

Synthesize existing Verilog/SystemVerilog without modifying RTL. Keep DC execution and report parsing separate.

## Execute

1. Select the target libraries and a project SDC in their native units, as described below. Use the project's Tcl when provided; otherwise select the bundled `default` flow/parser pair.
2. Invoke `scripts/run_synthesis.py` with `--workspace`, `--design`, `--top`, `--sdc`, and `--rtl` or `--filelist` (`-f`). Use `--target-db` to override the default library set. Resolve relative input paths against the workspace.
3. Read the returned `run_dir` and inspect `status.json`. A zero DC exit code alone is insufficient.
4. Run the paired parser only when normalized metrics, a summary, or report interpretation is requested. For synthesis alone, return the Run path and status.

| Pair | DC flow | Parser |
|---|---|---|
| `default` | `assets/templates/run_dc.tcl` | `scripts/parse_dc_reports.py` |

Keep bundled flows and their parsers paired in the Skill. Accept user-owned project flows through `--run-tcl`; preserve the runner's required outputs. Use the default parser only when the project's reports retain its expected formats; see [references/result-schema.md](references/result-schema.md).

## Library selection and constraints

`assets/libs/` and all companion files beneath it are local dependencies excluded
from Git. After cloning, supply the `.db` files at the paths below, or select
external files with `--target-db` / `SYN_DC_TARGET_DB`. The runner does not download
libraries. References to provenance and other files under `assets/libs/` describe
the locally prepared resources; those files are not included in a Git clone.

| Local set | Location under `assets/libs/` | Corner | Native units |
|---|---|---|---|
| ASAP7 (default), five release-28 RVT CCS files | `asap7-rvt-tt-ccs/` | TT, 0.7 V, 25 C | ps, fF |
| NanGate45, one NLDM file | `nangate45-typical-nldm/NangateOpenCellLibrary_typical.db` | typical/TypTyp, 1.1 V, 25 C | ns, fF |
| TCBN12 (T12), one CCS file | `tcbn12-tt-ccs/tcbn12ffcllbwp6t16p96cpdtt1v25c_ccs.db` | TT, 1.0 V, 25 C | ns, pF |

Select libraries through either entry mode:

- **Command line:** pass `--target-db db1 [db2 ...]` to `run_synthesis.py` or `run_synthesis.sh`, together with all required project arguments. Shell argument mode bypasses its entire configuration block; passing only `--target-db` is insufficient.
- **Shell configuration:** edit `TARGET_DBS=(...)` and `SDC_FILE` in `scripts/run_synthesis.sh`, then run it without arguments. A populated array is forwarded as `--target-db`.

The Shell configuration starts with empty project inputs. Before using it without
arguments, also configure `DESIGN`, `TOP`, and `FILELIST` or `RTL_FILES`.
The workspace is inferred from the script location; outputs default to
`<workspace>/experiments`, and an empty `RUN_TCL` uses the bundled flow.

Selection precedence is explicit `--target-db` (including the Shell array), then `SYN_DC_TARGET_DB` (colon-separated paths on this Linux host), then the five default ASAP7 files. An empty Shell array preserves this fallback. Relative DB paths resolve against `WORKSPACE` / `--workspace`.

When switching libraries, select or update the SDC at the same time. All time values must use the target library's native units: **500 ps in ASAP7 becomes 0.5 ns in NanGate or TCBN12**, including clocks, delays, uncertainties and transition constraints. Capacitance values also need conversion: **a 5 fF load is `set_load 5` in ASAP7/NanGate and `set_load 0.005` in TCBN12**. The runner does not convert SDC inputs; the parser converts reported time values to ns using `reports/units.rpt`.

Keep library files immutable and do not mix models, corners or releases in one target set. The locally prepared files are precompiled; synthesis reads `.db` directly. For source provenance and library-specific caveats, read [ASAP7](references/asap7.md), [NanGate45](assets/libs/nangate45-typical-nldm/README.md) or [TCBN12](references/tcbn12.md). Confirm the selected paths in `manifest.json` (`target_dbs`) and `reports/libraries.rpt`, and units in `reports/units.rpt`.

For nested filelists, include directories or macros, read [references/filelist.md](references/filelist.md). Direct `--include-dir` and `--define` options are repeatable. `--max-paths` defaults to `10`; `--output-root` defaults to `<workspace>/experiments`.

## Configuration and execution

Templates in `assets/templates/` have distinct roles:

- `.synopsys_dc.setup`: Run-local startup entry; sources `config/common_setup.tcl`, then `config/dc_setup.tcl` relative to itself.
- `common_setup.tcl.tpl`: renders project inputs, selected `TARGET_DBS`, and Run paths.
- `dc_setup.tcl`: applies `TARGET_DBS` to `target_library` and `link_library`, sets search paths, WORK design library and alib cache.
- `run_dc.tcl`: analysis, elaboration, constraints, compile, and raw outputs.
- `report_helpers.tcl`: effective-clock and runtime report procedures used by the default flow.

The runner copies/renders these files and records their hashes in `manifest.json`. Change invocation parameters, Shell configuration or source templates; preserve completed Run configurations. Library switching requires no edits to Python defaults or `dc_setup.tcl`.

`--backend auto` uses native `dc_shell` when available, otherwise a temporary EDA container. The host's `eda-tool` wrapper is routed to that Docker flow. For backend overrides, image/license settings or Library Compiler errors, read [references/environment.md](references/environment.md).

## Results

Runs live at `<output-root>/<design>/dc/<UTC-timestamp>__<fingerprint8>/`. Preserve completed Runs. Never write experiment results inside the Skill.

- `manifest.json`: inputs, configuration sources/hashes, tool/image identity, and command.
- `status.json`: state, logged errors, and missing required outputs.
- `config/`, `logs/dc.log`, `reports/`, `mapped/`, `work/`: configuration snapshots and raw DC outputs.
- `<output-root>/.cache/dc/alib/`: library-analysis cache shared across Runs.

When parsing is requested, run `python3 scripts/parse_dc_reports.py --run-dir <run>`. Read `summary.md` first, then `metrics.json`; inspect raw reports/logs for anomalies. Read [references/result-schema.md](references/result-schema.md) when comparing Runs or implementing consumers. Raw reports and exported SDC use native units; the parser normalizes time to ns.
