# TCBN12 (T12) TT CCS library

The optional target is `assets/libs/tcbn12-tt-ccs/tcbn12ffcllbwp6t16p96cpdtt1v25c_ccs.db`.
Select it with `--target-db` or the commented `TARGET_DBS` example in
`scripts/run_synthesis.sh`; ASAP7 remains the default.

## Source and units

This precompiled file was supplied as
`tcbn12ffcllbwp6t16p96cpdtt1v25c_ccs.db` and copied without changing its binary
contents. Its original source path, SHA-256 and local validation are recorded
in [provenance.json](../assets/libs/tcbn12-tt-ccs/provenance.json).
Paths in that record describe the original import and validation; select the
bundled file under this skill's `assets/libs/` for current runs.

The internal library name is `tcbn12ffcllbwp6t16p96cpdtt1v25c_ccs`, with
1,143 cells at `tt1v25c` (TT, 1.0 V, 25 C). Native units are **ns and pF**:
use `0.5` for a 500 ps clock period and `0.005` for a 5 fF load.
The runner does not convert SDC inputs. See
[library selection and constraints](../SKILL.md#library-selection-and-constraints)
for selection precedence and the required project arguments.

## Local validation

DC `O-2018.06-SP1` loaded the library and completed a four-bit registered-adder
`compile_ultra` run with a 1 ns clock. All 10 mapped instances belong to this
library; the run has no logged errors or missing required outputs. Source and
bundled file hashes remained identical after synthesis. The validation paths
and observed library attributes are in `provenance.json`; this smoke test does
not exhaustively compare timing/power tables or cell functions.
