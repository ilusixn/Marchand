# Perl
- Always `use strict; use warnings;`. Run `perl file.pl`; tests via `prove`. Declare variables with `my`; pass arrays/hashes by reference (`\@list`, `\%h`) and return references.
- `sort` compares as strings: use `sort { $a <=> $b }` for numbers and `$b <=> $a` for descending; sort returns a new list, it does not change the original.
- Regex captures: `if ($line =~ /^\s*(\w+)\s*=\s*(.*?)\s*$/) { $h{$1} = $2 }`. Use non-greedy `.*?`, anchors, and `/x` for readability. `split /;/, $text` then trim each part.
- `die` with a message, `eval {}` to catch; `local $_` when using `$_` in functions. Context matters (scalar vs list): `scalar(@a)` for counts.
- Files: three-argument `open(my $fh, '<', $path) or die ...`, then `close`.
