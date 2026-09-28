# 实验运行产物

这里存放日志、波形、生成 RTL、网表、原始报告和指标等运行产物。Git 只保留本说明，其余内容由 `.gitignore` 排除。任务说明与可复现的配置放在 [tasks/](../tasks/README.md)。

建议按任务分组。现有 VCS / DC runner 支持 `--output-root`，将其设为 `experiments/<任务名>` 后会创建：

```text
experiments/<任务名>/<design>/<sim 或 dc>/<run-id>/
```

未指定输出根目录时，runner 使用 `experiments/<design>/<sim 或 dc>/<run-id>/`。两种路径都记录到对应 `task.md`，不要求移动已有 Run。具体产物结构见 [sim-vcs](../.agents/skills/sim-vcs/SKILL.md) 和 [syn-dc](../.agents/skills/syn-dc/SKILL.md)。

- 每次运行使用独立目录，保留输入身份、配置、命令、工具与库版本、状态和原始输出。
- 完成的 Run 保持不变；修复或更换参数后建立新 Run。失败、超时和负结果同样记录。
- 正式比较先确认功能验证与比较条件，再解释指标；执行成功不等于结论成立。
- `task.md` 汇总结果供人工审阅，并链接或注明 Run 路径。原始结果需自行备份，Git push 不会上传这些文件。
- 临时调试与学习输出不作为正式实验的唯一证据。
