# Python
- Follow PEP 8; type hints where the codebase uses them; f-strings; pathlib; context managers for files.
- Run: `python -m pytest -q` (or `python -m unittest`), type check with mypy/pyright if configured, lint with ruff/flake8.
- Beware: mutable default arguments, late-binding closures, `is` vs `==`, bare `except:`, modifying a list while
  iterating, naive datetimes, missing `if __name__ == "__main__"`, relative-import errors (run with `-m`).
- Use `subprocess.run([...], check=True)` with a list, not shell strings. Use `logging`, not print, in libraries.
- Dependencies: use the repo's tool (pip + requirements.txt, poetry, uv). Do not add one unless required.
