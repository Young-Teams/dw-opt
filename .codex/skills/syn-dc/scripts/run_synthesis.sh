#!/usr/bin/env bash
# 手动综合入口：修改下方项目配置，然后执行 bash scripts/run_synthesis.sh。
# 无参数时使用配置区；有参数时全部原样传给 Python runner，不读取配置区。
# 查看命令行参数：bash scripts/run_synthesis.sh --help
# 工艺库通过 TARGET_DBS 指定；留空时使用 runner 的环境变量/默认库选择。
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

if (( $# > 0 )); then
    exec python3 "${SCRIPT_DIR}/run_synthesis.py" "$@"
fi

# ===== 按项目修改这里 =====
# 1. 项目标识：所有相对路径均以 WORKSPACE 为基准。
WORKSPACE="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
DESIGN=""                           # 填写项目名称，或通过命令行传入完整参数
TOP=""                              # RTL 顶层模块名

# 2. RTL 输入：优先使用 FILELIST；设为空字符串时使用 RTL_FILES 数组。
FILELIST=""                         # 非空时使用清单，忽略 RTL_FILES
FILELIST_BASE="workspace"            # 清单内路径的基准：workspace 或 filelist
RTL_FILES=()
INCLUDE_DIRS=()                      # 例如 ("rtl/include")
DEFINES=()                           # 例如 ("SYNTHESIS" "WIDTH=8")

# 3. 工艺库与时序约束：库文件路径可为绝对路径，或相对于 WORKSPACE。
TARGET_DBS=()                       # 空数组：使用 SYN_DC_TARGET_DB 环境变量，未设置则用默认 ASAP7。
# NanGate 示例：同时将下方 SDC_FILE 指向使用 ns/fF 的项目约束文件。
# TARGET_DBS=(
#     ".codex/skills/syn-dc/assets/libs/nangate45-typical-nldm/NangateOpenCellLibrary_typical.db"
# )
# TCBN12 (T12) 示例：同时将 SDC_FILE 指向使用 ns/pF 的项目约束文件。
# TARGET_DBS=(
#     ".codex/skills/syn-dc/assets/libs/tcbn12-tt-ccs/tcbn12ffcllbwp6t16p96cpdtt1v25c_ccs.db"
# )
# 多文件库可在数组中逐行列出同一工艺、模型、工艺角的一组 .db。
# 必须指定项目 SDC，所有时钟名称、端口和周期都在该文件中设置。
SDC_FILE=""                         # 必填：项目的时序约束文件
# SDC 数值使用目标库单位：ASAP7 为 ps/fF，NanGate 为 ns/fF，TCBN12 为 ns/pF；runner 不自动换算。
# 例如 500 ps 时钟在 TCBN12 中写 0.5，5 fF 输出负载在 TCBN12 中写 0.005。

# 4. 综合流程、报告和输出位置
RUN_TCL=""                          # 项目自己的综合脚本；留空使用 Skill 默认流程
MAX_PATHS="10"
OUTPUT_ROOT="$WORKSPACE/experiments" # 输出根目录；可换成其他绝对路径
# OUTPUT_ROOT="" 时使用 WORKSPACE/experiments；runner 会自动建立目录和时间戳子目录。
# ========================

if [[ -z "$DESIGN" || -z "$TOP" || -z "$SDC_FILE" ]] || { [[ -z "$FILELIST" ]] && (( ${#RTL_FILES[@]} == 0 )); }; then
    printf '请先配置 DESIGN、TOP、SDC_FILE 和 FILELIST 或 RTL_FILES，或传入完整命令行参数；用 --help 查看用法。\n' >&2
    exit 2
fi

args=(
    --workspace "$WORKSPACE"
    --design "$DESIGN"
    --top "$TOP"
    --sdc "$SDC_FILE"
    --max-paths "$MAX_PATHS"
)
if [[ -n "$FILELIST" ]]; then
    args+=(--filelist "$FILELIST" --filelist-base "$FILELIST_BASE")
elif (( ${#RTL_FILES[@]} > 0 )); then
    args+=(--rtl "${RTL_FILES[@]}")
fi
for value in "${INCLUDE_DIRS[@]}"; do args+=(--include-dir "$value"); done
for value in "${DEFINES[@]}"; do args+=(--define "$value"); done
if (( ${#TARGET_DBS[@]} > 0 )); then
    args+=(--target-db "${TARGET_DBS[@]}")
fi
if [[ -n "$RUN_TCL" ]]; then
    args+=(--run-tcl "$RUN_TCL")
fi
if [[ -n "$OUTPUT_ROOT" ]]; then
    args+=(--output-root "$OUTPUT_ROOT")
fi

printf '运行命令：' >&2
printf ' %q' python3 "${SCRIPT_DIR}/run_synthesis.py" "${args[@]}" >&2
printf '\n' >&2
exec python3 "${SCRIPT_DIR}/run_synthesis.py" "${args[@]}"
