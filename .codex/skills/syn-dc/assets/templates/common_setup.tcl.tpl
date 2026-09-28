# 本次综合参数：runner 从此模板生成 config/common_setup.tcl。
# 参数取自命令行或 run_synthesis.sh；生成后的文件作为本次 Run 的配置记录。

# 1. 设计标识
set DESIGN_NAME @DESIGN_NAME@
set TOP_MODULE  @TOP_MODULE@

# 2. 项目与运行目录
# WORKSPACE_DIR 是项目根目录；RUN_DIR 是带时间戳的实验目录，也是 DC 启动目录。
set WORKSPACE_DIR @WORKSPACE_DIR@
set RUN_DIR       @RUN_DIR@
set CONFIG_DIR    [file join $RUN_DIR config]
set LOG_DIR       [file join $RUN_DIR logs]
set REPORT_DIR    [file join $RUN_DIR reports]
set MAPPED_DIR    [file join $RUN_DIR mapped]

# WORK_DIR 存放本次运行的中间文件；DESIGN_LIB_DIR 存放 analyze 的 WORK 设计库。
set WORK_DIR       [file join $RUN_DIR work]
set DESIGN_LIB_DIR [file join $WORK_DIR design_lib]
# SVF 输出路径；run_dc.tcl 在综合前开启记录、导出后关闭。
set SVF_FILE       [file join $WORK_DIR ${DESIGN_NAME}.svf]
# ALIB_DIR 是同一输出根目录下各 Run 共用的工艺库分析缓存。
set ALIB_DIR @ALIB_DIR@

# 3. RTL 输入：保留 filelist 展开后的编译顺序；路径均已解析为绝对路径。
set RTL_FILES @RTL_FILES@
set INCLUDE_DIRS @INCLUDE_DIRS@
set HDL_DEFINES @HDL_DEFINES@

# 4. 时序约束：指向调用者提供的项目 SDC，时钟及其他约束均由该文件定义。
set SDC_FILE @SDC_FILE@

# 5. 目标工艺库：由调用参数选择；未指定时默认五份 ASAP7 RVT/TT CCS 库。
# TARGET_DBS 是输入文件列表；dc_setup.tcl 将它应用到 DC 的 target_library。
set TARGET_DBS @TARGET_DBS@
# 保留首个库的兼容别名；多库流程使用 TARGET_DBS。
set TARGET_DB [lindex $TARGET_DBS 0]

# 6. 报告参数：输出最差的 N 条 max-delay 路径。
set MAX_PATHS @MAX_PATHS@
