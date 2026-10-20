# Debugging method
- Reproduce first. Get the exact failing command and its full output. If you cannot reproduce it, say so.
- Read the error bottom-up: the last frame is where it broke, the first project frame is usually where it was caused.
- Form ONE hypothesis, test it with the cheapest experiment (print, assert, a tiny script, a focused test), then decide.
- Bisect: narrow by input, by commit (git bisect / git log -p), by layer (caller, callee, data).
- Check the boring causes first: typos, wrong path or working directory, stale build output or cache, wrong
  environment or version, off-by-one, None/null, encoding, timezone, integer overflow, mutated shared state.
- Fix the cause, not the symptom. Add a regression test that fails before the fix and passes after it.
- If three attempts fail, stop and re-read the code from the entry point; your mental model is probably wrong.
- Remove debug prints before finishing.
