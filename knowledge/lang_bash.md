# Bash / shell
- Start scripts with `#!/usr/bin/env bash` and `set -euo pipefail`. Check arguments (`[ "$#" -eq 2 ] || { echo "usage: ..." >&2; exit 2; }`) and inputs (`[ -f "$f" ]`).
- ALWAYS quote expansions: `"$var"`, `"$@"`, `"$dir/file"`. Unquoted variables break on spaces and globbing. Use `local` in functions.
- Errors go to stderr (`>&2`) with a non-zero exit code; success prints to stdout. Do not parse `ls`: use `find`, globs, or `while IFS= read -r line`.
- Use `[[ ]]` for tests, `$(command)` not backticks, `"${var:-default}"`, `cp -- "$a" "$b"`. `mktemp -d` and `trap 'rm -rf "$tmp"' EXIT` for temp files.
- Check scripts with `shellcheck` when available. Windows: needs Git Bash or WSL.
