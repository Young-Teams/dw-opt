# 默认流程的报告辅助函数；source 本文件只定义函数，不执行报告命令。

# 保存 SDC 加载后的时钟，供默认解析器读取；不创建或绑定时钟。
proc syn_dc_report_clocks {report_dir} {
    set fid [open [file join $report_dir clocks.tsv] w]
    puts $fid "name\tperiod\twaveform\tsources"
    # clk 是遍历 DC 对象的局部变量，与 RTL 端口名无关。
    foreach_in_collection clk [get_clocks *] {
        set clock_name [get_object_name $clk]
        set clock_period [get_attribute $clk period]
        set clock_waveform [get_attribute $clk waveform]
        set clock_sources [get_attribute $clk sources]
        set source_names [list]
        # 虚拟时钟没有源端口/引脚；其他时钟将源对象转换为名称。
        if {[sizeof_collection $clock_sources] > 0} {
            set source_names [get_object_name $clock_sources]
        }
        # 时间数值保留 DC 原生单位；四个字段用制表符分隔。
        puts $fid [join [list \
            $clock_name \
            $clock_period \
            [join $clock_waveform ,] \
            [join $source_names ,] \
        ] "\t"]
    }
    close $fid
}

# 单独记录 compile_ultra 耗时，单位为秒。
proc syn_dc_report_runtime {report_dir elapsed_sec} {
    set fid [open [file join $report_dir runtime.rpt] w]
    puts $fid "compile_command     : compile_ultra"
    puts $fid "compile_elapsed_sec : $elapsed_sec"
    close $fid
}
