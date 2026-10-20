# C / C++
- Build with the project's system (CMake/Make/Meson) or directly: `g++ -std=c++17 -Wall -Wextra -o prog *.cpp`. Read the FIRST compiler error; build only the target you need.
- Match the standard (C++17/20), naming, header layout and formatting (.clang-format/.editorconfig). Changing a header rebuilds many files: touch headers only when needed.
- RAII and smart pointers (`std::unique_ptr`, `std::make_unique`); no raw owning pointers. `const` correctness, references for non-null params, `std::string_view`/`std::span` for views.
- Never erase from a container while iterating it by index/iterator: use the erase-remove idiom (`v.erase(std::remove_if(...), v.end())`) or `std::erase_if` (C++20). push_back/insert can invalidate iterators and references.
- Templates: keep definitions in headers; constrain with `static_assert`/concepts; use `std::min/std::max/std::clamp` (C++17) instead of hand-written ternaries.
- Beware: dangling references to temporaries, signed/unsigned mixes, uninitialised members, missing `virtual` destructors, ODR violations, data races, UB on signed overflow.
- C code: see the C guide (bounded copies, NUL termination, malloc/free).
