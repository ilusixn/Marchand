# Debug method
1. Reproduce with the exact command.
2. Read the traceback from the bottom; open the first project frame.
3. State a hypothesis. Test it with a print/assert/small script.
4. Bisect inputs, commits (git bisect), layers.
5. Fix the cause not the symptom. Add a failing-then-passing test.
6. Remove debug output.
