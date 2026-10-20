# PowerShell
- Use `Set-StrictMode -Version Latest` and `$ErrorActionPreference = 'Stop'`. Cmdlets output objects: filter with `Where-Object`, shape with `Select-Object`, not text parsing.
- Quote paths with spaces; use `Join-Path`, `Test-Path`, `-LiteralPath`. Compare with `-eq/-ne/-like/-match` (not `==`). Return values by writing to the pipeline; use `Write-Error`/`throw` for failures and try/catch.
- Pester for tests (`Invoke-Pester`).
