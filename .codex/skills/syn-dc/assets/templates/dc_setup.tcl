# DC 环境设置：由 Skill 统一维护，在 common_setup.tcl 之后加载。

# 1. 库搜索目录
# synopsys_root 由当前 dc_shell 提供，适配宿主机和 Docker 中的安装位置。
set DC_LIB_PATH [file join $synopsys_root libraries syn]
set TARGET_LIB_DIRS [list]
foreach db $TARGET_DBS {
    lappend TARGET_LIB_DIRS [file dirname $db]
}
set TARGET_LIB_DIRS [lsort -unique $TARGET_LIB_DIRS]
set_app_var search_path [concat [list .] $INCLUDE_DIRS $TARGET_LIB_DIRS [list $DC_LIB_PATH]]

# 2. 综合和链接库
# target_library：RTL 最终映射到的标准单元库。
# synthetic_library：DC 自带的 DesignWare 等综合库。
# link_library：解析单元和子模块引用；* 表示先查找内存中已加载的设计。
set_app_var target_library    $TARGET_DBS
set_app_var synthetic_library [list dw_foundation.sldb standard.sldb]
set_app_var link_library      [concat [list *] $target_library $synthetic_library]

# 3. 本次运行的工作库、输出目录和共享缓存
foreach dir [list $WORK_DIR $REPORT_DIR $MAPPED_DIR $ALIB_DIR] {
    file mkdir $dir
}
define_design_lib WORK -path $DESIGN_LIB_DIR
set_app_var alib_library_analysis_path $ALIB_DIR

# 4. 启动摘要：批量运行时可直接从 logs/dc.log 确认本次配置。
puts "syn-dc setup loaded"
puts "  design / top     : $DESIGN_NAME / $TOP_MODULE"
puts "  workspace        : $WORKSPACE_DIR"
puts "  run directory    : $RUN_DIR"
puts "  configuration    : $CONFIG_DIR"
puts "  RTL files        : [llength $RTL_FILES]"
puts "  constraints      : $SDC_FILE"
puts "  alib cache       : $ALIB_DIR"
puts "  max paths        : $MAX_PATHS"
puts "  target libraries :"
foreach db $target_library {
    puts "    $db"
}
