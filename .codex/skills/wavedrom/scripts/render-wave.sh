#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: render-wave.sh <input.json5> [output.svg]" >&2
}

if (( $# < 1 || $# > 2 )); then
  usage
  exit 2
fi

input_path=$1
output_path=${2:-${input_path%.*}.svg}

if [[ ! -f "$input_path" ]]; then
  echo "WaveDrom input not found: $input_path" >&2
  exit 1
fi

if [[ "$output_path" != *.svg ]]; then
  echo "WaveDrom output must use the .svg extension: $output_path" >&2
  exit 1
fi

if command -v wavedrom >/dev/null 2>&1; then
  wavedrom_bin=$(command -v wavedrom)
elif [[ -x "${HOME}/.local/bin/wavedrom" ]]; then
  wavedrom_bin="${HOME}/.local/bin/wavedrom"
else
  echo "WaveDrom CLI is not installed or not on PATH." >&2
  exit 1
fi

output_dir=$(dirname "$output_path")
if [[ ! -d "$output_dir" ]]; then
  echo "Output directory does not exist: $output_dir" >&2
  exit 1
fi

temporary_svg=$(mktemp "${output_path}.tmp.XXXXXX")
trap 'rm -f -- "$temporary_svg"' EXIT

"$wavedrom_bin" --input "$input_path" --indent 2 > "$temporary_svg"

if [[ ! -s "$temporary_svg" ]] || ! grep -q '<svg' "$temporary_svg"; then
  echo "WaveDrom did not produce a valid SVG." >&2
  exit 1
fi

mv -- "$temporary_svg" "$output_path"
trap - EXIT
echo "$output_path"
