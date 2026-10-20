# Git and project hygiene
- Check `git status` and `git diff` before and after your work so you know what you changed.
- Never commit, push, reset --hard, clean -fd, or rewrite history unless the user asks.
- Do not touch generated files, lockfiles or vendored code unless the task requires it.
- Respect .gitignore and project docs (README, CONTRIBUTING, AGENTS.md, CLAUDE.md, CODER.md): they are instructions.
- Keep diffs minimal and focused: one concern per change.
