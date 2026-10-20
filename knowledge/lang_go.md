# Go
- `go build ./...`, `go vet ./...`, `go test ./...` (add `-race` when concurrency is involved); `gofmt` formatting is mandatory. A module needs `go.mod`.
- Handle EVERY returned error. Wrap with `fmt.Errorf("context: %w", err)` so callers can use `errors.Is/As`; define sentinel errors with `errors.New`.
- Slices share memory: `append` may write into the caller's backing array. When a function must not alias, copy (`make` + `copy`) or use a full slice expression `s[:len(s):len(s)]`.
- Maps are not safe for concurrent writes (mutex or `sync.Map`); iteration order is random. Always close/receive channels deliberately; every goroutine needs a way to stop (context, done channel); use `sync.WaitGroup`.
- Zero values are useful: design types so the zero value works. Accept interfaces, return structs. Table-driven tests with `t.Run`.
- `defer` runs at function exit (watch loops); loop variables per-iteration since Go 1.22.
