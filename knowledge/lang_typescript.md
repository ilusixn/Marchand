# TypeScript
- Run the type checker (`npx tsc --noEmit`) and the tests. Fix type errors properly; avoid `any`, `as` casts and `// @ts-ignore`. Prefer `unknown` plus narrowing.
- Narrow before use: `typeof`, `in`, `instanceof`, discriminated unions with a literal `kind`. Do not use truthiness to check numbers (0 is valid): compare with `null`/`undefined`.
- Generics: constrain with `extends` (`K extends string | number`), let inference work, return precise types (`Record<K, T[]>`).
- Types vanish at runtime: validate untrusted data (JSON, network) with real checks. `Number.isInteger`, `Array.isArray`.
- Same async rules as JavaScript (`await`, `Promise.all`). Optional chaining `?.` and `??` for defaults (`??` keeps 0 and "").
- Quick runs without a build: `node --experimental-strip-types file.ts` (Node 22.6+, type annotations only: no enums or namespaces).
