# Java
- Build with the project's tool: `mvn -q test` / `gradle test`; single files: `javac A.java B.java && java Main`. Read the first compiler error.
- Override `equals` AND `hashCode` together (use `Objects.equals/hash`); otherwise HashSet/HashMap misbehave. Compare strings with `.equals`, never `==`.
- Integer division truncates: cast before dividing (`(double) sum / n`); widen to `long` to avoid overflow; guard empty collections/arrays (divide by zero, `get(0)`).
- Prefer immutable fields (`final`), interfaces for types (`List` not `ArrayList`), `Optional` instead of returning null, try-with-resources for streams.
- Do not modify a collection while iterating it (ConcurrentModificationException): use an iterator's `remove` or `removeIf`.
- Use `StringBuilder` in loops; `String.format`/text blocks for messages. Checked exceptions: handle or declare, never swallow silently.
- Tests: JUnit 5 (`@Test`, `assertEquals`) or the project's framework.
