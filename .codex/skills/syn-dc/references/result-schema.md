# syn-dc result schema

## Contents

1. Run identity
2. Metrics
3. Critical paths
4. Directory contract

## Run identity

Each invocation creates a new directory named:

```text
<UTC timestamp with microseconds>__<input fingerprint prefix>
```

The full SHA-256 `fingerprint` in `manifest.json` covers the top module, ordered RTL contents, project SDC contents, all target DBs, DC flow/setup templates, requested path count, execution mode, and Docker image ID when applicable. Equal fingerprints identify equivalent recorded synthesis inputs and flow definitions even when timestamps differ.

`target_dbs[]` contains every library's path and SHA-256 in mapping order. The
legacy `target_db` field remains an alias for the first library; consumers must
use `target_dbs` when comparing complete library sets. Old Runs only have
`target_db`. `execution` records native/Docker mode and the Docker image tag/ID.

When all selected DBs share a directory containing `provenance.json`,
`library_provenance` records that file's path/hash in the manifest and fingerprint.
This applies to either bundled set or a user-provided set. DB hashes are always
recorded, even when there is no common provenance file.

`rtl` is the full expanded compilation order, including filelist sources.
`filelists` records each visited list's path, SHA-256 and effective base directory;
`include_dirs` and `defines` record the resolved preprocessing configuration.
These fields and the bundled filelist parser hash also contribute to the fingerprint.

Startup configuration is recorded separately:

- `setup`: the `.synopsys_dc.setup` source path/hash; `run_path` locates its Run-local copy.
- `dc_setup`: the Run-local `config/dc_setup.tcl`, source path, and hash.
- `common_setup`: the generated `config/common_setup.tcl` path/hash and its template path/hash.
- `report_helpers`: the Run-local `config/report_helpers.tcl`, source path, and hash.

The setup templates and report helper contribute to the input fingerprint. The generated common
setup hash is recorded only in the manifest: its timestamped paths differ between
Runs and must not change the input fingerprint.

## Metrics

Running `scripts/parse_dc_reports.py` creates `metrics.json` with `schema_version: 1`. Synthesis itself does not create normalized metrics.

### `constraints`

- `sdc`: absolute project SDC path used by DC. The runner requires this file and does not generate constraints.
- `sdc_sha256`: effective SDC content hash.
- `clocks[]`: clocks that actually exist in DC after sourcing the SDC.
- `period_ns`, `waveform_ns`: effective DC clock values converted into ns using `reports/units.rpt`.
- `frequency_mhz`: `1000 / period_ns`.
- `sources`: source ports for each clock; empty for virtual clocks.

Using effective DC clocks avoids depending on how variables and expressions were written in the source SDC.

Raw `clocks.tsv`, timing/QoR reports, and exported SDC use DC's native units
(ps for ASAP7, ns for NanGate). All `*_ns` metrics are converted to ns.
Runs whose manifest contains `target_dbs` require `units.rpt`; a missing report
is an error. Only legacy manifests without `target_dbs` retain the original ns
fallback when that report is absent. A malformed units report is always an error.

### `area`

- `cell_area`: DC `Total cell area`; use this as the primary area comparison.
- `combinational_area`: mapped combinational-cell area.
- `noncombinational_area`: mapped sequential-cell area.
- `macro_black_box_area`: mapped macro or black-box area.

Area values use the target library's area units. Do not compare values produced with different target libraries.

### `timing`

- `critical_path_delay_ns`: DC QoR `Critical Path Length`.
- `critical_path_slack_ns`: raw slack of the worst max-delay path; positive values meet timing.
- `wns_ns`: signed worst negative slack normalized as `min(0, critical_path_slack_ns)`.
- `max_paths_requested`: caller-provided `--max-paths N`.
- `paths_reported`: paths DC actually returned.
- `critical_paths[]`: ordered worst max-delay paths.

## Critical paths

Each path records:

- `rank`
- `startpoint`
- `endpoint`
- `path_group`
- `path_type`
- `data_arrival_time_ns`
- `data_required_time_ns`
- `slack_ns`

Paths follow DC `report_timing -delay_type max -max_paths N -nworst 1` ordering. They are the worst setup/max-delay paths, not paths sorted only by combinational depth.

## Directory contract

```text
run/
├── .synopsys_dc.setup             # sources the two startup configuration files
├── manifest.json
├── status.json
├── metrics.json                 # only after parsing
├── summary.md                  # only after parsing
├── config/
│   ├── common_setup.tcl           # generated project parameters and paths
│   ├── dc_setup.tcl               # copied shared DC/library setup
│   ├── run_dc.tcl
│   └── report_helpers.tcl         # effective clocks and runtime procedures
├── logs/dc.log
├── reports/
├── mapped/
└── work/
```

Consumers should read `status.json` before running a parser or trusting metrics. Missing measurements are represented as JSON `null`; raw reports remain authoritative for detailed debugging.

The runner requires nonempty mapped netlist, DDC and exported SDC files, plus
`reports/qor.rpt`, `area.rpt`, `timing.rpt`, `clocks.tsv` and `units.rpt`.
A zero exit code with missing outputs or logged DC errors is a failed Run.
Historical Runs retain their original configuration layouts and files.

The alib cache is not part of an immutable Run. All Runs below one output root share `<output-root>/.cache/dc/alib/` for reusable target-library analysis files. DC may write only placeholder entries for some libraries; those require analysis again on subsequent Runs.
