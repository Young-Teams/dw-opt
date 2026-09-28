# syn-dc 默认流程：初始化 -> 读 RTL -> 加载约束 -> 综合 -> 报告 -> 导出。
# source 遇到 Tcl 错误时中止；DC 消息的停止级别另由 sh_script_stop_severity 控制。
set_app_var sh_continue_on_error false

# 1. 初始化：启动入口已加载 common_setup.tcl、dc_setup.tcl 并建立 WORK 设计库。
if {![info exists SYN_DC_SETUP_LOADED] || !$SYN_DC_SETUP_LOADED} {
    error "syn-dc: startup configuration did not complete; check .synopsys_dc.setup and config/"
}
source [file join $CONFIG_DIR report_helpers.tcl]
# SVF 路径在 common_setup 中配置；从这里开始记录 Formality 所需的综合变换。
set_svf $SVF_FILE

# 2. 读 RTL：分析源文件、展开顶层、解析模块和库单元引用。
set analyze_options [list -format sverilog -library WORK]
if {[llength $HDL_DEFINES]} {lappend analyze_options -define $HDL_DEFINES}
analyze {*}$analyze_options $RTL_FILES
elaborate $TOP_MODULE -library WORK
current_design $TOP_MODULE
if {![link]} {error "syn-dc: design linking failed"}
# 为同一子模块的多个实例建立独立的设计副本，便于分别优化；不增加 RTL 实例数量。
uniquify

# 3. 加载项目 SDC：数值使用目标库单位（ASAP7 为 ps/fF，NanGate 为 ns/fF，TCBN12 为 ns/pF）。
# -echo 回显命令，-verbose 显示返回结果；端口绑定由 SDC 中的 get_ports 完成。
source $SDC_FILE -echo -verbose
# 综合时修复直通、多输出共网和常量网络；常量用缓冲器处理。-all 已包含 -feedthroughs。
set_fix_multiple_port_nets -all -buffer_constants -feedthroughs [all_designs]

# 综合前保存有效时钟及结构/时序检查。
syn_dc_report_clocks $REPORT_DIR
redirect -file [file join $REPORT_DIR check_design.rpt] {check_design}
redirect -file [file join $REPORT_DIR check_timing.rpt] {check_timing}
redirect -file [file join $REPORT_DIR clocks.rpt] {report_clock}

# 4. 综合：执行 DC Ultra 优化和标准单元映射。
set compile_start_time [clock seconds]
if {![compile_ultra]} {error "syn-dc: compile_ultra failed"}
set compile_elapsed_sec [expr {[clock seconds] - $compile_start_time}]

# 5. 生成报告：QoR、面积、最差 N 条 max-delay 路径、约束违例和耗时。
# 单位报告只供 Python 解析器归一化结果，不参与输入约束换算。
redirect -file [file join $REPORT_DIR units.rpt] {report_units}
redirect -file [file join $REPORT_DIR qor.rpt] {report_qor}
redirect -file [file join $REPORT_DIR area.rpt] {report_area}
redirect -file [file join $REPORT_DIR timing.rpt] {
    report_timing -delay_type max -max_paths $MAX_PATHS -nworst 1
}
redirect -file [file join $REPORT_DIR constraint.rpt] {
    report_constraint -all_violators
}
redirect -file [file join $REPORT_DIR libraries.rpt] {list_libs}
syn_dc_report_runtime $REPORT_DIR $compile_elapsed_sec

# 6. 导出结果：门级网表、DDC 和综合后约束。
change_names -rules verilog -hierarchy
write -format verilog -hierarchy \
    -output [file join $MAPPED_DIR ${TOP_MODULE}_netlist.v]
write -format ddc -hierarchy \
    -output [file join $MAPPED_DIR ${TOP_MODULE}.ddc]
write_sdc [file join $MAPPED_DIR ${TOP_MODULE}.sdc]

# 停止 SVF 记录，将内部缓冲的信息写完并关闭文件，供后续 Formality 使用。
set_svf -off
exit
