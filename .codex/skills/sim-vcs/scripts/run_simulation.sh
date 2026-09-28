#!/usr/bin/env bash
# 无参数：使用下面的项目配置。有参数：完整透传给 Python runner。
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if (( $# > 0 )); then
    exec python3 "${SCRIPT_DIR}/run_simulation.py" "$@"
fi

# ===== 按项目修改这里 =====
WORKSPACE="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
DESIGN=""                           # 填写项目名称，或通过命令行传入完整参数
TOP=""                              # 测试平台顶层，不是 DUT 顶层
FILELIST=""                         # 非空时使用清单，忽略 RTL_FILES/TB_FILES
FILELIST_BASE="workspace"           # workspace 或 filelist
TB_FILES=()
RTL_FILES=()
INCLUDE_DIRS=()
DEFINES=()
PLUSARGS=()
DATA_FILES=()
TIMESCALE="1ns/1ps"
WAVE_FORMAT="both"                  # both：同时生成 FSDB/VCD；也可选 fsdb 或 vcd
PASS_PATTERN=""                     # 填写 TB 的成功标记；留空仅检查执行状态
CLEAN_INTERMEDIATES=false           # true：删除本次 work/ 和 VCS ucli.key
COMPILE_TIMEOUT=300                 # 墙钟秒数，不是仿真时间
SIM_TIMEOUT=300
OUTPUT_ROOT="${SIM_VCS_OUTPUT_ROOT:-$WORKSPACE/experiments}"
# ========================

if [[ -z "$DESIGN" || -z "$TOP" ]] || { [[ -z "$FILELIST" ]] && (( ${#RTL_FILES[@]} + ${#TB_FILES[@]} == 0 )); }; then
    printf '请先配置 DESIGN、TOP 和 FILELIST 或 RTL_FILES/TB_FILES，或传入完整命令行参数；用 --help 查看用法。\n' >&2
    exit 2
fi

args=(--workspace "$WORKSPACE" --design "$DESIGN" --top "$TOP"
      --timescale "$TIMESCALE" --wave-format "$WAVE_FORMAT"
      --compile-timeout "$COMPILE_TIMEOUT" --sim-timeout "$SIM_TIMEOUT")
if [[ -n "$FILELIST" ]]; then
    args+=(--filelist "$FILELIST" --filelist-base "$FILELIST_BASE")
else
    if (( ${#RTL_FILES[@]} )); then args+=(--rtl "${RTL_FILES[@]}"); fi
    if (( ${#TB_FILES[@]} )); then args+=(--tb "${TB_FILES[@]}"); fi
fi
if (( ${#DATA_FILES[@]} )); then args+=(--data "${DATA_FILES[@]}"); fi
for value in "${INCLUDE_DIRS[@]}"; do args+=(--include-dir "$value"); done
for value in "${DEFINES[@]}"; do args+=(--define "$value"); done
for value in "${PLUSARGS[@]}"; do args+=(--plusarg "$value"); done
if [[ -n "$PASS_PATTERN" ]]; then args+=(--pass-pattern "$PASS_PATTERN"); fi
if [[ -n "$OUTPUT_ROOT" ]]; then args+=(--output-root "$OUTPUT_ROOT"); fi
case "$CLEAN_INTERMEDIATES" in
    true) args+=(--clean-intermediates) ;;
    false) ;;
    *) printf 'CLEAN_INTERMEDIATES 必须为 true 或 false\n' >&2; exit 2 ;;
esac
printf '运行命令：' >&2
printf ' %q' python3 "${SCRIPT_DIR}/run_simulation.py" "${args[@]}" >&2
printf '\n' >&2
exec python3 "${SCRIPT_DIR}/run_simulation.py" "${args[@]}"
