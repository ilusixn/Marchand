# Ruby
- Run `ruby file.rb`; tests with `rake test`/`bundle exec rspec`/minitest as the project does. Methods return the last expression; `puts` prints, `p` inspects.
- Prefer `each_with_object`, `map`, `select`, `group_by`, `tally`, `sum`; `text.scan(/[a-z0-9']+/i)` extracts words. Do not mutate arguments (`dup`, `map` instead of `map!`).
- `Hash.new([])` shares ONE default array between keys: use `Hash.new { |h, k| h[k] = [] }` or `fetch(key, 0)`. Keys: `"a"` and `:a` differ; convert with `to_sym`/`transform_keys`.
- Only `nil` and `false` are falsy (0 and "" are truthy). Use `&.` for safe navigation, `||=` for defaults, `raise ArgumentError, "msg"` for bad input.
- Blocks/procs/lambdas: `yield`, `block_given?`; symbols `&:upcase`. Freeze constants.
