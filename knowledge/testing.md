# Testing
- Use the framework already in the repo (pytest/unittest, jest/vitest, go test, cargo test, ctest, JUnit, xUnit).
- A good test is small, deterministic, named for behaviour, and fails for exactly one reason.
- Arrange / Act / Assert. Test the public behaviour, edge cases (empty, None, zero, max, unicode), and error paths.
- Put new tests next to the existing ones and copy their fixtures and style.
- No network, wall-clock sleeps or real files outside a temp dir. Use fakes/mocks only at the boundaries.
- For a bug: write the failing test first, see it fail, fix, see it pass.
- Run the single test while iterating, then the whole suite before finishing.
