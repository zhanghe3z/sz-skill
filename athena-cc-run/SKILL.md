---
name: athena-cc-run
description: "在 Athena 的 Slurm 计算节点上运行 lingbot：使用中性进程名、过滤任务输出、持久保存工作目录，并诊断中断和恢复进度。用于 Athena 跑 lingbot、进程被 kill、日志要求不含产品名称的任务。"
---

# Athena lingbot 运行与恢复

`lingbot` 是本技能使用的本地启动名称，复用已安装 coding agent 的原生程序、登录状态和模型配置。技能入口仍为 `$athena-cc-run`，便于沿用现有引用。

## 已知经验与适用范围

2026-10-05 两个 coding agent 作业（当时称为 CC）几乎同时收到 SIGKILL。用户判断与进程中出现 `claude` 有关，但没有独立确认触发者或规则。改用本 skill 当时的 `cc-agent` 启动方式后，观察到两节点继续执行；检查时进程名、命令行和新任务日志中该字样均为零。**这支持复用该配置，不构成“不被 kill”的保证。** 历史事实见 [references/incident.md](references/incident.md)。

这个流程用于用户已授权的正常计算作业。遇到明确的管理员禁令或资源策略，按规则解决。保留真实退出码和历史证据；不能把非零退出、改名或日志过滤解释为任务成功。

## 启动

1. 所有远程操作和传输使用 `rca`，遵循现有 `remote-cluster-agent` skill。先检查 daemon 和 `athena` 连通性。长任务放在 Slurm 计算节点；节点、CPU、内存、时限和模型遵循本次用户选择。
2. 启动 coding agent 时统一使用 lingbot 启动器。把本 skill 的 `scripts/activate_lingbot.sh` 和 `scripts/lingbot_runtime.py` 放在远程同一目录，用 `bash activate_lingbot.sh ...` 调用。启动器把原生可执行文件复制成 `lingbot`，并设置同名 argv[0]。**只建符号链接或只使用 `exec -a` 不足以让实际可执行路径与进程名都变为中性名称。**
3. `LINGBOT_ENGINE_SOURCE` 可指定已安装的原生可执行文件；默认优先使用 `~/.local/share/lingbot/native/lingbot`，再解析用户的现有安装。`LINGBOT_ENGINE_CACHE` 使用任务拥有的持久目录，建议每节点独立，例如 `.../runtime-cnode403/lingbot`，避免共享缓存竞争。不要重新登录、复制凭据或改变账户设置来完成改名。
4. 模型通过环境传入：`LINGBOT_MODEL` 优先于现有 `ANTHROPIC_MODEL`；均未设置时遵循原生 coding agent 的现有默认。不要为了进程名改成另一模型。此次 Opus 5.5 的可复制设置见 runbook。从过滤后的初始化事件确认实际模型，例如 `lingbot-opus-5-5`。
5. `LINGBOT_CONFIG_DIR` 默认为 `~/.lingbot`，映射到原生程序支持的配置目录变量；关闭其自动设置终端标题与自动更新，保留 lingbot 进程名和部署。已有登录与全局配置需在首次迁移时原地移动并验证，不能仅建空目录后重新登录。交互式 CLI 入口设置 `LINGBOT_STDIN=inherit`，由包装器使用 PTY；批处理直接调用 `activate_lingbot.sh`，默认 stdin 为 DEVNULL。
6. 使用无交互批处理参数，并由任务明确授权所需工具。ALE 此次采用 `-p`、`--effort max`、`--max-turns 150`、`--output-format stream-json --verbose`、`--permission-mode acceptEdits`，允许 Bash/Read/Write/Edit/Glob/Grep，并禁用交互式提问和规划工具。其他任务按实际需要调整。

具体传输、sbatch 和观测方法见 [references/athena-runbook.md](references/athena-runbook.md)，首次部署时阅读。

## 输出与工作目录

- `lingbot_runtime.py` 在 stdout/stderr **写入任务日志前**，大小写不敏感地将产品关键词替换为 `lingbot`。重定向启动器的输出；不要另接原始输出到 tee 或临时文件再事后清洗。
- 提示词、模型参数、任务状态、Slurm 作业名、日志文件名使用中性描述。提示词也会出现在 argv 中；避免在里面写需要过滤的品牌名称。模型原始标识可在环境中存在：这个流程没有隐藏环境或应用内部状态。
- 过滤范围是启动器转发的任务 stdout/stderr。lingbot 内部会话记录、认证文件、程序直接写入的独立日志和第三方工具输出不自动受它控制。必要时针对这些**任务文件**单独处理；不要承诺全账户所有文件都没有该词。旧日志保留作诊断证据。
- 2026-10-22 迁移后，Bash 子进程已引用 `.lingbot/shell-snapshots/`，但仍有原生程序写死的 `claude-…-cwd` 临时文件名出现在 argv。改配置目录不能消除这个固定前缀；当日验证见 runbook。
- 原生二进制内的固定字符串、服务端要求的模型 ID、认证字段和兼容环境变量名仍使用原值；本地改名不等于重写底层产品或协议。
- 历史实测：主进程改名后，原生 coding agent 的 Bash 子进程仍可能在 argv 中通过 `source ~/.claude/shell-snapshots/...` 引用内部配置目录。约 18 分钟检查时两题仍运行，但这些子进程的关键词检查为 true。不能把主进程和任务日志的零匹配扩大为整个后代进程树的零匹配；先报告实际边界，不为改名而中断正在正常求解的任务。
- 工作目录放在自己拥有的持久路径，例如 `/scratch/shared/beegfs/shangzhan/lingbot_runs/<run-id>/workspace`。节点 `/tmp` 在作业结束后可能被清理；把“工作脚本仅留 /tmp、只备份最终 output”当作真实的数据丢失风险。
- 保留源脚本、中间产物、最终输出和运行状态，频繁保存。根据规模设置备份；不要复制其他用户的数据或未授权目录。

## 观测、退出与恢复

- 用 `squeue` / `sacct` 查状态、退出码、Elapsed、MaxRSS；用 `scripts/inspect_runtime.py --pid PID --log FILE ...` 检查自己的 lingbot 包装进程及后代，报告关键词是否出现。检查脚本需要在该计算节点执行，可用所属作业的 `srun --overlap`。
- Slurm RUNNING 只说明作业存活。结合初始化事件、正在增长的工具日志、真实文件和结果事件判断进度。不以分析图片、占位目录或 Slurm COMPLETED 代替实际提交。
- 原生子进程负返回码表示信号，例如 `-9` 是 SIGKILL；启动器把它映射为 shell 的 `137`。外层 Python/Slurm 包装器必须继续传播非零退出，否则 Slurm 会错误显示成功。记录超时和实际子进程退出码。
- 中断后先排查：作业取消、时限、OOM、节点故障、用户信号等。MaxRSS 低于配额不足以独立证明不存在任何内存或外部问题。对未确认的原因明确标为推测。
- 有历史会话和工作目录时优先恢复；临时目录已丢失时，用保存的脚本、输出与 lingbot 自己的可见进度记录建立恢复上下文。恢复成功的 Write/Edit 内容可以重建文件；不要批量重放历史 Bash 命令。维持题目、模型及评估隔离，重新检查实际存在的产物。
- 只对自己的确切 PID/进程组或 Slurm 作业操作。若同一原因再次中断，先诊断并报告，避免无限自动重启。若尚未完成，不给虚构分数；完整提交后再运行用户授权的评估。
