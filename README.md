# DW-OPT

基本算子优化科研工作区，用于自研代码开发、benchmark 验证和实验探索。代码按影响范围进行独立审查，实验结果与结论通过 `task.md` 交由人审阅。

## 仓库结构

```text
dw-opt/
├── src/                     # 自研算子、优化算法、代码生成器与共享框架
├── bench/                   # benchmark 定义、基线、用例、参考模型与测量入口
│   └── mult/                # 现有乘法基线 RTL 与 testbench
├── tasks/                   # 纳入 Git 的任务说明、审阅记录和复现配置
│   └── <任务名>/
│       ├── task.md
│       └── config/          # 按需建立
├── experiments/             # 本地运行产物，Git 仅保留 README.md
├── docs/                    # 代码审查约定与任务模板
├── AGENTS.md                # Codex 项目约定
├── .codex/agents/           # 项目自定义 Agent，包含独立审查角色
├── .codex/skills/           # 项目技能及配套工具
├── .agents/skills           # 指向 ../.codex/skills 的发现入口
├── papers/                  # 本地论文与参考材料，不纳入 Git
├── learn/                   # 本地学习材料与工具链，不纳入 Git
└── designware/              # 本地 IP 资源，不纳入 Git
```

`<任务名>/` 和 `config/` 在需要时创建。目录职责与使用说明：

| 入口 | 内容 |
|---|---|
| [src/](src/README.md) | 自己编写并维护的代码 |
| [bench/](bench/README.md) | 可重复使用的 benchmark；当前有 [mult](bench/mult/README.md) |
| [tasks/](tasks/README.md) | 每项任务的目标、代码版本、配置、Run 索引和人工审阅记录 |
| [experiments/](experiments/README.md) | 日志、波形、网表、原始报告、指标及其他生成产物 |
| [代码审查](docs/code-review.md) | 审查触发条件、独立上下文、版本与修复复核 |

## Git 范围

`src/`、`bench/`、`tasks/`、`docs/` 和项目协作文件纳入版本管理。`experiments/README.md` 用于保留结果目录的说明，运行产物留在本地。

`papers/`、`learn/`、`designware/` 由根目录 `.gitignore` 排除；普通 Git 克隆不包含这些材料或实验结果。它们可作为本地参考资源使用，需要跨机器复现时另行准备，任务记录应说明依赖及版本。

`syn-dc` 的工艺库目录 `.codex/skills/syn-dc/assets/libs/` 及其中的配套文件同样不纳入 Git。克隆后需自行准备库文件，放入约定路径，或通过 `--target-db` / `SYN_DC_TARGET_DB` 指定外部库；runner 不会自动下载工艺库。

## 开发与实验

1. 确定目标、范围、验收与适用的资源预算。持续跟踪的任务使用 [task.md 模板](docs/templates/task.md)，保存到 `tasks/<任务名>/task.md`。
2. 在 `src/` 实现，用 `bench/` 验证。保留公共基线，单次任务参数和配置写入任务目录。
3. 按有意义的小阶段 commit；共享实现、框架或评测逻辑的修改触发独立代码审查，修复后复核，阶段完成后按约定 push。
4. 固定实际代码与配置后运行实验，将产物写入 `experiments/`，在 `task.md` 汇总证据、结果和未验证项。
5. 将实验任务标记为待人工审阅，由人决定结论是否可采纳及下一步。

普通开发不强制创建 PR 或每任务分支；较长重构、互斥方案或并行修改时再隔离分支或 worktree。commit/push 保存进展，不代表实验结论已经通过人工审阅。

## Codex 与已有工具

从仓库根目录启动 `codex`，遵循 [AGENTS.md](AGENTS.md)。项目技能通过 `.agents/skills` 发现：

- [sim-vcs](.agents/skills/sim-vcs/SKILL.md)：执行 VCS 仿真并保存状态、日志和波形。
- [syn-dc](.agents/skills/syn-dc/SKILL.md)：执行 DC 综合并保存配置、报告和网表。
- [wavedrom](.agents/skills/wavedrom/SKILL.md)：绘制时序图。
- [grill-me](.agents/skills/grill-me/SKILL.md)：显式调用方案访谈，使用 `grilling` 工作流。

独立代码审查默认通过可查看过程的 subagent 线程执行，角色定义见 [code_reviewer](.codex/agents/code_reviewer.toml)。历史隔离、委派内容与结果记录见[代码审查约定](docs/code-review.md)。

查看 EDA 脚本参数，以下命令不会启动仿真或综合：

```bash
bash .agents/skills/sim-vcs/scripts/run_simulation.sh --help
bash .agents/skills/syn-dc/scripts/run_synthesis.sh --help
```

正式运行需提供顶层、源文件与工具环境；综合还需指定工艺库和 SDC。通过 `--output-root experiments/<任务名>` 将结果按任务分组，具体 Run 布局见[实验目录说明](experiments/README.md)。

当前 `src/` 仅建立目录约定；`bench/mult` 包含基线 RTL 和 TB，使用前需提供适配器，尚无统一 benchmark CLI。目录结构不代表完整实验框架已经实现。
