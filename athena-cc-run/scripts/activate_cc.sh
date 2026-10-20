#!/usr/bin/env bash
# Start CC with a neutral executable name and filtered stdout/stderr.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
engine_name="cl""aude"
export CC_ENGINE_SOURCE="${CC_ENGINE_SOURCE:-${HOME}/.local/bin/${engine_name}}"
export CC_ENGINE_CACHE="${CC_ENGINE_CACHE:-${HOME}/.local/lib/cc}"
if [[ -n "${CC_MODEL:-}" ]]; then
    export ANTHROPIC_MODEL="${CC_MODEL}"
fi
exec python3 "${script_dir}/cc_runtime.py" "$@"
