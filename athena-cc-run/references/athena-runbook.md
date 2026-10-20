# 部署与作业模板

## RCA 通道

先按 `remote-cluster-agent` skill 检查安装、daemon 和 `athena` 连通性。默认用现有配置，所有 exec/cp 都经过 RCA。

此次另建独立配置 `/Users/shangzhan/Documents/ALE_3D_trials/rca-athena.toml`，socket 为 `/Users/shangzhan/.config/rca/rca-ale-3d.sock`，因为共享 daemon 被其他会话的大文件传输占满。独立 daemon 仅在实际出现这种队列阻塞时考虑；保留节点配置并使用不同 socket，不能停止或重配别的会话的 daemon。

```bash
rca daemon status
rca nodes
# 使用独立配置时，每次调用都加同一个 --config /absolute/path/config.toml。
```

## 传输

把三个脚本传到自己拥有的同一个远程目录：`activate_cc.sh`、`cc_runtime.py`、`inspect_runtime.py`。例如先设置本地变量 `skill_scripts` 与远程变量 `remote_runner`，再分别 `rca cp`。目录创建也用 `rca exec`。不要把本地 macOS 路径误当远程路径。

```bash
skill_scripts="${CODEX_HOME:-$HOME/.codex}/skills/athena-cc-run/scripts"
remote_runner='/users/shangzhan/cc_runs/runner'
rca exec -n athena "mkdir -p '$remote_runner'"
rca cp "$skill_scripts/activate_cc.sh" "athena:$remote_runner/activate_cc.sh"
rca cp "$skill_scripts/cc_runtime.py" "athena:$remote_runner/cc_runtime.py"
rca cp "$skill_scripts/inspect_runtime.py" "athena:$remote_runner/inspect_runtime.py"
```

RCA 版本此次传输限制 50 MB/文件，递归 cp 未实现；小脚本分别传，大目录使用归档或已配置同步。不要重复上传约 240 MB 的原生 CC 程序，远端启动器直接使用已安装的原生程序。本模板依赖 Python 3、Bash 和现有 CC 登录；不复制任何认证文件到本地。

## Batch 模板

下面是远程保存的 `run_task.sbatch` 正文。`RUN_DIR` 和 `RUNNER_DIR` 在提交前设定并导出，必须是绝对路径、用户拥有且已创建。提交前在 `RUN_DIR/workspace` 放好本题输入、`prompt.txt`，以及已有恢复文件。作业资源和节点由 sbatch 参数选择。

```bash
#!/usr/bin/env bash
set -euo pipefail
: "${RUN_DIR:?Set the persistent run directory}"
: "${RUNNER_DIR:?Set the remote runner directory}"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/workspace"
cd "$RUN_DIR/workspace"

export CC_ENGINE_CACHE="$RUN_DIR/runtime-${SLURMD_NODENAME:-$(hostname)}/cc"
# 仅当此次明确要求 Opus 5.5 时使用；其他模型保留用户选择。
provider_name="cl""aude"
export CC_MODEL="${provider_name}-opus-5-5"

# 提示词用 CC 等中性名称；它会出现在进程参数列表。
prompt_text="$(< "$RUN_DIR/prompt.txt")"
bash "$RUNNER_DIR/activate_cc.sh" \
  -p "$prompt_text" --effort max --max-turns 150 \
  --output-format stream-json --verbose \
  --permission-mode acceptEdits \
  --allowedTools Bash,Read,Write,Edit,Glob,Grep \
  --disallowedTools AskUserQuestion,EnterPlanMode,ExitPlanMode,EnterWorktree,RemoteTrigger \
  > "$RUN_DIR/logs/cc.jsonl" 2> "$RUN_DIR/logs/cc.stderr.log" &
cc_pid=$!
printf '%s\n' "$cc_pid" > "$RUN_DIR/cc.pid"
trap 'kill -TERM "$cc_pid" 2>/dev/null || true' TERM INT
if wait "$cc_pid"; then
  exit_code=0
else
  exit_code=$?
fi
printf '%s\n' "$exit_code" > "$RUN_DIR/exit_code.txt"
exit "$exit_code"
```

远程使用 `sbatch --parsable --partition=compute --nodelist=cnode403 --nodes=1 --ntasks=1 --cpus-per-task=16 --mem=64G --time=04:00:00 --job-name=cc-task --output=.../slurm-%j.log /absolute/path/run_task.sbatch`。cnode403、16 CPU、64G、4h 是本次 ALE 的例子，先确认可用资源及用户要求。每题用独立 RUN_DIR、独立 job；两节点并行是本次用户明确授权的安排。

如果有额外 Python 包装器，在 finally 中保存产物和状态，并让非零退出继续传给 Slurm。限时终止仅处理自己的确切进程组；记录原始信号。只有程序真正输出最终结果且文件齐全时才能说求解完成。

## 检查

1. `squeue -j JOB_ID`，以及 `sacct -j JOB_ID --format=JobID,State,ExitCode,Elapsed,MaxRSS -P`。
2. 已知包装器 PID 时，在该节点调用 `inspect_runtime.py`。正在运行的 Slurm 作业可用：

```bash
srun --jobid=JOB_ID --overlap --nodes=1 --ntasks=1 --cpus-per-task=1 \
  python3 /absolute/path/runner/inspect_runtime.py --pid WRAPPER_PID \
  --log /absolute/path/logs/cc.jsonl --log /absolute/path/logs/cc.stderr.log
```

3. 检查脚本输出不泄露完整提示词或环境值，分别报告 comm、argv、实际可执行路径是否含关键词；日志报告匹配数。进程退出或读不到 /proc 时结合作业状态，不把空列表当作已验证通过。
4. 用 `rca cp` 将任务日志/状态下载后本地读取，初始化事件应为用户指定模型。过滤改变了展示标识，因此原始 `...-opus-5-5` 在任务日志中为 `CC-opus-5-5`。不把日志展示别名用于真实模型配置。
5. 检查模型实际写出的文件和结果事件；没有提交就不运行会产生误导性“零分”的正式评判。若已授权，可在 solver 结束后设置评估依赖；评估报告需明确 incomplete submission 与真实得分的区别。

## 缓存、目录与恢复经验

BeeGFS 上此次跨节点 fcntl 锁没有可靠协调同一安装缓存，因此 Blender/原生程序缓存按节点分开。不要依靠共享 fcntl 锁实现跨节点唯一安装。

此次两个节点都有 `/dev/kvm`，但当前用户无访问权限、无免密 sudo。这与 CC 被杀是不同问题。用户已选择原生 Blender，因此继续该环境并注明不是官方 Windows/KVM；其他任务不能据此自行替换用户要求的运行环境。

恢复时保留原任务输入、模型和环境记录。使用原会话恢复前确认历史目录可用；目录已经清理时，提取之前成功的 Write/Edit 与可见进度记录，恢复相对路径，并告知 CC 检查实际文件。不要执行旧 Bash 日志作为恢复脚本，也不要让恢复上下文混入隐藏评估答案。
