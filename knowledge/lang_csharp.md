# C# / .NET
- Build and run with `dotnet build`, `dotnet test`, `dotnet run`; read the first error. Match the project's target framework and nullable settings.
- Nullable reference types: handle `null` explicitly (`string.IsNullOrWhiteSpace`, `?.`, `??`); never use `!` to silence a warning you have not checked.
- LINQ: `GroupBy`, `OrderBy(...).ThenBy(...)`, `Select`; ties need an explicit `ThenBy`. Normalise case with `ToLowerInvariant()`, compare with `StringComparer.Ordinal`/`OrdinalIgnoreCase`.
- Parse and format numbers/dates with `CultureInfo.InvariantCulture`; use `decimal` for money.
- `async`/`await` all the way: no `.Result`/`.Wait()`; return `Task`, pass `CancellationToken`. Dispose `IDisposable` with `using`.
- Override `Equals` and `GetHashCode` together (or use `record`); prefer `record`/immutable types for data.
- Throw specific exceptions (`ArgumentException`, `InvalidOperationException`) with messages; do not catch `Exception` just to hide errors.
