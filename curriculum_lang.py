def register():
    import curriculum
    task = curriculum.task
    from curriculum_re import register_re

    # ------------------------------------------------------------------ JavaScript
    task("js_sort", "Sort numbers correctly", "bug fix", 1,
         "sortNumbers() in numbers.js sorts numbers as text and also modifies the caller's array. Fix it so test.js passes.",
         {"numbers.js": '''function sortNumbers(arr) {
  return arr.sort();
}
module.exports = { sortNumbers };
'''},
         {"test.js": '''const assert = require("assert");
const { sortNumbers } = require("./numbers");

const input = [10, 9, 1, 100, -5];
assert.deepStrictEqual(sortNumbers(input), [-5, 1, 9, 10, 100]);
assert.deepStrictEqual(input, [10, 9, 1, 100, -5]);
assert.deepStrictEqual(sortNumbers([]), []);
console.log("OK");
'''},
         {"numbers.js": '''function sortNumbers(arr) {
  return [...arr].sort((a, b) => a - b);
}
module.exports = { sortNumbers };
'''}, test_cmd="node test.js", lang="javascript", requires=["node"])

    task("js_async", "Await all promises in order", "bug fix", 2,
         "loadUsers() in users.js returns before the users are loaded and the order is wrong. Fix it so test.js passes: results in the same order as ids, and the call rejects if any lookup fails.",
         {"users.js": '''async function loadUsers(ids, getUser) {
  const users = [];
  ids.forEach(async (id) => {
    users.push(await getUser(id));
  });
  return users;
}
module.exports = { loadUsers };
'''},
         {"test.js": '''const assert = require("assert");
const { loadUsers } = require("./users");

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const getUser = async (id) => {
  await wait(30 - id * 10);
  if (id === 99) throw new Error("not found");
  return { id };
};

(async () => {
  assert.deepStrictEqual(await loadUsers([1, 2, 3], getUser), [{ id: 1 }, { id: 2 }, { id: 3 }]);
  assert.deepStrictEqual(await loadUsers([], getUser), []);
  await assert.rejects(() => loadUsers([1, 99], getUser), /not found/);
  console.log("OK");
})();
'''},
         {"users.js": '''async function loadUsers(ids, getUser) {
  return Promise.all(ids.map((id) => getUser(id)));
}
module.exports = { loadUsers };
'''}, test_cmd="node test.js", lang="javascript", requires=["node"])

    # ------------------------------------------------------------------ TypeScript
    ts_probe = 'node --experimental-strip-types -e "const x: number = 1"'
    task("ts_groupby", "Implement a generic groupBy", "implement", 2,
         "Implement groupBy<T, K extends string | number>(items, key) in groupBy.ts: it returns an object that maps each key to the list of items with that key, keeping the original order. Make test.ts pass.",
         {"package.json": '{"type": "module"}\n', "groupBy.ts": '''export function groupBy<T, K extends string | number>(items: T[], key: (item: T) => K): Record<K, T[]> {
  throw new Error("not implemented");
}
'''},
         {"test.ts": '''import assert from "node:assert";
import { groupBy } from "./groupBy.ts";

const words = ["apple", "avocado", "banana", "blueberry", "cherry"];
assert.deepStrictEqual(groupBy(words, (w) => w[0]), { a: ["apple", "avocado"], b: ["banana", "blueberry"], c: ["cherry"] });
assert.deepStrictEqual(groupBy([1, 2, 3, 4, 5], (n) => n % 2), { 1: [1, 3, 5], 0: [2, 4] });
assert.deepStrictEqual(groupBy([], (x: number) => x), {});
console.log("OK");
'''},
         {"groupBy.ts": '''export function groupBy<T, K extends string | number>(items: T[], key: (item: T) => K): Record<K, T[]> {
  const out = {} as Record<K, T[]>;
  for (const item of items) {
    const k = key(item);
    (out[k] ??= []).push(item);
  }
  return out;
}
'''}, test_cmd="node --experimental-strip-types test.ts", lang="typescript", requires=["node"], probe=ts_probe)

    task("ts_zero_id", "Fix a falsy check that drops zero", "bug fix", 1,
         "parseId() in parse.ts treats the id 0 as missing and does not trim strings. Valid ids are non-negative integers (numbers or numeric strings); everything else returns null. Fix it so test.ts passes.",
         {"package.json": '{"type": "module"}\n', "parse.ts": '''export function parseId(input: string | number | null | undefined): number | null {
  if (!input) return null;
  const n = Number(input);
  return Number.isInteger(n) ? n : null;
}
'''},
         {"test.ts": '''import assert from "node:assert";
import { parseId } from "./parse.ts";

assert.strictEqual(parseId(0), 0);
assert.strictEqual(parseId("0"), 0);
assert.strictEqual(parseId(" 42 "), 42);
assert.strictEqual(parseId(7), 7);
assert.strictEqual(parseId(null), null);
assert.strictEqual(parseId(undefined), null);
assert.strictEqual(parseId(""), null);
assert.strictEqual(parseId("   "), null);
assert.strictEqual(parseId(-3), null);
assert.strictEqual(parseId(1.5), null);
assert.strictEqual(parseId("abc"), null);
console.log("OK");
'''},
         {"parse.ts": '''export function parseId(input: string | number | null | undefined): number | null {
  if (input === null || input === undefined) return null;
  const text = String(input).trim();
  if (text === "") return null;
  const n = Number(text);
  return Number.isInteger(n) && n >= 0 ? n : null;
}
'''}, test_cmd="node --experimental-strip-types test.ts", lang="typescript", requires=["node"], probe=ts_probe)

    # ------------------------------------------------------------------ C
    task("c_safe_copy", "Fix a buffer overflow", "security", 2,
         "copy_name() in names.c overflows the destination when the name is too long. It must copy at most cap-1 characters and always NUL-terminate. Fix it so test.c passes.",
         {"names.h": '''#include <stddef.h>
void copy_name(char *dst, size_t cap, const char *src);
''', "names.c": '''#include <string.h>
#include "names.h"

void copy_name(char *dst, size_t cap, const char *src) {
    strcpy(dst, src);
}
'''},
         {"test.c": '''#include <stdio.h>
#include <string.h>
#include "names.h"

int main(void) {
    char buf[16];
    memset(buf, 0x7F, sizeof buf);
    copy_name(buf, 8, "Ada");
    if (strcmp(buf, "Ada") != 0) { puts("short name broken"); return 1; }
    memset(buf, 0x7F, sizeof buf);
    copy_name(buf, 8, "Bartholomew the Third");
    if (strcmp(buf, "Barthol") != 0) { puts("long name must be truncated to 7 chars + NUL"); return 1; }
    for (int i = 8; i < 16; i++) if (buf[i] != 0x7F) { puts("wrote past the end"); return 1; }
    memset(buf, 0x7F, sizeof buf);
    copy_name(buf, 1, "x");
    if (buf[0] != '\\0') { puts("cap 1 must give empty string"); return 1; }
    copy_name(buf, 0, "x");
    puts("OK");
    return 0;
}
'''},
         {"names.c": '''#include <string.h>
#include "names.h"

void copy_name(char *dst, size_t cap, const char *src) {
    if (cap == 0) return;
    size_t n = strlen(src);
    if (n > cap - 1) n = cap - 1;
    memcpy(dst, src, n);
    dst[n] = '\\0';
}
'''}, test_cmd="gcc -Wall -o {exe:t} test.c names.c && {exe:t}", lang="c", requires=["gcc"])

    task("c_sum_range", "Fix an off-by-one in a range sum", "bug fix", 1,
         "sum_range(a, n, from, to) in range.c must add the elements from index `from` up to but not including `to`, and clamp `to` to n. Fix it so test.c passes.",
         {"range.h": '''#include <stddef.h>
long sum_range(const int *a, size_t n, size_t from, size_t to);
''', "range.c": '''#include "range.h"

long sum_range(const int *a, size_t n, size_t from, size_t to) {
    long total = 0;
    for (size_t i = from; i <= to; i++) {
        total += a[i];
    }
    return total;
}
'''},
         {"test.c": '''#include <stdio.h>
#include "range.h"

int main(void) {
    int a[] = {1, 2, 3, 4, 5};
    if (sum_range(a, 5, 0, 5) != 15) { puts("whole array"); return 1; }
    if (sum_range(a, 5, 1, 3) != 5) { puts("middle"); return 1; }
    if (sum_range(a, 5, 2, 2) != 0) { puts("empty range"); return 1; }
    if (sum_range(a, 5, 3, 100) != 9) { puts("to must be clamped to n"); return 1; }
    if (sum_range(a, 5, 4, 2) != 0) { puts("from > to"); return 1; }
    puts("OK");
    return 0;
}
'''},
         {"range.c": '''#include "range.h"

long sum_range(const int *a, size_t n, size_t from, size_t to) {
    long total = 0;
    if (to > n) to = n;
    for (size_t i = from; i < to; i++) {
        total += a[i];
    }
    return total;
}
'''}, test_cmd="gcc -Wall -o {exe:t} test.c range.c && {exe:t}", lang="c", requires=["gcc"])

    # ------------------------------------------------------------------ C++
    task("cpp_erase", "Remove items safely while iterating", "bug fix", 2,
         "remove_negatives() in vec.cpp erases from the vector inside a loop, which skips elements and invalidates iterators. Fix it with the erase-remove idiom so test.cpp passes.",
         {"vec.h": '''#pragma once
#include <vector>
void remove_negatives(std::vector<int>& v);
''', "vec.cpp": '''#include "vec.h"

void remove_negatives(std::vector<int>& v) {
    for (auto it = v.begin(); it != v.end(); ++it) {
        if (*it < 0) v.erase(it);
    }
}
'''},
         {"test.cpp": '''#include <cstdio>
#include <vector>
#include "vec.h"

int main() {
    std::vector<int> a{1, -2, -3, 4, -5, 6};
    remove_negatives(a);
    if (a != std::vector<int>{1, 4, 6}) { std::puts("consecutive negatives"); return 1; }
    std::vector<int> b{-1, -1, -1};
    remove_negatives(b);
    if (!b.empty()) { std::puts("all negative"); return 1; }
    std::vector<int> c{};
    remove_negatives(c);
    std::vector<int> d{3, 0, 2};
    remove_negatives(d);
    if (d != std::vector<int>{3, 0, 2}) { std::puts("none negative"); return 1; }
    std::puts("OK");
    return 0;
}
'''},
         {"vec.cpp": '''#include "vec.h"
#include <algorithm>

void remove_negatives(std::vector<int>& v) {
    v.erase(std::remove_if(v.begin(), v.end(), [](int x) { return x < 0; }), v.end());
}
'''}, test_cmd="g++ -std=c++17 -Wall -o {exe:t} test.cpp vec.cpp && {exe:t}", lang="cpp", requires=["g++"])

    task("cpp_clamp", "Write a template function", "implement", 2,
         "Implement the template clamp_all(values, lo, hi) in clamp.h: it returns a new std::vector with every value limited to the range [lo, hi] and leaves the input untouched. It must work for int and double. Make test.cpp pass.",
         {"clamp.h": '''#pragma once
#include <vector>

// TODO: template<typename T> std::vector<T> clamp_all(const std::vector<T>& values, T lo, T hi);
'''},
         {"test.cpp": '''#include <cstdio>
#include <vector>
#include "clamp.h"

int main() {
    const std::vector<int> a{-5, 0, 5, 10, 15};
    auto r = clamp_all(a, 0, 10);
    if (r != std::vector<int>{0, 0, 5, 10, 10}) { std::puts("ints"); return 1; }
    if (a != std::vector<int>{-5, 0, 5, 10, 15}) { std::puts("input modified"); return 1; }
    auto d = clamp_all(std::vector<double>{-1.5, 0.25, 9.75}, 0.0, 1.0);
    if (d != std::vector<double>{0.0, 0.25, 1.0}) { std::puts("doubles"); return 1; }
    if (!clamp_all(std::vector<int>{}, 0, 1).empty()) { std::puts("empty"); return 1; }
    std::puts("OK");
    return 0;
}
'''},
         {"clamp.h": '''#pragma once
#include <algorithm>
#include <vector>

template <typename T>
std::vector<T> clamp_all(const std::vector<T>& values, T lo, T hi) {
    std::vector<T> out;
    out.reserve(values.size());
    for (const T& v : values) out.push_back(std::min(std::max(v, lo), hi));
    return out;
}
'''}, test_cmd="g++ -std=c++17 -Wall -o {exe:t} test.cpp && {exe:t}", lang="cpp", requires=["g++"])

    # ------------------------------------------------------------------ C#
    csproj = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>{{TFM}}</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
'''
    task("cs_top_words", "Top words with LINQ", "implement", 2,
         "TopWords() in Words.cs must return the n most frequent words, case-insensitive (results in lower case), with ties broken alphabetically. Fix it so Program.cs (the test) passes.",
         {"app.csproj": csproj, "Words.cs": '''public static class Words
{
    public static List<string> TopWords(IEnumerable<string> words, int n)
    {
        return words.GroupBy(w => w).OrderByDescending(g => g.Count()).Take(n).Select(g => g.Key).ToList();
    }
}
'''},
         {"Program.cs": '''var words = new[] { "The", "cat", "the", "DOG", "a", "cat", "A", "the", "bird" };
void Check(bool ok, string what) { if (!ok) { Console.WriteLine("FAIL: " + what); Environment.Exit(1); } }
Check(Words.TopWords(words, 2).SequenceEqual(new[] { "the", "a" }), "top 2");
Check(Words.TopWords(words, 4).SequenceEqual(new[] { "the", "a", "cat", "bird" }), "tie-break alphabetical");
Check(Words.TopWords(Array.Empty<string>(), 3).Count == 0, "empty");
Console.WriteLine("OK");
'''},
         {"Words.cs": '''public static class Words
{
    public static List<string> TopWords(IEnumerable<string> words, int n)
    {
        return words.Select(w => w.ToLowerInvariant())
            .GroupBy(w => w)
            .OrderByDescending(g => g.Count())
            .ThenBy(g => g.Key, StringComparer.Ordinal)
            .Take(n)
            .Select(g => g.Key)
            .ToList();
    }
}
'''}, test_cmd="dotnet run --nologo -v q", lang="csharp", requires=["dotnet"])

    task("cs_initials", "Handle null and blank names", "robustness", 1,
         "Initials() in Names.cs throws on null or blank input. It must return the upper-case first letters of every word (for example \"ada king lovelace\" gives \"AKL\"), and an empty string for null, empty or whitespace. Make Program.cs (the test) pass.",
         {"app.csproj": csproj, "Names.cs": '''public static class Names
{
    public static string Initials(string? name)
    {
        return string.Concat(name!.Split(' ').Select(p => char.ToUpper(p[0])));
    }
}
'''},
         {"Program.cs": '''void Check(string got, string want) { if (got != want) { Console.WriteLine($"FAIL: got '{got}', wanted '{want}'"); Environment.Exit(1); } }
Check(Names.Initials("ada king lovelace"), "AKL");
Check(Names.Initials("  grace   hopper "), "GH");
Check(Names.Initials(null), "");
Check(Names.Initials(""), "");
Check(Names.Initials("   "), "");
Check(Names.Initials("x"), "X");
Console.WriteLine("OK");
'''},
         {"Names.cs": '''public static class Names
{
    public static string Initials(string? name)
    {
        if (string.IsNullOrWhiteSpace(name)) return "";
        var parts = name.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return string.Concat(parts.Select(p => char.ToUpperInvariant(p[0])));
    }
}
'''}, test_cmd="dotnet run --nologo -v q", lang="csharp", requires=["dotnet"])

    # ------------------------------------------------------------------ Java
    task("java_hashcode", "Fix equals without hashCode", "bug fix", 2,
         "Money objects are equal but a HashSet keeps duplicates. Fix the class in Money.java (equals and hashCode must agree) so CheckMain.java passes.",
         {"Money.java": '''public final class Money {
    private final long cents;
    private final String currency;

    public Money(long cents, String currency) {
        this.cents = cents;
        this.currency = currency;
    }

    @Override
    public boolean equals(Object o) {
        if (!(o instanceof Money)) return false;
        Money m = (Money) o;
        return cents == m.cents && currency.equals(m.currency);
    }
}
'''},
         {"CheckMain.java": '''import java.util.*;

public class CheckMain {
    static void check(boolean ok, String what) {
        if (!ok) { System.out.println("FAIL: " + what); System.exit(1); }
    }

    public static void main(String[] args) {
        Set<Money> set = new HashSet<>();
        set.add(new Money(500, "EUR"));
        set.add(new Money(500, "EUR"));
        set.add(new Money(500, "USD"));
        check(set.size() == 2, "duplicates in set");
        check(new Money(1, "EUR").hashCode() == new Money(1, "EUR").hashCode(), "equal objects need equal hash codes");
        Map<Money, String> m = new HashMap<>();
        m.put(new Money(100, "EUR"), "one euro");
        check("one euro".equals(m.get(new Money(100, "EUR"))), "map lookup");
        check(!new Money(1, "EUR").equals(null), "null");
        System.out.println("OK");
    }
}
'''},
         {"Money.java": '''import java.util.Objects;

public final class Money {
    private final long cents;
    private final String currency;

    public Money(long cents, String currency) {
        this.cents = cents;
        this.currency = currency;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Money)) return false;
        Money m = (Money) o;
        return cents == m.cents && currency.equals(m.currency);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cents, currency);
    }
}
'''}, test_cmd="javac Money.java CheckMain.java && java CheckMain", lang="java", requires=["javac", "java"])

    task("java_average", "Fix integer division in an average", "bug fix", 1,
         "average() in Stats.java truncates the result and crashes on an empty array. It must return the exact mean as a double, and 0.0 for an empty array. Make CheckMain.java pass.",
         {"Stats.java": '''public class Stats {
    public static double average(int[] values) {
        int sum = 0;
        for (int v : values) sum += v;
        return sum / values.length;
    }
}
'''},
         {"CheckMain.java": '''public class CheckMain {
    static void check(boolean ok, String what) {
        if (!ok) { System.out.println("FAIL: " + what); System.exit(1); }
    }

    public static void main(String[] args) {
        check(Stats.average(new int[]{1, 2}) == 1.5, "1.5");
        check(Stats.average(new int[]{4, 4, 4}) == 4.0, "4.0");
        check(Stats.average(new int[]{}) == 0.0, "empty");
        check(Stats.average(new int[]{Integer.MAX_VALUE, Integer.MAX_VALUE}) == (double) Integer.MAX_VALUE, "overflow");
        System.out.println("OK");
    }
}
'''},
         {"Stats.java": '''public class Stats {
    public static double average(int[] values) {
        if (values.length == 0) return 0.0;
        long sum = 0;
        for (int v : values) sum += v;
        return (double) sum / values.length;
    }
}
'''}, test_cmd="javac Stats.java CheckMain.java && java CheckMain", lang="java", requires=["javac", "java"])

    # ------------------------------------------------------------------ Go
    task("go_slice_alias", "Stop slices sharing memory", "bug fix", 2,
         "WithItem() in items.go must return a new slice with the item added and never change the caller's backing array. Two results built from the same base must be independent. Fix it so `go test` passes.",
         {"go.mod": "module marchand/task\n\ngo 1.20\n", "items.go": '''package task

func WithItem(items []int, v int) []int {
	return append(items, v)
}
'''},
         {"items_test.go": '''package task

import (
	"reflect"
	"testing"
)

func TestIndependentResults(t *testing.T) {
	base := make([]int, 3, 10)
	copy(base, []int{1, 2, 3})
	a := WithItem(base, 100)
	b := WithItem(base, 200)
	if !reflect.DeepEqual(a, []int{1, 2, 3, 100}) {
		t.Fatalf("a = %v", a)
	}
	if !reflect.DeepEqual(b, []int{1, 2, 3, 200}) {
		t.Fatalf("b = %v", b)
	}
}

func TestEmpty(t *testing.T) {
	if got := WithItem(nil, 1); !reflect.DeepEqual(got, []int{1}) {
		t.Fatalf("got %v", got)
	}
}
'''},
         {"items.go": '''package task

func WithItem(items []int, v int) []int {
	out := make([]int, len(items), len(items)+1)
	copy(out, items)
	return append(out, v)
}
'''}, test_cmd="go test ./...", lang="go", requires=["go"])

    task("go_errors_is", "Wrap errors so errors.Is works", "bug fix", 2,
         "ParsePort() in port.go must wrap ErrInvalidPort with %w so callers can use errors.Is, and must reject ports outside 1..65535. Fix it so `go test` passes.",
         {"go.mod": "module marchand/task\n\ngo 1.20\n", "port.go": '''package task

import (
	"errors"
	"fmt"
	"strconv"
)

var ErrInvalidPort = errors.New("invalid port")

func ParsePort(s string) (int, error) {
	n, err := strconv.Atoi(s)
	if err != nil {
		return 0, fmt.Errorf("parse %q: %v", s, err)
	}
	return n, nil
}
'''},
         {"port_test.go": '''package task

import (
	"errors"
	"testing"
)

func TestValid(t *testing.T) {
	for in, want := range map[string]int{"80": 80, "65535": 65535, "1": 1} {
		got, err := ParsePort(in)
		if err != nil || got != want {
			t.Fatalf("%q: got %d, %v", in, got, err)
		}
	}
}

func TestInvalid(t *testing.T) {
	for _, in := range []string{"abc", "", "0", "65536", "-5"} {
		_, err := ParsePort(in)
		if !errors.Is(err, ErrInvalidPort) {
			t.Fatalf("%q: expected ErrInvalidPort, got %v", in, err)
		}
	}
}
'''},
         {"port.go": '''package task

import (
	"errors"
	"fmt"
	"strconv"
)

var ErrInvalidPort = errors.New("invalid port")

func ParsePort(s string) (int, error) {
	n, err := strconv.Atoi(s)
	if err != nil {
		return 0, fmt.Errorf("parse %q: %w", s, ErrInvalidPort)
	}
	if n < 1 || n > 65535 {
		return 0, fmt.Errorf("port %d out of range: %w", n, ErrInvalidPort)
	}
	return n, nil
}
'''}, test_cmd="go test ./...", lang="go", requires=["go"])

    # ------------------------------------------------------------------ Rust
    task("rust_borrow", "Fix a move error by borrowing", "bug fix", 2,
         "The program does not compile: count_vowels() takes its argument by value but the caller needs the text afterwards. Change lib.rs so test_main.rs compiles and passes (hint: take a &str).",
         {"lib.rs": '''pub fn count_vowels(s: String) -> usize {
    s.chars().filter(|c| "aeiouAEIOU".contains(*c)).count()
}
'''},
         {"test_main.rs": '''mod lib;

fn main() {
    let text = String::from("Reverse Engineering");
    assert_eq!(lib::count_vowels(&text), 8);
    assert_eq!(lib::count_vowels(&text), 8);
    assert_eq!(lib::count_vowels("sky"), 0);
    assert_eq!(lib::count_vowels(""), 0);
    println!("OK");
}
'''},
         {"lib.rs": '''pub fn count_vowels(s: &str) -> usize {
    s.chars().filter(|c| "aeiouAEIOU".contains(*c)).count()
}
'''}, test_cmd="rustc --edition 2021 -o {exe:t} test_main.rs && {exe:t}", lang="rust", requires=["rustc"])

    task("rust_parse_pair", "Parse a pair with Result", "implement", 2,
         "Implement parse_pair() in lib.rs: it parses text like \"3,4\" (spaces allowed around the numbers) into (i32, i32), and returns Err(String) with a helpful message for anything else. Make test_main.rs pass.",
         {"lib.rs": '''pub fn parse_pair(s: &str) -> Result<(i32, i32), String> {
    unimplemented!()
}
'''},
         {"test_main.rs": '''mod lib;

fn main() {
    assert_eq!(lib::parse_pair("3,4"), Ok((3, 4)));
    assert_eq!(lib::parse_pair(" -7 , 12 "), Ok((-7, 12)));
    for bad in ["", "3", "3,", ",4", "a,b", "1,2,3", "3;4"] {
        let r = lib::parse_pair(bad);
        assert!(r.is_err(), "should reject {:?}", bad);
        assert!(!r.unwrap_err().is_empty());
    }
    println!("OK");
}
'''},
         {"lib.rs": '''pub fn parse_pair(s: &str) -> Result<(i32, i32), String> {
    let parts: Vec<&str> = s.split(',').collect();
    if parts.len() != 2 {
        return Err(format!("expected two numbers separated by a comma, got {:?}", s));
    }
    let a = parts[0].trim().parse::<i32>().map_err(|e| format!("first number: {}", e))?;
    let b = parts[1].trim().parse::<i32>().map_err(|e| format!("second number: {}", e))?;
    Ok((a, b))
}
'''}, test_cmd="rustc --edition 2021 -o {exe:t} test_main.rs && {exe:t}", lang="rust", requires=["rustc"])

    # ------------------------------------------------------------------ PHP
    task("php_dedupe", "Deduplicate users by email", "bug fix", 2,
         "dedupe_users() in users.php must keep the first user for each e-mail address, ignoring letter case and surrounding spaces, and keep the original order. Fix it so test.php passes.",
         {"users.php": '''<?php
function dedupe_users(array $users): array {
    return array_unique($users, SORT_REGULAR);
}
'''},
         {"test.php": '''<?php
require __DIR__ . "/users.php";

$users = [
    ["name" => "Ann", "email" => "ann@example.com"],
    ["name" => "Bob", "email" => "bob@example.com"],
    ["name" => "Ann Again", "email" => " ANN@example.com "],
    ["name" => "Cy", "email" => "cy@example.com"],
    ["name" => "Bobby", "email" => "Bob@Example.com"],
];
$out = dedupe_users($users);
$names = array_map(fn($u) => $u["name"], $out);
if ($names !== ["Ann", "Bob", "Cy"]) { echo "FAIL: " . json_encode($names) . "\\n"; exit(1); }
if (dedupe_users([]) !== []) { echo "FAIL: empty\\n"; exit(1); }
echo "OK\\n";
'''},
         {"users.php": '''<?php
function dedupe_users(array $users): array {
    $seen = [];
    $out = [];
    foreach ($users as $u) {
        $key = strtolower(trim($u["email"]));
        if (isset($seen[$key])) continue;
        $seen[$key] = true;
        $out[] = $u;
    }
    return $out;
}
'''}, test_cmd="php test.php", lang="php", requires=["php"])

    task("php_pdo", "Fix SQL injection with PDO", "security", 2,
         "find_user() in repo.php builds SQL with string concatenation. Use a prepared statement so test.php passes (and quotes in names are handled).",
         {"repo.php": '''<?php
function find_user(PDO $db, string $name): array {
    $stmt = $db->query("SELECT id, name FROM users WHERE name = '" . $name . "'");
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}
'''},
         {"test.php": '''<?php
require __DIR__ . "/repo.php";

$db = new PDO("sqlite::memory:");
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->exec("CREATE TABLE users (id INTEGER, name TEXT)");
$db->exec("INSERT INTO users VALUES (1, 'ann'), (2, 'bob'), (3, 'o''neil')");
if (count(find_user($db, "bob")) !== 1) { echo "FAIL: bob\\n"; exit(1); }
if (count(find_user($db, "x' OR '1'='1")) !== 0) { echo "FAIL: injection\\n"; exit(1); }
$r = find_user($db, "o'neil");
if (count($r) !== 1 || $r[0]["id"] != 3) { echo "FAIL: quote in name\\n"; exit(1); }
echo "OK\\n";
'''},
         {"repo.php": '''<?php
function find_user(PDO $db, string $name): array {
    $stmt = $db->prepare("SELECT id, name FROM users WHERE name = ?");
    $stmt->execute([$name]);
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}
'''}, test_cmd="php test.php", lang="php", requires=["php"], probe='php -r "new PDO(\'sqlite::memory:\');"')

    # ------------------------------------------------------------------ Ruby
    task("ruby_symbolize", "Symbolize hash keys deeply", "implement", 2,
         "Implement deep_symbolize(obj) in util.rb: it converts string keys to symbols in nested hashes, including hashes inside arrays, without modifying the input. Make test.rb pass.",
         {"util.rb": '''def deep_symbolize(obj)
  raise NotImplementedError
end
'''},
         {"test.rb": '''require_relative "util"

input = { "name" => "x", "tags" => [{ "id" => 1 }, 2], "meta" => { "a" => { "b" => 3 } } }
copy = Marshal.load(Marshal.dump(input))
out = deep_symbolize(input)
expected = { name: "x", tags: [{ id: 1 }, 2], meta: { a: { b: 3 } } }
raise "wrong result: #{out.inspect}" unless out == expected
raise "input modified" unless input == copy
raise "scalar" unless deep_symbolize(5) == 5
puts "OK"
'''},
         {"util.rb": '''def deep_symbolize(obj)
  case obj
  when Hash then obj.each_with_object({}) { |(k, v), h| h[k.to_sym] = deep_symbolize(v) }
  when Array then obj.map { |v| deep_symbolize(v) }
  else obj
  end
end
'''}, test_cmd="ruby test.rb", lang="ruby", requires=["ruby"])

    task("ruby_word_counts", "Count words with each_with_object", "bug fix", 1,
         "word_counts() in counts.rb is wrong: it ignores letter case, counts punctuation as part of words, and returns a Hash with a shared default. Fix it so test.rb passes (keys are lower-case strings).",
         {"counts.rb": '''def word_counts(text)
  counts = Hash.new([])
  text.split(" ").each { |w| counts[w] += 1 }
  counts
end
'''},
         {"test.rb": '''require_relative "counts"

r = word_counts("The cat. the DOG! a cat, a bird")
raise "wrong: #{r.inspect}" unless r == { "the" => 2, "cat" => 2, "dog" => 1, "a" => 2, "bird" => 1 }
raise "missing key must be nil" unless r["zebra"].nil?
raise "empty" unless word_counts("") == {}
puts "OK"
'''},
         {"counts.rb": '''def word_counts(text)
  text.downcase.scan(/[a-z0-9']+/).each_with_object({}) { |w, h| h[w] = h.fetch(w, 0) + 1 }
end
'''}, test_cmd="ruby test.rb", lang="ruby", requires=["ruby"])

    # ------------------------------------------------------------------ Perl
    task("perl_kv", "Parse key=value pairs with regex", "implement", 2,
         "Implement parse_kv($text) in kv.pl: it returns a hash reference from text like \"host=db1; port=5432;user = ann\" (pairs separated by semicolons, spaces allowed around keys and values, empty pairs ignored). Make test.pl pass.",
         {"kv.pl": '''use strict;
use warnings;

sub parse_kv {
    my ($text) = @_;
    die "not implemented";
}

1;
'''},
         {"test.pl": '''use strict;
use warnings;
require "./kv.pl";

my $h = parse_kv("host=db1; port=5432;user = ann");
die "wrong" unless $h->{host} eq "db1" && $h->{port} eq "5432" && $h->{user} eq "ann" && keys(%$h) == 3;
my $e = parse_kv(";; a=1 ;; ");
die "empty pairs" unless keys(%$e) == 1 && $e->{a} eq "1";
my $v = parse_kv("url=http://x/y?a=b");
die "value with equals" unless $v->{url} eq "http://x/y?a=b";
die "empty" unless keys(%{ parse_kv("") }) == 0;
print "OK\\n";
'''},
         {"kv.pl": '''use strict;
use warnings;

sub parse_kv {
    my ($text) = @_;
    my %h;
    for my $pair (split /;/, $text) {
        next unless $pair =~ /^\\s*([^=\\s]+)\\s*=\\s*(.*?)\\s*$/;
        $h{$1} = $2;
    }
    return \\%h;
}

1;
'''}, test_cmd="perl test.pl", lang="perl", requires=["perl"])

    task("perl_numeric_sort", "Sort numerically in Perl", "bug fix", 1,
         "sorted_desc() in sort.pl sorts as strings. It must return the numbers sorted from largest to smallest (numerically), without changing the caller's array. Make test.pl pass.",
         {"sort.pl": '''use strict;
use warnings;

sub sorted_desc {
    my ($list) = @_;
    return [ reverse sort @$list ];
}

1;
'''},
         {"test.pl": '''use strict;
use warnings;
require "./sort.pl";

my @in = (10, 9, 100, 1, -5, 2.5);
my $out = sorted_desc(\\@in);
die "wrong: @$out" unless "@$out" eq "100 10 9 2.5 1 -5";
die "input changed" unless "@in" eq "10 9 100 1 -5 2.5";
die "empty" unless @{ sorted_desc([]) } == 0;
print "OK\\n";
'''},
         {"sort.pl": '''use strict;
use warnings;

sub sorted_desc {
    my ($list) = @_;
    return [ sort { $b <=> $a } @$list ];
}

1;
'''}, test_cmd="perl test.pl", lang="perl", requires=["perl"])

    # ------------------------------------------------------------------ Lua
    task("lua_last_n", "Fix 1-based indexing", "bug fix", 1,
         "last_n(t, n) in list.lua should return a new table with the last n items (all items if n is larger, an empty table if n <= 0). Lua tables start at index 1. Fix it so test.lua passes.",
         {"list.lua": '''local M = {}

function M.last_n(t, n)
  local out = {}
  for i = #t - n, #t - 1 do
    out[#out + 1] = t[i]
  end
  return out
end

return M
'''},
         {"test.lua": '''local list = require("list")

local function eq(a, b)
  if #a ~= #b then return false end
  for i = 1, #a do if a[i] ~= b[i] then return false end end
  return true
end

assert(eq(list.last_n({1, 2, 3, 4, 5}, 2), {4, 5}), "last 2")
assert(eq(list.last_n({1, 2, 3}, 10), {1, 2, 3}), "n larger than list")
assert(eq(list.last_n({1, 2, 3}, 0), {}), "zero")
assert(eq(list.last_n({1, 2, 3}, -1), {}), "negative")
assert(eq(list.last_n({}, 3), {}), "empty")
print("OK")
'''},
         {"list.lua": '''local M = {}

function M.last_n(t, n)
  local out = {}
  if n <= 0 then return out end
  local first = math.max(1, #t - n + 1)
  for i = first, #t do
    out[#out + 1] = t[i]
  end
  return out
end

return M
'''}, test_cmd="lua test.lua", lang="lua", requires=["lua"])

    task("lua_count_keys", "Count keys in a table with holes", "bug fix", 2,
         "count_keys(t) in tbl.lua uses the # operator, which is wrong for tables with string keys or holes. Return the real number of entries. Make test.lua pass.",
         {"tbl.lua": '''local M = {}

function M.count_keys(t)
  return #t
end

return M
'''},
         {"test.lua": '''local tbl = require("tbl")

assert(tbl.count_keys({}) == 0, "empty")
assert(tbl.count_keys({10, 20, 30}) == 3, "array")
assert(tbl.count_keys({a = 1, b = 2}) == 2, "string keys")
assert(tbl.count_keys({1, 2, nil, 4, x = "y"}) == 4, "holes and mixed keys")
assert(tbl.count_keys({[100] = true, [200] = true}) == 2, "sparse")
print("OK")
'''},
         {"tbl.lua": '''local M = {}

function M.count_keys(t)
  local n = 0
  for _ in pairs(t) do n = n + 1 end
  return n
end

return M
'''}, test_cmd="lua test.lua", lang="lua", requires=["lua"])

    # ------------------------------------------------------------------ Bash
    task("bash_spaces", "Quote variables so spaces work", "bug fix", 1,
         "count_files() in lib.sh breaks on folder names with spaces. Quote it properly and make it print 0 for a missing folder. Make test.sh pass.",
         {"lib.sh": '''count_files() {
  dir=$1
  ls $dir | wc -l
}
'''},
         {"test.sh": '''#!/usr/bin/env bash
. ./lib.sh
tmp=$(mktemp -d)
mkdir "$tmp/my docs"
touch "$tmp/my docs/a.txt" "$tmp/my docs/b b.txt"
n=$(count_files "$tmp/my docs" | tr -d ' ')
[ "$n" = "2" ] || { echo "FAIL: spaces gave '$n'"; exit 1; }
n=$(count_files "$tmp/missing folder" 2>/dev/null | tr -d ' ')
[ "$n" = "0" ] || { echo "FAIL: missing folder gave '$n'"; exit 1; }
echo OK
'''},
         {"lib.sh": '''count_files() {
  local dir=$1
  if [ ! -d "$dir" ]; then
    echo 0
    return
  fi
  find "$dir" -maxdepth 1 -type f | wc -l
}
'''}, test_cmd="bash test.sh", lang="bash", requires=["bash"])

    task("bash_strict", "Make a script fail on errors", "robustness", 2,
         "backup.sh copies a file and prints \"done\" even when the copy fails. Make it stop with a non-zero exit code and an error message on stderr when the source is missing or the copy fails (use set -euo pipefail and check inputs). Make test.sh pass.",
         {"backup.sh": '''#!/usr/bin/env bash
src=$1
dest=$2
cp $src $dest
echo done
'''},
         {"test.sh": '''#!/usr/bin/env bash
tmp=$(mktemp -d)
echo hi > "$tmp/in.txt"
out=$(bash backup.sh "$tmp/in.txt" "$tmp/out.txt")
[ "$?" = "0" ] && [ "$out" = "done" ] && [ -f "$tmp/out.txt" ] || { echo "FAIL: normal copy"; exit 1; }
err=$(bash backup.sh "$tmp/missing.txt" "$tmp/x.txt" 2>&1 >/dev/null); code=$?
[ "$code" != "0" ] || { echo "FAIL: missing source must exit non-zero"; exit 1; }
[ -n "$err" ] || { echo "FAIL: error message expected on stderr"; exit 1; }
out=$(bash backup.sh "$tmp/in.txt" "$tmp/no/such/dir/x.txt" 2>/dev/null); code=$?
[ "$code" != "0" ] && [ "$out" != "done" ] || { echo "FAIL: failed copy must not print done"; exit 1; }
out=$(bash backup.sh 2>/dev/null); code=$?
[ "$code" != "0" ] || { echo "FAIL: usage error"; exit 1; }
echo OK
'''},
         {"backup.sh": '''#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "usage: backup.sh SOURCE DEST" >&2
  exit 2
fi
src=$1
dest=$2
if [ ! -f "$src" ]; then
  echo "error: source file not found: $src" >&2
  exit 1
fi
cp -- "$src" "$dest"
echo done
'''}, test_cmd="bash test.sh", lang="bash", requires=["bash"])

    # ------------------------------------------------------------------ SQL (run through Python's sqlite3)
    sql_runner = '''import sqlite3, sys

def run(query_file, setup, order=True):
    db = sqlite3.connect(":memory:")
    db.executescript(setup)
    sql = open(query_file).read().strip().rstrip(";")
    return db.execute(sql).fetchall()
'''
    task("sql_left_join", "Include customers without orders", "bug fix", 2,
         "query.sql should list every customer with their number of orders (0 when they have none), sorted by name. Columns: name, orders. Fix the query so test_sql.py passes.",
         {"query.sql": '''SELECT c.name, COUNT(o.id) AS orders
FROM customers c
JOIN orders o ON o.customer_id = c.id
ORDER BY c.name;
'''},
         {"test_sql.py": sql_runner + '''
SETUP = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER);
INSERT INTO customers VALUES (1,'Ann'),(2,'Bob'),(3,'Cy');
INSERT INTO orders VALUES (1,1),(2,1),(3,3);
"""
rows = run("query.sql", SETUP)
assert rows == [("Ann", 2), ("Bob", 0), ("Cy", 1)], rows
print("OK")
'''},
         {"query.sql": '''SELECT c.name, COUNT(o.id) AS orders
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.name
ORDER BY c.name;
'''}, lang="sql")

    task("sql_top_per_group", "Top earner per department", "implement", 3,
         "query.sql should return, for each department, the employee with the highest salary (ties: the lowest id wins). Columns: department, name, salary; sorted by department. Use a window function. Make test_sql.py pass.",
         {"query.sql": '''SELECT department, name, salary
FROM employees
ORDER BY department;
'''},
         {"test_sql.py": sql_runner + '''
SETUP = """
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department TEXT, salary INTEGER);
INSERT INTO employees VALUES (1,'Ann','eng',100),(2,'Bob','eng',120),(3,'Cy','eng',120),
 (4,'Di','ops',90),(5,'Ed','ops',80),(6,'Flo','hr',70);
"""
rows = run("query.sql", SETUP)
assert rows == [("eng", "Bob", 120), ("hr", "Flo", 70), ("ops", "Di", 90)], rows
print("OK")
'''},
         {"query.sql": '''SELECT department, name, salary FROM (
  SELECT department, name, salary,
         ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, id ASC) AS rn
  FROM employees
)
WHERE rn = 1
ORDER BY department;
'''}, lang="sql")

    register_re()
