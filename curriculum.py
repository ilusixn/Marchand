TASKS = []


def task(id, title, topic, level, prompt, files, tests, solution, test_cmd=None, lang="python", requires=(), probe=None):
    test_name = sorted(tests)[0]
    TASKS.append({"id": id, "title": title, "topic": topic, "level": level, "prompt": prompt, "files": files, "tests": tests,
                  "solution": solution, "test_cmd": test_cmd or "python " + test_name, "lang": lang, "requires": list(requires), "probe": probe})


task("pagination", "Fix an off-by-one in pagination", "bug fix", 1,
     "The tests in test_pagination.py fail. Fix the bug in pagination.py. Pages start at 1, and a page number below 1 must raise ValueError.",
     {"pagination.py": '''def paginate(items, page, size):
    start = page * size
    return items[start:start + size]
'''},
     {"test_pagination.py": '''from pagination import paginate

items = list(range(10))
assert paginate(items, 1, 3) == [0, 1, 2]
assert paginate(items, 2, 3) == [3, 4, 5]
assert paginate(items, 4, 3) == [9]
assert paginate(items, 5, 3) == []
try:
    paginate(items, 0, 3)
    raise SystemExit("page 0 must raise ValueError")
except ValueError:
    pass
print("OK")
'''},
     {"pagination.py": '''def paginate(items, page, size):
    if page < 1:
        raise ValueError("page starts at 1")
    start = (page - 1) * size
    return items[start:start + size]
'''})

task("slugify", "Implement slugify()", "implement", 1,
     "Implement slugify(text) in text_utils.py so the tests in test_slugify.py pass: lowercase, accents removed, every run of non-alphanumeric characters becomes one dash, no dashes at the ends.",
     {"text_utils.py": '''def slugify(text):
    raise NotImplementedError
'''},
     {"test_slugify.py": '''from text_utils import slugify

assert slugify("Hello World") == "hello-world"
assert slugify("  Crème brûlée!  ") == "creme-brulee"
assert slugify("a--b__c") == "a-b-c"
assert slugify("Ünïcödé 2024 / Édition") == "unicode-2024-edition"
assert slugify("---") == ""
print("OK")
'''},
     {"text_utils.py": '''import re
import unicodedata


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return text.strip("-")
'''})

task("mutable_default", "Fix a mutable default argument", "bug fix", 1,
     "add_tag() in tags.py leaks tags between calls. Find the cause and fix it so test_tags.py passes.",
     {"tags.py": '''def add_tag(tag, tags=[]):
    tags.append(tag)
    return tags
'''},
     {"test_tags.py": '''from tags import add_tag

assert add_tag("a") == ["a"]
assert add_tag("b") == ["b"]
mine = ["x"]
assert add_tag("y", mine) == ["x", "y"]
assert mine == ["x", "y"]
print("OK")
'''},
     {"tags.py": '''def add_tag(tag, tags=None):
    if tags is None:
        tags = []
    tags.append(tag)
    return tags
'''})

task("lru_cache", "Implement an LRU cache class", "implement", 2,
     "Implement the LRUCache class in lru.py (get returns -1 when missing; put evicts the least recently used key when over capacity; get counts as use). Make test_lru.py pass.",
     {"lru.py": '''class LRUCache:
    def __init__(self, capacity):
        pass

    def get(self, key):
        pass

    def put(self, key, value):
        pass
'''},
     {"test_lru.py": '''from lru import LRUCache

c = LRUCache(2)
c.put(1, "a")
c.put(2, "b")
assert c.get(1) == "a"
c.put(3, "c")
assert c.get(2) == -1
assert c.get(3) == "c"
c.put(1, "A")
c.put(4, "d")
assert c.get(3) == -1
assert c.get(1) == "A"
assert c.get(4) == "d"
print("OK")
'''},
     {"lru.py": '''from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.data = OrderedDict()

    def get(self, key):
        if key not in self.data:
            return -1
        self.data.move_to_end(key)
        return self.data[key]

    def put(self, key, value):
        self.data[key] = value
        self.data.move_to_end(key)
        if len(self.data) > self.capacity:
            self.data.popitem(last=False)
'''})

task("roman", "Fix Roman numeral conversion", "bug fix", 2,
     "roman.py converts numbers to Roman numerals but gets 4, 9, 40, 90, 400 and 900 wrong, and accepts invalid input. Fix it so test_roman.py passes (valid range 1 to 3999, otherwise ValueError).",
     {"roman.py": '''VALUES = [(1000, "M"), (500, "D"), (100, "C"), (50, "L"), (10, "X"), (5, "V"), (1, "I")]


def to_roman(n):
    out = ""
    for value, sym in VALUES:
        while n >= value:
            out += sym
            n -= value
    return out
'''},
     {"test_roman.py": '''from roman import to_roman

assert to_roman(1) == "I"
assert to_roman(4) == "IV"
assert to_roman(9) == "IX"
assert to_roman(14) == "XIV"
assert to_roman(40) == "XL"
assert to_roman(90) == "XC"
assert to_roman(400) == "CD"
assert to_roman(1994) == "MCMXCIV"
assert to_roman(3999) == "MMMCMXCIX"
for bad in (0, 4000, -3):
    try:
        to_roman(bad)
        raise SystemExit("must reject %d" % bad)
    except ValueError:
        pass
print("OK")
'''},
     {"roman.py": '''VALUES = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
          (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(n):
    if not 1 <= n <= 3999:
        raise ValueError("number must be between 1 and 3999")
    out = ""
    for value, sym in VALUES:
        while n >= value:
            out += sym
            n -= value
    return out
'''})

task("csv_quotes", "Parse CSV lines with quoted fields", "bug fix", 2,
     "parse_line() in csvline.py breaks on quoted fields that contain commas. Fix it (the standard library can help) so test_csvline.py passes.",
     {"csvline.py": '''def parse_line(line):
    return line.split(",")
'''},
     {"test_csvline.py": '''from csvline import parse_line

assert parse_line("a,b,c") == ["a", "b", "c"]
assert parse_line('1,"Smith, John",x') == ["1", "Smith, John", "x"]
assert parse_line('"say ""hi""",2') == ['say "hi"', "2"]
assert parse_line("") == []
print("OK")
'''},
     {"csvline.py": '''import csv


def parse_line(line):
    if not line:
        return []
    return next(csv.reader([line]))
'''})

task("binary_search", "Fix binary search edge cases", "bug fix", 2,
     "find() in search.py misses some elements. Fix the binary search so test_search.py passes. It must stay O(log n).",
     {"search.py": '''def find(items, target):
    lo, hi = 0, len(items) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
'''},
     {"test_search.py": '''from search import find

data = [1, 3, 5, 7, 9, 11]
for i, v in enumerate(data):
    assert find(data, v) == i, v
assert find(data, 4) == -1
assert find(data, 12) == -1
assert find([], 1) == -1
assert find([2], 2) == 0
print("OK")
'''},
     {"search.py": '''def find(items, target):
    lo, hi = 0, len(items) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
'''})

task("rename", "Rename a function across several files", "multi-file", 2,
     "Rename calc_total() in utils.py to compute_total() and update every caller in the project so test_rename.py passes. Do not leave the old name behind.",
     {"utils.py": '''def calc_total(prices, tax=0.0):
    return round(sum(prices) * (1 + tax), 2)
''', "report.py": '''from utils import calc_total


def build_report(prices):
    return "Total: %.2f" % calc_total(prices, 0.2)
''', "main.py": '''from utils import calc_total

if __name__ == "__main__":
    print(calc_total([1, 2, 3]))
'''},
     {"test_rename.py": '''import pathlib

from report import build_report
from utils import compute_total

assert compute_total([10, 20]) == 30
assert build_report([10, 20]) == "Total: 36.00"
for f in pathlib.Path(".").glob("*.py"):
    if f.name != "test_rename.py":
        assert "calc_total" not in f.read_text(), f.name
print("OK")
'''},
     {"utils.py": '''def compute_total(prices, tax=0.0):
    return round(sum(prices) * (1 + tax), 2)
''', "report.py": '''from utils import compute_total


def build_report(prices):
    return "Total: %.2f" % compute_total(prices, 0.2)
''', "main.py": '''from utils import compute_total

if __name__ == "__main__":
    print(compute_total([1, 2, 3]))
'''})

task("sql_injection", "Fix a SQL injection", "security", 2,
     "find_user() in users.py is vulnerable to SQL injection. Fix it with query parameters so test_users.py passes.",
     {"users.py": '''def find_user(conn, name):
    return conn.execute("SELECT id, name FROM users WHERE name = '%s'" % name).fetchall()
'''},
     {"test_users.py": '''import sqlite3

from users import find_user

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
conn.executemany("INSERT INTO users VALUES (?, ?)", [(1, "ann"), (2, "bob"), (3, "o'neil")])
assert find_user(conn, "bob") == [(2, "bob")]
assert find_user(conn, "x' OR '1'='1") == []
assert find_user(conn, "o'neil") == [(3, "o'neil")]
print("OK")
'''},
     {"users.py": '''def find_user(conn, name):
    return conn.execute("SELECT id, name FROM users WHERE name = ?", (name,)).fetchall()
'''})

task("path_traversal", "Block path traversal", "security", 2,
     "read_note() in notes.py lets callers read files outside the notes folder with names like ../secret.txt. Make it raise ValueError for any name that escapes base_dir, so test_notes.py passes.",
     {"notes.py": '''import os


def read_note(base_dir, name):
    with open(os.path.join(base_dir, name)) as f:
        return f.read()
'''},
     {"test_notes.py": '''import os
import tempfile

from notes import read_note

root = tempfile.mkdtemp()
notes = os.path.join(root, "notes")
os.makedirs(os.path.join(notes, "sub"))
open(os.path.join(notes, "a.txt"), "w").write("A")
open(os.path.join(notes, "sub", "b.txt"), "w").write("B")
open(os.path.join(root, "secret.txt"), "w").write("S")
assert read_note(notes, "a.txt") == "A"
assert read_note(notes, "sub/b.txt") == "B"
for bad in ("../secret.txt", "sub/../../secret.txt", os.path.join(root, "secret.txt")):
    try:
        read_note(notes, bad)
        raise SystemExit("must refuse " + bad)
    except ValueError:
        pass
print("OK")
'''},
     {"notes.py": '''import os


def read_note(base_dir, name):
    base = os.path.realpath(base_dir)
    path = os.path.realpath(os.path.join(base, name))
    if os.path.commonpath([base, path]) != base:
        raise ValueError("note name escapes the notes folder")
    with open(path) as f:
        return f.read()
'''})

task("dedupe_perf", "Make dedupe() fast", "performance", 2,
     "dedupe() in dedupe.py is far too slow on big lists. Make it O(n) while keeping the original order, so test_dedupe.py passes.",
     {"dedupe.py": '''def dedupe(items):
    out = []
    for x in items:
        if x not in out:
            out.append(x)
    return out
'''},
     {"test_dedupe.py": '''import time

from dedupe import dedupe

assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]
assert dedupe([]) == []
big = list(range(20000)) * 2
t = time.time()
assert dedupe(big) == list(range(20000))
assert time.time() - t < 1.0, "too slow"
print("OK")
'''},
     {"dedupe.py": '''def dedupe(items):
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
'''})

task("deep_flatten", "Flatten very deep lists without recursion errors", "bug fix", 3,
     "flatten() in flatten.py crashes with RecursionError on deeply nested lists. Rewrite it without recursion so test_flatten.py passes.",
     {"flatten.py": '''def flatten(items):
    out = []
    for x in items:
        if isinstance(x, list):
            out.extend(flatten(x))
        else:
            out.append(x)
    return out
'''},
     {"test_flatten.py": '''from flatten import flatten

assert flatten([1, [2, [3, 4]], 5]) == [1, 2, 3, 4, 5]
assert flatten([]) == []
deep = [0]
for i in range(1, 3000):
    deep = [deep, i]
assert flatten(deep) == list(range(3000))
print("OK")
'''},
     {"flatten.py": '''def flatten(items):
    out = []
    stack = [iter(items)]
    while stack:
        for x in stack[-1]:
            if isinstance(x, list):
                stack.append(iter(x))
                break
            out.append(x)
        else:
            stack.pop()
    return out
'''})

task("hashable_point", "Make Point usable in sets", "bug fix", 2,
     "Point objects in geometry.py cannot be put in a set and equal points are not deduplicated. Fix the class so test_geometry.py passes.",
     {"geometry.py": '''class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)
'''},
     {"test_geometry.py": '''from geometry import Point

pts = {Point(1, 2), Point(1, 2), Point(3, 4)}
assert len(pts) == 2
assert Point(1, 2) == Point(1, 2)
assert Point(1, 2) != Point(2, 1)
assert {Point(0, 0): "origin"}[Point(0, 0)] == "origin"
print("OK")
'''},
     {"geometry.py": '''class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)

    def __hash__(self):
        return hash((self.x, self.y))
'''})

task("retry", "Implement a retry decorator with backoff", "implement", 3,
     "Implement retry(times, delay, sleep=time.sleep) in retry.py: it retries the function up to `times` attempts, sleeping delay, delay*2, delay*4... between attempts, and re-raises the last error. Make test_retry.py pass.",
     {"retry.py": '''import time


def retry(times, delay, sleep=time.sleep):
    raise NotImplementedError
'''},
     {"test_retry.py": '''from retry import retry

waits = []
calls = {"n": 0}


@retry(times=4, delay=0.5, sleep=waits.append)
def flaky():
    calls["n"] += 1
    if calls["n"] < 3:
        raise IOError("boom")
    return "ok"


assert flaky() == "ok"
assert calls["n"] == 3
assert waits == [0.5, 1.0]

waits.clear()


@retry(times=2, delay=1, sleep=waits.append)
def always():
    raise KeyError("x")


try:
    always()
    raise SystemExit("must re-raise")
except KeyError:
    pass
assert waits == [1]
print("OK")
'''},
     {"retry.py": '''import functools
import time


def retry(times, delay, sleep=time.sleep):
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            wait = delay
            for attempt in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    if attempt == times - 1:
                        raise
                    sleep(wait)
                    wait *= 2
        return inner
    return wrap
'''})

task("cli_flag", "Add a command-line flag", "feature", 2,
     "Add an --upper flag to cli.py that prints the greeting in capitals. Keep the existing behaviour. Make test_cli.py pass.",
     {"cli.py": '''import argparse


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="world")
    a = p.parse_args(argv)
    return "Hello, %s!" % a.name


if __name__ == "__main__":
    print(main())
'''},
     {"test_cli.py": '''from cli import main

assert main([]) == "Hello, world!"
assert main(["--name", "bob"]) == "Hello, bob!"
assert main(["--name", "bob", "--upper"]) == "HELLO, BOB!"
print("OK")
'''},
     {"cli.py": '''import argparse


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="world")
    p.add_argument("--upper", action="store_true")
    a = p.parse_args(argv)
    text = "Hello, %s!" % a.name
    return text.upper() if a.upper else text


if __name__ == "__main__":
    print(main())
'''})

task("deep_merge", "Deep-merge two dictionaries", "implement", 2,
     "merge(a, b) in merge.py only merges the top level. Make it merge nested dictionaries recursively (values from b win) without modifying the inputs, so test_merge.py passes.",
     {"merge.py": '''def merge(a, b):
    return {**a, **b}
'''},
     {"test_merge.py": '''import copy

from merge import merge

a = {"db": {"host": "x", "port": 1}, "debug": False, "tags": [1]}
b = {"db": {"port": 2, "user": "u"}, "debug": True}
a0, b0 = copy.deepcopy(a), copy.deepcopy(b)
assert merge(a, b) == {"db": {"host": "x", "port": 2, "user": "u"}, "debug": True, "tags": [1]}
assert a == a0 and b == b0
assert merge({"x": {"y": 1}}, {"x": 5}) == {"x": 5}
print("OK")
'''},
     {"merge.py": '''import copy


def merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out
'''})

task("dates", "Fix date parsing", "bug fix", 2,
     "parse_date() in dates.py returns wrong dates. It must accept ISO dates (2024-03-05) and European dates (05/03/2024 = 5 March) and raise ValueError for anything else. Make test_dates.py pass.",
     {"dates.py": '''from datetime import datetime


def parse_date(text):
    return datetime.strptime(text, "%Y-%d-%m").date()
'''},
     {"test_dates.py": '''from datetime import date

from dates import parse_date

assert parse_date("2024-03-05") == date(2024, 3, 5)
assert parse_date("05/03/2024") == date(2024, 3, 5)
assert parse_date(" 2024-12-31 ") == date(2024, 12, 31)
for bad in ("2024/03/05", "tomorrow", ""):
    try:
        parse_date(bad)
        raise SystemExit("must reject " + bad)
    except ValueError:
        pass
print("OK")
'''},
     {"dates.py": '''from datetime import datetime


def parse_date(text):
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("unrecognised date: %r" % text)
'''})

task("wrap", "Implement word wrapping", "implement", 2,
     "Implement wrap(text, width) in wrap.py: return a list of lines no longer than width, breaking only between words; a word longer than width goes on its own line. Make test_wrap.py pass.",
     {"wrap.py": '''def wrap(text, width):
    raise NotImplementedError
'''},
     {"test_wrap.py": '''from wrap import wrap

assert wrap("the quick brown fox", 10) == ["the quick", "brown fox"]
assert wrap("a bb ccc", 3) == ["a", "bb", "ccc"]
assert wrap("supercalifragilistic is long", 8) == ["supercalifragilistic", "is long"]
assert wrap("", 5) == []
assert wrap("  spaced   out  ", 20) == ["spaced out"]
print("OK")
'''},
     {"wrap.py": '''def wrap(text, width):
    lines, cur = [], ""
    for word in text.split():
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines
'''})

task("log_summary", "Summarise a log file", "bug fix", 2,
     "summarize(path) in logsum.py should count lines per level (INFO, WARNING, ERROR) but it counts the wrong field and crashes on blank lines. Fix it so test_logsum.py passes.",
     {"logsum.py": '''def summarize(path):
    counts = {}
    for line in open(path):
        level = line.split()[1]
        counts[level] = counts.get(level, 0) + 1
    return counts
'''},
     {"test_logsum.py": '''import os
import tempfile

from logsum import summarize

p = os.path.join(tempfile.mkdtemp(), "app.log")
open(p, "w").write("""2024-01-01 10:00:00 INFO started
2024-01-01 10:00:01 ERROR disk full

2024-01-01 10:00:02 WARNING slow
2024-01-01 10:00:03 ERROR again
""")
assert summarize(p) == {"INFO": 1, "ERROR": 2, "WARNING": 1}
print("OK")
'''},
     {"logsum.py": '''def summarize(path):
    counts = {}
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            level = parts[2]
            counts[level] = counts.get(level, 0) + 1
    return counts
'''})

task("port_config", "Validate a port from the environment", "robustness", 1,
     "get_port(env) in config.py crashes when PORT is missing and accepts nonsense. Default to 8080, accept 1..65535, raise ValueError otherwise. Make test_config.py pass.",
     {"config.py": '''def get_port(env):
    return int(env["PORT"])
'''},
     {"test_config.py": '''from config import get_port

assert get_port({}) == 8080
assert get_port({"PORT": "3000"}) == 3000
assert get_port({"PORT": " 443 "}) == 443
for bad in ("0", "70000", "abc", "-1"):
    try:
        get_port({"PORT": bad})
        raise SystemExit("must reject " + bad)
    except ValueError:
        pass
print("OK")
'''},
     {"config.py": '''def get_port(env):
    raw = env.get("PORT")
    if raw is None:
        return 8080
    port = int(raw.strip())
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return port
'''})

task("transpose", "Fix matrix transpose", "bug fix", 1,
     "transpose() in matrix.py only works for square matrices. Fix it so test_matrix.py passes.",
     {"matrix.py": '''def transpose(m):
    n = len(m)
    return [[m[j][i] for j in range(n)] for i in range(n)]
'''},
     {"test_matrix.py": '''from matrix import transpose

assert transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]
assert transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]
assert transpose([[1], [2], [3]]) == [[1, 2, 3]]
assert transpose([]) == []
print("OK")
'''},
     {"matrix.py": '''def transpose(m):
    return [list(row) for row in zip(*m)]
'''})

task("word_freq", "Top words with tie-breaking", "implement", 2,
     "top_words(text, n) in words.py must be case-insensitive, ignore punctuation, and break ties alphabetically. Fix it so test_words.py passes.",
     {"words.py": '''from collections import Counter


def top_words(text, n):
    return [w for w, _ in Counter(text.split()).most_common(n)]
'''},
     {"test_words.py": '''from words import top_words

text = "The cat. the DOG! a cat, a bird; The end"
assert top_words(text, 2) == ["the", "a"]
assert top_words(text, 4) == ["the", "a", "cat", "bird"]
assert top_words("", 3) == []
print("OK")
'''},
     {"words.py": '''import re
from collections import Counter


def top_words(text, n):
    counts = Counter(re.findall(r"[a-z0-9']+", text.lower()))
    return [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]
'''})

task("bank", "Stop invalid withdrawals", "robustness", 1,
     "The Account class in bank.py allows overdrafts and negative deposits. Make both raise ValueError without changing the balance, so test_bank.py passes.",
     {"bank.py": '''class Account:
    def __init__(self, balance=0):
        self.balance = balance

    def deposit(self, amount):
        self.balance += amount

    def withdraw(self, amount):
        self.balance -= amount
'''},
     {"test_bank.py": '''from bank import Account

a = Account(100)
a.deposit(50)
a.withdraw(30)
assert a.balance == 120
for action, amount in ((a.withdraw, 500), (a.deposit, -5), (a.withdraw, -5), (a.deposit, 0)):
    try:
        action(amount)
        raise SystemExit("must reject")
    except ValueError:
        pass
assert a.balance == 120
print("OK")
'''},
     {"bank.py": '''class Account:
    def __init__(self, balance=0):
        self.balance = balance

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("deposit must be positive")
        self.balance += amount

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("withdrawal must be positive")
        if amount > self.balance:
            raise ValueError("insufficient funds")
        self.balance -= amount
'''})

task("settings_file", "Load settings safely", "robustness", 2,
     "load() in store.py crashes when the settings file is missing or corrupt. Return {} in those cases, and make save() write the file so it can be loaded back. Make test_store.py pass.",
     {"store.py": '''import json


def load(path):
    with open(path) as f:
        return json.load(f)


def save(path, data):
    pass
'''},
     {"test_store.py": '''import os
import tempfile

from store import load, save

d = tempfile.mkdtemp()
p = os.path.join(d, "settings.json")
assert load(p) == {}
save(p, {"theme": "dark", "n": 3})
assert load(p) == {"theme": "dark", "n": 3}
open(p, "w").write("{not json")
assert load(p) == {}
print("OK")
'''},
     {"store.py": '''import json
import os


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)
'''})

task("inventory", "Add a feature with tests already written", "feature", 3,
     "Add remove(name, qty) to Inventory in inventory.py: it lowers the quantity, deletes the item when it reaches 0, and raises KeyError for unknown items and ValueError when removing more than available. Keep the existing methods working. Make test_inventory.py pass.",
     {"inventory.py": '''class Inventory:
    def __init__(self):
        self.items = {}

    def add(self, name, qty=1):
        if qty <= 0:
            raise ValueError("qty must be positive")
        self.items[name] = self.items.get(name, 0) + qty

    def count(self, name):
        return self.items.get(name, 0)
'''},
     {"test_inventory.py": '''from inventory import Inventory

inv = Inventory()
inv.add("apple", 5)
inv.remove("apple", 2)
assert inv.count("apple") == 3
inv.remove("apple", 3)
assert "apple" not in inv.items
try:
    inv.remove("pear", 1)
    raise SystemExit("unknown item must raise KeyError")
except KeyError:
    pass
inv.add("kiwi", 1)
try:
    inv.remove("kiwi", 2)
    raise SystemExit("must raise ValueError")
except ValueError:
    pass
assert inv.count("kiwi") == 1
print("OK")
'''},
     {"inventory.py": '''class Inventory:
    def __init__(self):
        self.items = {}

    def add(self, name, qty=1):
        if qty <= 0:
            raise ValueError("qty must be positive")
        self.items[name] = self.items.get(name, 0) + qty

    def count(self, name):
        return self.items.get(name, 0)

    def remove(self, name, qty=1):
        if name not in self.items:
            raise KeyError(name)
        if qty <= 0 or qty > self.items[name]:
            raise ValueError("cannot remove %d %s" % (qty, name))
        self.items[name] -= qty
        if self.items[name] == 0:
            del self.items[name]
'''})


LANG_NAMES = {"python": "Python", "javascript": "JavaScript", "typescript": "TypeScript", "c": "C", "cpp": "C++", "csharp": "C#", "java": "Java",
              "go": "Go", "rust": "Rust", "php": "PHP", "ruby": "Ruby", "perl": "Perl", "lua": "Lua", "bash": "Bash", "sql": "SQL",
              "reverse": "Reverse engineering"}


def load_all():
    import curriculum_lang
    curriculum_lang.register()


def get(task_id):
    return next((t for t in TASKS if t["id"] == task_id), None)


load_all()
