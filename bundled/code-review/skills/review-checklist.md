# Review checklist
1. Does it do what was asked?
2. Correctness: off-by-one, None/null, concurrency, resource leaks, error handling.
3. Security: injection, path traversal, secrets, unsafe deserialization.
4. Tests: new behaviour and bugs covered? deterministic?
5. Style and naming match the codebase.
6. API compatibility and migrations.
Report findings as: [severity] file:line - problem - fix.
