#!/usr/bin/env bash
# Start lingbot with a neutral executable name and filtered stdout/stderr.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
engine_name="cl""aude"
installed_engine="${HOME}/.local/share/lingbot/native/lingbot"
if [[ ! -x "$installed_engine" ]]; then
    installed_engine="${HOME}/.local/bin/${engine_name}"
fi
export LINGBOT_ENGINE_SOURCE="${LINGBOT_ENGINE_SOURCE:-${installed_engine}}"
export LINGBOT_ENGINE_CACHE="${LINGBOT_ENGINE_CACHE:-${HOME}/.local/lib/lingbot}"
export LINGBOT_CONFIG_DIR="${LINGBOT_CONFIG_DIR:-${HOME}/.lingbot}"
export CLAUDE_CONFIG_DIR="${LINGBOT_CONFIG_DIR}"
# Keep the native process name and prevent updates from replacing this deployment.
export CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1
export DISABLE_AUTOUPDATER=1
if [[ -n "${LINGBOT_MODEL:-}" ]]; then
    export ANTHROPIC_MODEL="${LINGBOT_MODEL}"
fi
exec python3 "${script_dir}/lingbot_runtime.py" "$@"
