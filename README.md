# sz-skill

本地自定义 skills 集合，包含技能说明、配套脚本和参考文档。

| Skill | 用途 |
| --- | --- |
| [athena-cc-run](athena-cc-run/SKILL.md) | 在 Athena Slurm 计算节点运行 lingbot，支持交互与批处理、过滤任务输出、保存工作目录并诊断中断与恢复进度。 |
| [experiment-registry](experiment-registry/SKILL.md) | 使用 YAML 注册和管理 ML 实验，记录结果、比较运行和跟踪状态。 |
| [remote-cluster-agent](remote-cluster-agent/SKILL.md) | 通过 `rca` CLI 管理远程 GPU 集群，执行命令、传输文件、检查节点并同步代码。 |
| [ue-night-city-atmosphere](ue-night-city-atmosphere/SKILL.md) | 在现有 Unreal Engine 城市场景中设置科幻夜景氛围、雾气、发光背景和曝光。 |

每个目录的 `SKILL.md` 为入口；其他文件按原始目录结构保留。

本仓库仅收录自定义 skills，不包含 Codex 系统内置 skills、插件缓存或本地凭据。
