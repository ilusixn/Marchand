# PHP
- Run `php file.php`; project tests via `composer test` / `vendor/bin/phpunit`. Use `declare(strict_types=1);` and type hints; PHP 8 syntax is fine (match, named args, null-safe `?->`).
- SQL: ALWAYS use PDO prepared statements with bound parameters, never string concatenation. Escape HTML output with `htmlspecialchars($s, ENT_QUOTES)`.
- Comparisons: use `===`/`!==`; `array_unique` compares loosely and is wrong for arrays of arrays: key by a normalised value (`strtolower(trim($email))`) and keep first occurrence in a `$seen` map.
- `empty("0")` is true, `isset` vs `array_key_exists` differ for null values; use `??` for defaults. Do not trust `$_GET/$_POST`: validate and cast.
- Sorting: `usort` with `<=>`. Passwords: `password_hash/password_verify`. Dates: `DateTimeImmutable`.
