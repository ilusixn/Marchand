# Self-review checklist (run mentally before finish)
- Does the change do exactly what was asked, including the edge cases mentioned?
- Did I read the final diff? Any leftover debug code, commented-out code, TODOs I introduced, wrong indentation?
- Names and style match the neighbouring code? No unrelated edits?
- Error paths handled? Resources released? Off-by-one and None checks done?
- Tests added/updated and actually executed? Did the whole suite still pass?
- Docs/changelog/config that must change together with the code updated (only if the project does that)?
