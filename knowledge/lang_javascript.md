# JavaScript
- Check package.json "scripts" first (`npm test`, `npm run build`, `npm run lint`); use the package manager the lockfile names (npm / yarn / pnpm). Plain scripts: `node file.js`.
- Always `await` promises; `array.forEach(async ...)` does NOT wait. Use `await Promise.all(items.map(...))` (keeps order) and wrap in try/catch or `.catch`.
- `Array.prototype.sort()` compares as TEXT: pass `(a, b) => a - b` for numbers, and copy first (`[...arr].sort(...)`) because sort mutates.
- Use `===`, not `==`. Beware `NaN`, `0`/`""`/`null` being falsy: test `value === undefined` or `value == null` deliberately, not `if (!value)` when 0 is valid.
- Closures in loops: use `let`/`const`, never `var`. Do not mutate function arguments or shared objects; return new ones (spread, `structuredClone`).
- Modules: CommonJS (`require`/`module.exports`) vs ESM (`import`/`export`, "type": "module", file extensions required in imports). Match what the project uses.
- Numbers are floating point (`0.1 + 0.2`); use integers (cents) or `toFixed` only for display. Dates: months are 0-based.
- Tests: node:test / assert, jest, vitest, mocha: use the one already in the repo. Never leave `.only`.
