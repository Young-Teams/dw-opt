# HDL filelists

Use `--filelist path/filelist.f` (alias `-f`) instead of listing each source on
the command line. Repeat the option for multiple lists. Keep synthesis lists
limited to synthesizable design/model files; simulation lists may also include
TB and verification packages. The runner still needs an explicit `--top`.

Example layout with `/root/dw-opt` as `--workspace`; replace these illustrative
filenames with the project's inputs:

```text
// filelist.f
rtl/design.sv
rtl/top.sv
```

```text
// sim_filelist.f
-f filelist.f
tb/tb_top.sv
```

## Supported subset

- Explicit source filenames, blank lines, `#` / `//` comments following whitespace,
  and `/* ... */` block comments.
- Quoted paths, backslash escapes and backslash-newline continuation.
- `$VAR`, `${VAR}` and `~` in paths. Undefined environment variables are errors.
- `-f child.f` and `-F child.f` nested lists; cycles are rejected.
- `+incdir+dir1+dir2`, `-I dir` and `-Idir` include directories.
- `+define+NAME+WIDTH=8`, `-D NAME=VALUE` and `-DNAME=VALUE` macros.
  Verilog literal apostrophes such as `+define+INIT=8'h00` are preserved.
  Escape literal double quotes if they must be part of a macro value.
- `-sverilog` is accepted; both runners already select this language mode.

This is a common portable subset, not a general VCS command-file interpreter.
Options such as `-y`, `-v`, `+libext+`, PLI/linker flags and shell commands are
rejected rather than silently ignored. List model files explicitly. Globs are
not expanded inside lists. Macro expressions containing a literal `+` should
be supplied with the runner's `--define` option instead of `+define+` syntax.

## Paths and order

The top-level filelist path itself always resolves against `--workspace`.
By default, relative entries inside top-level lists also resolve against
`--workspace`, matching the usual invocation of VCS `-f` from the project root.
Set `--filelist-base filelist` to resolve top-level contents against each list's
own directory instead. Absolute paths are unaffected.

Inside a list, the child list filename resolves against that list's current
base. `-f` processes the child's contents relative to `--workspace`; `-F`
processes them relative to the child's own directory. The resulting absolute
source paths and include paths are the same for DC and VCS.

Lists expand recursively in written order. DC compiles direct `--rtl` files
first, then filelist sources. VCS compiles direct `--rtl`, then filelist sources,
then direct `--tb`. A filelist may contain the entire simulation source set, so
`--tb` is optional in that case. Duplicate source paths are errors; do not list
the same TB both in the filelist and in `--tb`.

Definitions are global for the compilation. Later definitions of a name win,
and explicit CLI `--define` values override filelist values. Filelist include
directories precede explicit CLI `--include-dir` entries.

The Shell entries expose `FILELIST` and `FILELIST_BASE`. A nonempty `FILELIST`
selects filelist input and bypasses their direct RTL/TB arrays. Set it empty to
use the arrays. With CLI arguments, Shell forwards the complete arguments as usual.

## Traceability

Each manifest records expanded sources in compilation order, all nested list
paths/hashes and their base directories, effective include paths and macros.
DC's ordered source list is `manifest.rtl`; VCS's is `manifest.inputs.sources`.
Filelists are expanded by the host Python runner, not passed unmodified to a
tool working in a different Run directory. DC receives include paths through
`search_path` and macros through `analyze -define`; VCS receives equivalent
`+incdir+` and `+define+` flags.

Included HDL headers are not automatically discovered or archived; preserve
them together with the explicitly recorded sources. The two skills each bundle
the same `scripts/hdl_filelist.py`, keeping each skill independently usable.
