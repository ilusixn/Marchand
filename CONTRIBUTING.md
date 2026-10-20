# Contributing to Marchand Studio

Thanks for helping. A few simple rules keep the project healthy.

## Before you start
- Open an issue to discuss big changes first.
- By contributing you agree that your work is licensed under the **PolyForm Noncommercial License 1.0.0** (see `LICENSE`) and that the author may also
  offer the project under commercial terms.
- Keep the copyright and `Required Notice` lines in `LICENSE` and `NOTICE` intact.

## Run it
```bash
python3 app.py          # desktop window
python3 server.py       # browser only
```
Python 3.9+ and no third-party packages are needed to run the app.

## Run the tests
```bash
sh tests/run_all.sh
```
You need `python3` with `playwright` and a Chromium for the browser run. Every change should keep the suites green; add a test for new behaviour.
New training tasks must fail before and pass after their reference solution (`tests/verify_curriculum.py`).

## Style
- Plain Python 3.9+ standard library only. No new runtime dependencies.
- Keep the interface keyboard friendly and readable in light and dark themes.
- Be honest in the interface: never claim something works if it was not verified.

## Name and logo
Forks must use their own name and logo (see `TRADEMARK.md`).
