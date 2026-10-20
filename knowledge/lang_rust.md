# Rust
- Iterate with the compiler: `cargo check`, then `cargo test`, `cargo clippy`, `cargo fmt`. Single file: `rustc --edition 2021 file.rs`. Read the error AND the help text; `rustc --explain E0308` explains codes.
- Ownership: functions that only read take `&T`/`&str`/`&[T]`, not owned `String`/`Vec<T>`; clone only when you truly need a copy. Moved values cannot be used again: borrow instead.
- Errors: return `Result<T, E>` and use `?`; map errors with `map_err`; avoid `unwrap()`/`expect()` outside tests and truly impossible cases. Use `Option` for absence.
- Prefer iterators (`map`, `filter`, `collect`, `sum`) to index loops. Pattern match exhaustively. Derive `Debug, Clone, PartialEq` where useful.
- Lifetimes: let elision work; add `'a` only when the compiler asks. Mutable borrow `&mut` is exclusive: end it before taking another.
- Concurrency: `Arc<Mutex<T>>`, channels; `Send`/`Sync` errors mean shared state needs wrapping.
