# SQL
- Test queries on real sample data; state the dialect (SQLite, PostgreSQL, MySQL, SQL Server). Always use explicit column lists and table aliases.
- Keep rows with no match: `LEFT JOIN`, and count the right-hand column (`COUNT(o.id)`, not `COUNT(*)`). An INNER JOIN silently drops customers without orders. Filter on the right table in the JOIN's `ON`, not in `WHERE`.
- Every non-aggregated selected column must be in `GROUP BY`. `WHERE` filters rows, `HAVING` filters groups. `NULL` never equals anything: use `IS NULL`, `COALESCE`.
- "Top N per group": window functions: `ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC, id)` then filter `rn = 1` in an outer query. Add a deterministic tie-breaker.
- Never build SQL by string concatenation: use parameters (`?`, `$1`, `:name`). Add indexes for columns you filter/join on; use transactions for multi-step writes.
