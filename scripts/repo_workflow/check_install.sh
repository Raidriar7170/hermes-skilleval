#!/bin/sh
# Optional local/CI smoke. No models or Docker; caller supplies a fresh directory.
set -eu
repo_root=$(git rev-parse --show-toplevel)
check_root=${1:?Pass a fresh absolute output directory}
case "$check_root" in /*) ;; *) printf '%s\n' 'absolute output directory required' >&2; exit 2;; esac
if [ -e "$check_root" ]; then printf '%s\n' 'preserve existing output' >&2; exit 2; fi
mkdir -p "$check_root"
python -m pip wheel "$repo_root" --no-deps -w "$check_root/wheels"
python -m venv "$check_root/env"
"$check_root/env/bin/pip" install "$check_root"/wheels/*.whl
cd "$check_root"
env/bin/hermes-maintain doctor
env/bin/python -c 'import importlib.util; assert all(importlib.util.find_spec(n) is None for n in ["torch", "transformers", "sentence_transformers"])'
env/bin/hermes-maintain recommend --arm F --repository wireservice/csvkit --registry "$repo_root/configs/repo-portability/skills-v1/registry.json" --assets "$repo_root/configs/repo-portability/skills-v1" --fixed-config "$repo_root/configs/repo-portability/fixed-v1.json"
env/bin/hermes-maintain records --index "$repo_root/artifacts/repo-portability/records/index.json" --output "$check_root/records"
