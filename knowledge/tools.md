# Tools and how to use them well
Tools: list_files, read_file, search, edit_file, write_file, run_command, plan, ask_user, finish.

- read_file shows line numbers; they are NOT part of the file. When you copy text into edit_file `old`, copy only the
  code, exactly, including indentation. If edit_file says the text was not found, read the file again and copy it.
- edit_file needs `old` to appear exactly once. Add one neighbouring line to make it unique.
- search takes a regex. Use it to find definitions, call sites, config keys, error messages.
- run_command runs in the project root. Chain nothing fancy. Quote paths with spaces. Long-running servers must not be
  started in the foreground. Use short timeouts for tests when possible.
- After EACH edit, run the narrowest useful check (one test file, a syntax check, a type check). Before `finish`, run
  the broader check (full test suite or build) if it is reasonably fast.

Example of a good session (shape only):
  user: "make add() handle None"
  1. search pattern "def add" -> src/calc.py:12
  2. read_file src/calc.py
  3. plan ["add None handling in add()", "add a test", "run tests"]
  4. edit_file src/calc.py (small change)
  5. edit_file tests/test_calc.py (new test next to existing ones)
  6. run_command "python -m pytest -q tests/test_calc.py"  -> passes
  7. run_command "python -m pytest -q" -> passes
  8. finish "add() now treats None as 0. Test added in tests/test_calc.py. Full suite: 42 passed."
