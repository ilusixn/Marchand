# C
- Build with warnings on: `gcc -Wall -Wextra -o prog a.c b.c`, read the FIRST error. Use the project's Makefile/CMake if present.
- Never use `strcpy`, `sprintf`, `gets`; use bounded copies (`snprintf`, `memcpy` with a checked length) and ALWAYS NUL-terminate. Pass buffer sizes with every pointer.
- Off-by-one: loops are `i < n`, never `i <= n`; check index ranges before dereferencing. `size_t` is unsigned: `n - 1` wraps when n is 0.
- Every `malloc` needs a check and a matching `free`; do not use memory after free; initialise variables and structs (`= {0}`).
- Integer overflow on signed types is undefined behaviour; widen (`long`, `int64_t`) before multiplying.
- Headers: include guards or `#pragma once`, declarations in .h, definitions in .c; `const` for read-only pointers.
- Debug with `-g` and gdb, or `-fsanitize=address,undefined` when available.
