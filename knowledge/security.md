# Security and robustness
- Never build SQL, shell commands or file paths by string concatenation with user input; use parameters, argument
  lists, and path normalisation (reject `..`).
- Escape output (HTML) and validate input at boundaries (type, length, range, allow-lists).
- No secrets in code, logs or tests. Read them from environment or config.
- Use the standard crypto library; never invent crypto. Compare secrets in constant time.
- Close files, sockets and processes (context managers / defer / RAII). Set timeouts on network calls.
- Fail loudly on programmer errors, handle expected failures gracefully, never swallow exceptions silently.
