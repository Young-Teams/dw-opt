# ASAP7 libraries and this server

The default library set is ASAP7 `asap7sc7p5t_28`, RVT/TT, CCS, 0.7 V,
25 C. It contains INVBUF, SIMPLE, AO, OA, and SEQ libraries and uses ps/fF.
This is a logic-synthesis setup; no physical implementation files are required.

## Source and binary provenance

The local source checkout is `/root/asap7/asap7sc7p5t_28`, commit
`f970bd3c3292b79ae4d022a3ec80533534614066`.
Its original Liberty archives remain unchanged.

The bundled `.db` files are **precompiled**, not compiled on this server.
They come from `phyzhenli/asap7`, commit
`5c2688c0dc5606436b2eca7a9c910894dde148b3`, directory
`asap7sc7p5t_28/DB/CCS`. The publisher identifies them as Library Compiler
outputs. `assets/libs/asap7-rvt-tt-ccs/provenance.json` records the precise
source locations, archive/library hashes, binary hashes, and validation results.
The source PDK's BSD license is retained alongside the binaries.

The `source_lib` paths in `provenance.json` record historical extraction
locations. Use its `source_archive` paths under
`/root/asap7/asap7sc7p5t_28/LIB/CCS` for the retained local sources.

## Units and checks

For this ASAP7 set, verify that DC loads all five libraries, the nominal
corner and unit attributes match the source, and the mapped netlist uses
ASAP7 cells. Check cell availability against the source before interpreting
results. Do not substitute release-27, another threshold-voltage variant or
NLDM files into this release-28 RVT CCS set.

On this DC 2018 image, these CCS libraries produced placeholder `.alib` entries.
Subsequent runs reported OPT-1311 and repeated library analysis despite the
shared cache; do not assume that a populated cache eliminates this startup cost.

Library selection and SDC units are described in [SKILL.md](../SKILL.md).
For missing Library Compiler errors, see [environment.md](environment.md).
