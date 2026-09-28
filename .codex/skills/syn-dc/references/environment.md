# Execution environment and diagnostics

`--backend auto` prefers native `dc_shell`, except the host's `/usr/local/bin/eda-tool` wrapper, which the runner replaces with its own temporary Docker invocation. Use `--backend native` to require a native installation or `--backend docker` to force Docker. Explicit `--dc-shell` must identify a native executable and cannot be combined with Docker mode.

## Docker and licensing

- Default image: `ignis-cr-cn-beijing.cr.volces.com/ignis/synopsys-eda:2018.09`; it must already be available locally. Override with `--docker-image` or `SYN_DC_DOCKER_IMAGE`.
- License server: `SNPSLMD_LICENSE_FILE`, then `LM_LICENSE_FILE`, then `27000@192.168.3.150`. The selected value is passed as both variables inside the container.
- Host mapping: `SYN_DC_LICENSE_HOST`, default `iv-yeu4tcs9ogbw80enl3vc:192.168.3.150`; an empty value disables the mapping.

The runner mounts inputs read-only and the output root writable, using identical host/container paths. It does not need the running GUI container, SSH or host PATH changes. Startup locates Synopsys libraries through `$synopsys_root`.

## Library Compiler

The checked DC O-2018.06-SP1 environment has no `lc_shell`. Reading a precompiled `.db` for synthesis does not require it. Compiling `.lib` with `read_lib` requires a separate Library Compiler installation and appropriate license; merely selecting another `.lib` cannot replace that tool.

On this installation, `read_lib` and `report_lib` report LCSH-3 without LC. For a precompiled library, use `read_db`, `get_libs` / `get_lib_cells`, `get_attribute`, `list_libs` and a synthesis check. Use `report_units` after linking a design. A failed `report_lib` alone does not mean the `.db` cannot be used.
