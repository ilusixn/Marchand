# Refactoring and design
- Refactor only when asked or when needed for the change. Keep behaviour identical and prove it with tests that pass
  before and after.
- Small steps: extract function, rename, move, inline. Run tests after each step.
- Prefer composition and plain functions/data over deep inheritance. Keep functions short with one purpose.
- Remove duplication only when the duplicates really change for the same reason.
- Public interfaces change last, and all callers are updated in the same change (search for every usage).
