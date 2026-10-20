# Kotlin
- Build/test with Gradle (`./gradlew test`). Prefer `val`, data classes (equals/hashCode for free), null-safety (`?`, `?.`, `?:`), and never `!!` without proof.
- Use collection functions (`map`, `filter`, `groupBy`, `sortedBy`) and sequences for large data; `when` as an expression; sealed classes for state.
- Coroutines: `suspend` functions, structured concurrency (`coroutineScope`, `launch`), no blocking calls on the main dispatcher.
