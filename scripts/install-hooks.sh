#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
hook_path=$(git rev-parse --git-path hooks/pre-commit)
marker='# ai-docs-check: managed by scripts/install-hooks.sh'

if [[ -f "$hook_path" ]] && grep -Fq "$marker" "$hook_path"; then
    exit 0
fi

temp_hook=$(mktemp "${hook_path}.XXXXXX")
trap 'rm -f "$temp_hook"' EXIT

if [[ -f "$hook_path" ]]; then
    IFS= read -r first_line < "$hook_path" || true
    if [[ "$first_line" == '#!'* ]]; then
        printf '%s\n' "$first_line" > "$temp_hook"
        printf '%s\n' "$marker" 'python3 scripts/check_ai_docs.py --staged || exit $?' >> "$temp_hook"
        tail -n +2 "$hook_path" >> "$temp_hook"
    else
        printf '%s\n' '#!/bin/sh' "$marker" 'python3 scripts/check_ai_docs.py --staged || exit $?' > "$temp_hook"
        cat "$hook_path" >> "$temp_hook"
    fi
else
    printf '%s\n' '#!/bin/sh' "$marker" 'python3 scripts/check_ai_docs.py --staged || exit $?' > "$temp_hook"
fi

chmod +x "$temp_hook"
mv "$temp_hook" "$hook_path"
echo "Установлена проверка AI-документации: $hook_path"
