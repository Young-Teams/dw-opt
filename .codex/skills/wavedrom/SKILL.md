---
name: wavedrom
description: Create, edit, render, and validate WaveDrom digital timing diagrams from natural-language signal behavior or WaveJSON/JSON5 sources. Use when needs to draw hardware waveforms, bus transactions, protocol timing, clock/reset sequences, signal relationships, timing arrows, or produce SVG timing-diagram assets with the WaveDrom CLI.
---

# WaveDrom

Create readable WaveJSON sources and render them to SVG with the installed WaveDrom CLI.

## Workflow

1. Extract the signals, clock edges, cycle boundaries, values, and causal relationships from the request. State any assumption that affects timing.
2. Choose one visible column per meaningful time unit. Keep all `wave` and `node` strings aligned to that shared timeline; use `phase` only when a half-cycle shift is intentional.
3. Write the source as a `.json5` file beside the requested output. Preserve the source so the diagram remains editable.
4. Use descriptive lane names. Group related lanes, label bus values with `data`, and add `node`/`edge` annotations only when they clarify a relationship.
5. Render with:

   ```bash
   .codex/skills/wavedrom/scripts/render-wave.sh input.json5 output.svg
   ```

   Resolve the script relative to this skill directory when the working directory differs.
6. Verify that the command exits successfully, the SVG is non-empty, and the intended events line up. Inspect the rendered image when visual tooling is available.
7. Return both the editable `.json5` source and the rendered `.svg` unless the user requests only one artifact.

## Diagram Guidelines

- Prefer the shortest timeline that communicates the behavior.
- Use `.` to continue the preceding state instead of repeating it.
- Start buses in `x` or `z` when their initial value is unknown or undriven.
- Match every bus-value segment (`=`, `2`-`9`) to one `data` label.
- Use `p`/`n` for repeated clocks and `P`/`N` only when marked active edges add value.
- Use `|` sparingly to show an omitted interval, not as a routine separator.
- Add `head.tick` or `head.tock` when readers need cycle numbers.
- Keep node identifiers unique within a diagram and place each identifier at the exact event column.
- Do not invent setup/hold times, clock polarity, or protocol semantics that the request does not establish.

## Reference

Read [references/tutorial-zh.md](references/tutorial-zh.md) when composing or explaining WaveJSON syntax, selecting wave symbols, adding groups or arrows, embedding WaveDrom in HTML, or troubleshooting alignment.

Use `wavedrom --help` to confirm locally installed CLI flags. The supported rendering form is:

```bash
wavedrom --input source.json5 --indent 2 > output.svg
```
