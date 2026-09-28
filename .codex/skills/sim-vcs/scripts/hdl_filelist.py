"""Portable HDL filelist subset. Keep the bundled copy in sim-vcs identical."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re


def tokens(text: str, origin: Path) -> list[tuple[str, int]]:
    """Tokenize paths/options, preserving Verilog apostrophes such as 8'hff."""
    result: list[tuple[str, int]] = []
    word: list[str] = []
    quote = None
    line = start = 1
    i = 0

    def flush() -> None:
        if word:
            result.append(("".join(word), start))
            word.clear()

    while i < len(text):
        char = text[i]
        if char == "\\" and quote != "'":
            if i + 1 >= len(text):
                raise ValueError(f"{origin}:{line}: trailing backslash")
            if text[i + 1] == "\n":
                line += 1
            else:
                if not word:
                    start = line
                word.append(text[i + 1])
            i += 2
            continue
        if quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
                line += char == "\n"
            i += 1
            continue
        if text.startswith("/*", i):
            flush()
            end = text.find("*/", i + 2)
            if end < 0:
                raise ValueError(f"{origin}:{line}: unterminated block comment")
            line += text[i:end + 2].count("\n")
            i = end + 2
            continue
        if not word and (char == "#" or text.startswith("//", i)):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        if char == '"' or (char == "'" and not word):
            if not word:
                start = line
            quote = char
        elif char.isspace():
            flush()
            line += char == "\n"
        else:
            if not word:
                start = line
            word.append(char)
        i += 1
    if quote:
        raise ValueError(f"{origin}:{start}: unterminated quote")
    flush()
    return result


def expand_path(value: str, base: Path) -> Path:
    def replace(match: re.Match) -> str:
        name = match.group(1) or match.group(2)
        if name not in os.environ:
            raise ValueError(f"undefined environment variable: {name}")
        return os.environ[name]

    value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", replace, value)
    path = Path(value).expanduser()
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def merge_defines(values: list[str]) -> list[str]:
    """Definitions are global; the last value for a macro name wins."""
    definitions: dict[str, str] = {}
    for value in values:
        name = value.split("=", 1)[0]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", name):
            raise ValueError(f"invalid macro definition: {value}")
        definitions[name] = value
    return list(definitions.values())


def read_filelists(paths: list[Path], workspace: Path, relative_to: str = "workspace") -> dict:
    sources: list[Path] = []
    includes: list[Path] = []
    defines: list[str] = []
    records: list[dict] = []
    active: list[Path] = []

    def visit(path: Path, mode: str) -> None:
        path = path.resolve()
        if path in active:
            raise ValueError("recursive filelist: " + " -> ".join(map(str, active + [path])))
        if len(active) >= 64:
            raise ValueError("filelist nesting exceeds 64 levels")
        content = path.read_bytes()
        base = path.parent if mode == "filelist" else workspace
        records.append({"path": str(path), "sha256": hashlib.sha256(content).hexdigest(),
                        "base_directory": str(base)})
        active.append(path)
        entries = tokens(content.decode("utf-8-sig").replace("\r\n", "\n"), path)
        i = 0
        while i < len(entries):
            token, line = entries[i]
            i += 1
            try:
                if token in {"-f", "-F", "-I", "-D"}:
                    if i == len(entries):
                        raise ValueError(f"missing argument after {token}")
                    value = entries[i][0]
                    i += 1
                    if token in {"-f", "-F"}:
                        visit(expand_path(value, base), "filelist" if token == "-F" else "workspace")
                    elif token == "-I":
                        includes.append(expand_path(value, base))
                    else:
                        defines.append(value)
                elif token.startswith("+incdir+"):
                    values = token[len("+incdir+"):].split("+")
                    if not all(values):
                        raise ValueError("empty +incdir+ entry")
                    includes.extend(expand_path(value, base) for value in values)
                elif token.startswith("+define+"):
                    defines.extend(token[len("+define+"):].split("+"))
                elif token.startswith("-I"):
                    includes.append(expand_path(token[2:], base))
                elif token.startswith("-D"):
                    defines.append(token[2:])
                elif token == "-sverilog":
                    pass  # Both runners already select SystemVerilog.
                elif token.startswith(("-", "+")):
                    raise ValueError(f"unsupported filelist option: {token}")
                else:
                    source = expand_path(token, base)
                    if not source.is_file():
                        raise ValueError(f"source file does not exist: {source}")
                    sources.append(source)
            except (OSError, ValueError) as exc:
                raise ValueError(f"{path}:{line}: {exc}") from exc
        active.pop()

    for path in paths:
        visit(path, relative_to)
    for path in includes:
        if not path.is_dir():
            raise ValueError(f"include directory does not exist: {path}")
    return {"sources": sources, "include_dirs": list(dict.fromkeys(includes)),
            "defines": merge_defines(defines), "filelists": records}


def check_duplicates(sources: list[Path]) -> None:
    seen: set[Path] = set()
    for source in sources:
        if source in seen:
            raise ValueError(f"source listed more than once: {source}")
        seen.add(source)
