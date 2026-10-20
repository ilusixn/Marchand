# Reverse engineering and analysing unknown code, data and binaries (defensive and educational)
Use this for formats, protocols, compiled output and obfuscated code you are allowed to analyse (your own files, CTF/training material, legacy data, interoperability, malware triage in a sandbox). Never help bypass licences, DRM, anti-cheat or write malware.
1. OBSERVE before guessing. Collect samples. Look at file type/magic bytes (`file`, first 16 bytes), length, printable strings (`strings`), entropy, repeated patterns, and compare several samples side by side (what changes when only one input field changes?).
2. HYPOTHESISE small and write it down: header/magic, version, endianness, length fields (count/size before data), fixed vs variable records, checksums (sum, XOR, CRC), string encodings. Test each hypothesis against EVERY sample, not just one.
3. Binary data: use `struct` (`<` little-endian, `>` big-endian; `H`=u16, `I`=u32, `B`=u8, `h`=i16). Offsets matter: walk the bytes with a cursor and validate lengths before reading. Raise a clear error on truncated or malformed input.
4. Layered encodings: try hex, base64, zlib/gzip, JSON, XOR in turn and look at the result after each layer; write a loop that detects and peels layers automatically.
5. XOR / repeating keys: use KNOWN PLAINTEXT (a known header like "HTTP/1.1 200 OK" or "%PDF") to recover key bytes (`key[i] = cipher[i] ^ plain[i]`), then find the shortest repeating period.
6. Compiled code: read assembly top to bottom, name registers by role, find the loop and its exit condition, work out what each instruction does to the value (shifts and masks reveal bit tricks), then re-implement in a high-level language and TEST it against many inputs (including 0, 1, max, powers of two).
7. Obfuscated scripts: rename identifiers by meaning, inline lookup tables, evaluate small pieces in a REPL, and keep a test that compares the clean version with the original on many inputs.
8. Black-box behaviour: tabulate inputs and outputs, look at differences, ratios, modulo patterns and bit patterns, form a formula, then verify it on all samples and fresh inputs.
9. Protocols: find the framing (start/end bytes, length), message types, byte order, and checksum; decode with a table of types; reject invalid packets.
10. Unknown databases/files: use their own metadata (sqlite_master, PRAGMA, file headers) rather than guessing.
11. Finish by writing the discovered format/algorithm down (a short spec), a parser/re-implementation, and a round-trip or sample-based test.
