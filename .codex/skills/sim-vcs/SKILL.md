---
name: sim-vcs
description: Compile and simulate existing Verilog/SystemVerilog RTL and testbenches with Synopsys VCS, preserving logs and FSDB/VCD waveforms with optional intermediate cleanup.
---

# VCS simulation

Run existing RTL and testbenches without modifying their source files. Use VCS
for simulation; use syn-dc for logic synthesis. An RTL simulation does not need
a PDK `.db`; gate-level simulation needs the relevant Verilog cell models among
the source files.

## Workflow

1. Identify the TB top module and the ordered RTL/package/model and TB files.
2. Run `scripts/run_simulation.py` or `scripts/run_simulation.sh`.
3. Read `status.json`, then `logs/compile.log` and `logs/simulation.log`.
4. Return the Run and waveform paths. Keep intermediates unless cleanup was requested.

## Run

Replace the example project inputs and success marker with your own:

```bash
bash <skill-dir>/scripts/run_simulation.sh \
  --workspace /root/dw-opt \
  --design my_design \
  --top tb_top \
  --filelist sim_filelist.f \
  --wave-format both \
  --pass-pattern TEST_PASS
```

With no arguments, `run_simulation.sh` uses its editable configuration block.
Configure `DESIGN`, `TOP`, and `FILELIST` or `RTL_FILES`/`TB_FILES` first;
the workspace is inferred from the script location. Set `PASS_PATTERN` to the
TB's success marker and `CLEAN_INTERMEDIATES=true` to clean intermediates.
With arguments, it forwards the complete argument list to Python; its
configuration block is not applied. Use `--help` for all options.
A nonempty `FILELIST` bypasses the direct `RTL_FILES`/`TB_FILES` arrays.
Set it empty to use those arrays.

- `--top` is the **testbench** top, not the DUT top.
- `--rtl` files compile first, then filelist sources, then `--tb` files. Preserve package/dependency order.
- `--filelist FILE` (alias `-f`) is repeatable and can contain the whole source set, including the TB. Read [references/filelist.md](references/filelist.md) for nested lists, macros, include directories and path rules.
- Paths resolve against `--workspace`; the default output root is `workspace/experiments`.
- `--include-dir DIR`, `--define NAME=VALUE`, and `--plusarg NAME=VALUE` are repeatable.
- `--data FILE...` copies data files by basename into the simulation working directory, `outputs/`.
- `--timescale 1ns/1ps` supplies a default for modules without their own timescale; it does not override existing directives.
- `--compile-timeout` and `--sim-timeout` are wall-clock seconds (default 300 each), not HDL simulation time. The TB controls clocks and normal termination, normally with `$finish`.

## Waves and result interpretation

The default `--wave-format both` records FSDB and VCD in the same simulation,
without editing the TB. FSDB uses VCS's automatic dumping flag and the image's
Verdi PLI; VCD uses `+vcs+dumpvars+<path>`. Use `--wave-format fsdb` or `vcd` to
select only one. The runner requests `waves/<tb-top>.fsdb` and/or `.vcd`, and
requires every requested format to exist and be nonempty. A TB's own dump statements can select
another filename; wave files written below `outputs/` are also retained and
listed in `status.json`. Keep TB-generated final outputs in `outputs/` or `waves/`;
`work/` is disposable. Do not write results into source directories.

`status: success` means compilation and simulation exited successfully, no
recognized VCS/testbench failure lines were found, and a nonempty waveform was
produced in every requested format. It is not a functional proof. For a self-checking TB, provide
`--pass-pattern` for its success marker; a missing marker makes the Run fail.
`test_result: not_checked` means no success-marker check was requested.
An explicit marker does not replace proper TB assertions or `$fatal` on failure.

## Outputs and cleanup

```text
experiments/<design>/sim/<UTC-timestamp>__<fingerprint8>/
├── manifest.json         # inputs/hashes, options, commands, image ID, tool version
├── status.json           # per-stage exit/error/timeout status and cleanup result
├── logs/
│   ├── compile.log
│   └── simulation.log
├── waves/                # FSDB and VCD by default; single format optional
├── outputs/              # TB data/output files; simulation current directory
└── work/                 # simv, simv.daidir, csrc and other compilation files
```

Intermediates are retained by default. `--clean-intermediates` deletes only this
Run's `work/` and simulator-created `outputs/ucli.key`, after the tools stop,
including after a failed run. `logs/`, `waves/`, TB outputs, manifest, and status remain.
If termination cannot be confirmed, cleanup is skipped and reported as a failure.
Cleaning removes the executable, so another simulation needs recompilation in a
new Run. Never clean unrelated projects, shared installations, or earlier Runs.

The runner prints JSON with status, Run, log and waveform paths. It does not
create an `evidence/` directory or run synthesis. Do not rerun commands inside a
completed Run; launch a new Run with the runner.

## Server

Use a native `vcs` if present, otherwise the installed image
`ignis-cr-cn-beijing.cr.volces.com/ignis/synopsys-eda:2018.09`, pinned to its local
image ID. The server's `/usr/local/bin/eda-tool` symlink wrapper automatically
selects this Docker flow, so both compilation and simulation use the container's
Verdi environment without an SSH key or PATH adjustment. `--backend auto` is the
default; `--backend docker` forces Docker and `--backend native` requires a native
installation. `--vcs` selects an explicit native executable; `--docker-image` or
`SIM_VCS_DOCKER_IMAGE` selects the fallback image. Source directories are mounted
read-only at their original absolute paths; only the new Run is mounted writable.

Docker defaults match this server's license setup: `27000@192.168.3.150` and host
mapping `iv-yeu4tcs9ogbw80enl3vc:192.168.3.150`. Override with
`SNPSLMD_LICENSE_FILE` / `LM_LICENSE_FILE` and `SIM_VCS_LICENSE_HOST`.
For native FSDB, configure `VERDI_HOME` and the Verdi PLI paths
(`VERDI_PLI_TAB` / `VERDI_PLI_LIB`); VCD needs no Verdi PLI for automatic dumping.
The current image's VCS helper scripts may report missing Unix `dc`/`find`;
use actual compiler diagnostics, stage exit codes and TB results to judge the run.

Input hashes cover all expanded sources, nested filelists and explicit data files.
`manifest.inputs.sources` records the complete compilation order; `rtl` and `tb`
retain the direct CLI lists. Include directory paths
are recorded, but transitive include contents are not automatically archived or
hashed. Keep sources and dependencies consistent when reproducing a Run.
