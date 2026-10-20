# Lua
- Run `lua file.lua`. Tables are 1-based: the first item is `t[1]`, the last is `t[#t]`; loops are inclusive (`for i = 1, #t do`).
- `#t` is only reliable for sequences without holes; for "how many entries" or sparse/string-keyed tables count with `for _ in pairs(t) do n = n + 1 end`. `ipairs` stops at the first nil.
- Use `local` for variables and functions (globals leak). Modules return a table (`local M = {} ... return M`) loaded with `require`.
- Only `nil` and `false` are falsy (0 and "" are truthy). Strings are immutable; `..` concatenates; `string.format`, `string.gmatch`, patterns are not regex.
- Errors: `error("msg")`, catch with `pcall`. `table.insert/remove/concat/sort`; `math.max/min/floor`.
