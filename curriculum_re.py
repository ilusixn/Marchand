import base64
import json
import struct
import zlib


def _save(name, version, score, items):
    b = b"SAV1" + struct.pack("<H", version) + bytes([len(name)]) + name.encode() + struct.pack("<I", score) + bytes([len(items)])
    for i, q in items:
        b += struct.pack("<HB", i, q)
    return b


MYSTERY_ASM = '''; Compiled with gcc -O1 (Intel syntax, x86-64 System V). Argument n arrives in EDI, result is returned in EAX.
mystery:
        test    edi, edi
        je      .L4
        mov     eax, 0
.L3:
        add     eax, eax
        mov     edx, edi
        and     edx, 1
        or      eax, edx
        shr     edi
        jne     .L3
        ret
.L4:
        mov     eax, edi
        ret
'''

OPCODES = {0x01: ("PUSH", 1), 0x02: ("ADD", 0), 0x03: ("MUL", 0), 0x04: ("PRINT", 0), 0x05: ("JNZ", 1), 0x06: ("DUP", 0), 0x07: ("DEC", 0), 0x08: ("POP", 0), 0xFF: ("HALT", 0)}

VM_SOURCE = '''"""A tiny stack machine used by an old embedded tool (reference implementation)."""

# opcode -> (name, operand bytes)
OPCODES = {
    0x01: ("PUSH", 1),   # push the 1-byte operand
    0x02: ("ADD", 0),    # pop b, pop a, push a+b
    0x03: ("MUL", 0),    # pop b, pop a, push a*b
    0x04: ("PRINT", 0),  # pop and print
    0x05: ("JNZ", 1),    # pop; if non-zero jump to the absolute address in the operand
    0x06: ("DUP", 0),    # duplicate the top of the stack
    0x07: ("DEC", 0),    # pop a, push a-1
    0x08: ("POP", 0),    # discard the top
    0xFF: ("HALT", 0),
}


def run(code):
    stack, out, pc = [], [], 0
    while pc < len(code):
        op = code[pc]
        name, size = OPCODES[op]
        arg = code[pc + 1] if size else None
        pc += 1 + size
        if name == "PUSH": stack.append(arg)
        elif name == "ADD": b, a = stack.pop(), stack.pop(); stack.append(a + b)
        elif name == "MUL": b, a = stack.pop(), stack.pop(); stack.append(a * b)
        elif name == "PRINT": out.append(stack.pop())
        elif name == "JNZ":
            if stack.pop(): pc = arg
        elif name == "DUP": stack.append(stack[-1])
        elif name == "DEC": stack.append(stack.pop() - 1)
        elif name == "POP": stack.pop()
        elif name == "HALT": break
    return out
'''

PROGRAM = bytes([0x01, 5, 0x06, 0x04, 0x07, 0x06, 0x05, 2, 0x08, 0xFF])


def register_re():
    import curriculum
    task = curriculum.task

    # -------------------------------------------------- 1. unknown binary file format
    sample_a = _save("Zed", 3, 123456, [(7, 2), (300, 9)])
    sample_b = _save("Mira", 1, 42, [])
    task("re_file_format", "Work out an unknown save-file format", "reverse engineering", 3,
         "NOTES.txt describes two sample save files from an old game (hex dumps in sample_a.hex and sample_b.hex, with what they contain). Work out the binary format and implement parse(data: bytes) -> dict in reader.py so that test_reader.py passes. It must work for any file of this format, not just the samples.",
         {"NOTES.txt": '''Two save files from an old game, as hex (files sample_a.hex, sample_b.hex).

sample_a: player "Zed", game version 3, score 123456, inventory: item 7 x2, item 300 x9
sample_b: player "Mira", game version 1, score 42, empty inventory

parse(data) must return a dict:  {"name": str, "version": int, "score": int, "items": [(item_id, quantity), ...]}
Raise ValueError for data that is not this format.
''', "sample_a.hex": sample_a.hex() + "\n", "sample_b.hex": sample_b.hex() + "\n", "reader.py": '''def parse(data):
    raise NotImplementedError
'''},
         {"test_reader.py": '''import struct

from reader import parse


def build(name, version, score, items):
    b = b"SAV1" + struct.pack("<H", version) + bytes([len(name)]) + name.encode() + struct.pack("<I", score) + bytes([len(items)])
    for i, q in items:
        b += struct.pack("<HB", i, q)
    return b


a = parse(bytes.fromhex(open("sample_a.hex").read().strip()))
assert a == {"name": "Zed", "version": 3, "score": 123456, "items": [(7, 2), (300, 9)]}, a
b = parse(bytes.fromhex(open("sample_b.hex").read().strip()))
assert b == {"name": "Mira", "version": 1, "score": 42, "items": []}, b
c = parse(build("Alexandria-the-Great", 258, 4000000000, [(65535, 255), (1, 1), (256, 2)]))
assert c == {"name": "Alexandria-the-Great", "version": 258, "score": 4000000000, "items": [(65535, 255), (1, 1), (256, 2)]}, c
for bad in (b"", b"XXXX" + b"\\0" * 20, build("A", 1, 1, [(1, 1)])[:-1]):
    try:
        parse(bad)
        raise SystemExit("must reject bad data")
    except ValueError:
        pass
print("OK")
'''},
         {"reader.py": '''import struct


def parse(data):
    try:
        if data[:4] != b"SAV1":
            raise ValueError("bad magic")
        version, = struct.unpack_from("<H", data, 4)
        name_len = data[6]
        name = data[7:7 + name_len].decode()
        if len(data[7:7 + name_len]) != name_len:
            raise ValueError("truncated name")
        pos = 7 + name_len
        score, = struct.unpack_from("<I", data, pos)
        count = data[pos + 4]
        pos += 5
        items = []
        for _ in range(count):
            item_id, qty = struct.unpack_from("<HB", data, pos)
            items.append((item_id, qty))
            pos += 3
        return {"name": name, "version": version, "score": score, "items": items}
    except (struct.error, IndexError, UnicodeDecodeError) as ex:
        raise ValueError("malformed save file: %s" % ex)
'''}, lang="reverse")

    # -------------------------------------------------- 2. assembly to code
    task("re_asm_to_python", "Read assembly and rewrite it", "reverse engineering", 3,
         "mystery.s is the compiler output (x86-64, Intel syntax) of a small C function. Read it, work out what it computes, and write the same function in Python: mystery(n) in mystery.py, for unsigned 32-bit n. Make test_mystery.py pass.",
         {"mystery.s": MYSTERY_ASM, "mystery.py": '''def mystery(n):
    raise NotImplementedError
'''},
         {"test_mystery.py": '''from mystery import mystery


def reference(n):
    r = 0
    while n:
        r = ((r << 1) | (n & 1)) & 0xFFFFFFFF
        n >>= 1
    return r


for n in list(range(0, 2000)) + [2 ** 31, 2 ** 32 - 1, 123456789, 0x80000001, 255, 256]:
    assert mystery(n) == reference(n), (n, mystery(n), reference(n))
print("OK")
'''},
         {"mystery.py": '''def mystery(n):
    r = 0
    while n:
        r = ((r << 1) | (n & 1)) & 0xFFFFFFFF
        n >>= 1
    return r
'''}, lang="reverse")

    # -------------------------------------------------- 3. deobfuscate javascript
    obf = '''var _0x4f2a=['split','reverse','join','toUpperCase','charCodeAt','fromCharCode','map'];
function _0x1b(_0x3c){return _0x3c[_0x4f2a[0]]('')[_0x4f2a[1]]()[_0x4f2a[2]]('')[_0x4f2a[3]]();}
function _0x2d(_0x5e){return _0x5e[_0x4f2a[0]]('')[_0x4f2a[6]](function(_0x6f){var _0x7a=_0x6f[_0x4f2a[4]](0);if(_0x7a>=97&&_0x7a<=122){return String[_0x4f2a[5]]((_0x7a-97+3)%26+97);}return _0x6f;})[_0x4f2a[2]]('');}
module.exports={f:_0x1b,g:_0x2d};
'''
    task("re_deobfuscate_js", "Deobfuscate a JavaScript file", "reverse engineering", 3,
         "obfuscated.js is machine-obfuscated JavaScript with two exported functions (f and g). Work out what each one does and write clean, readable versions in clean.js, exported as reverseUpper and shift, that behave identically. Make test.js pass.",
         {"obfuscated.js": obf, "clean.js": '''module.exports = {
  reverseUpper() { throw new Error("todo"); },
  shift() { throw new Error("todo"); },
};
'''},
         {"test.js": '''const assert = require("assert");
const orig = require("./obfuscated");
const clean = require("./clean");

const samples = ["hello world", "Reverse Engineering", "", "xyz abc", "MiXeD 123 case!", "a"];
for (const s of samples) {
  assert.strictEqual(clean.reverseUpper(s), orig.f(s), "reverseUpper(" + JSON.stringify(s) + ")");
  assert.strictEqual(clean.shift(s), orig.g(s), "shift(" + JSON.stringify(s) + ")");
}
assert.ok(!/_0x/.test(require("fs").readFileSync("clean.js", "utf8")), "clean.js must not keep obfuscated names");
console.log("OK");
'''},
         {"clean.js": '''function reverseUpper(text) {
  return text.split("").reverse().join("").toUpperCase();
}

function shift(text) {
  return text
    .split("")
    .map((ch) => {
      const code = ch.charCodeAt(0);
      if (code >= 97 && code <= 122) return String.fromCharCode(((code - 97 + 3) % 26) + 97);
      return ch;
    })
    .join("");
}

module.exports = { reverseUpper, shift };
'''}, test_cmd="node test.js", lang="reverse", requires=["node"])

    # -------------------------------------------------- 4. known plaintext
    def xor(data, key):
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    plain = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nthe quick brown fox jumps over the lazy dog"
    task("re_known_plaintext", "Recover a repeating XOR key", "reverse engineering", 3,
         "intercepted.hex is a captured server response that was XOR-encrypted with a short repeating key. All responses from this server start with the text \"HTTP/1.1 200 OK\\r\\n\". Use that known plaintext to recover the key and implement decode(data: bytes) -> bytes in decode.py so it works for responses encrypted with any key of up to 8 bytes. Make test_decode.py pass.",
         {"intercepted.hex": xor(plain, b"k3y!").hex() + "\n", "decode.py": '''def decode(data):
    raise NotImplementedError
'''},
         {"test_decode.py": '''from decode import decode


def xor(data, key):
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


HEADER = b"HTTP/1.1 200 OK\\r\\n"
bodies = [b"HTTP/1.1 200 OK\\r\\nContent-Type: text/plain\\r\\n\\r\\nhello there, this is a longer body so every key byte is used",
          b"HTTP/1.1 200 OK\\r\\n\\r\\n{\\"a\\": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}"]
for key in (b"k3y!", b"A", b"secret", b"\\x00\\xff\\x10", b"12345678"):
    for body in bodies:
        assert decode(xor(body, key)) == body, (key, body)
cap = bytes.fromhex(open("intercepted.hex").read().strip())
assert decode(cap).startswith(HEADER)
print("OK")
'''},
         {"decode.py": '''def decode(data):
    known = b"HTTP/1.1 200 OK\\r\\n"
    stream = bytes(d ^ k for d, k in zip(data, known))
    for size in range(1, 9):
        key = stream[:size]
        if all(stream[i] == key[i % size] for i in range(len(stream))):
            return bytes(b ^ key[i % size] for i, b in enumerate(data))
    raise ValueError("could not recover a key of up to 8 bytes")
'''}, lang="reverse")

    # -------------------------------------------------- 5. black box oracle
    def secret(x):
        return (x * x * 3 + 7) % 1000
    samples = "\n".join("f(%d) = %d" % (x, secret(x)) for x in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 20, 31, 50, 99, 100, 123, 250, 333, 500, 999, 1234))
    task("re_black_box", "Infer a hidden function from its outputs", "reverse engineering", 3,
         "oracle_samples.txt lists inputs and outputs of a hidden function f that takes a non-negative integer. Study the numbers, form a hypothesis about its formula, check it against every sample, and implement f(x) in guess.py so test_guess.py passes (the test checks many more inputs).",
         {"oracle_samples.txt": samples + "\n", "guess.py": '''def f(x):
    raise NotImplementedError
'''},
         {"test_guess.py": '''from guess import f

for x in list(range(0, 3000)) + [10 ** 6, 123456789]:
    assert f(x) == (x * x * 3 + 7) % 1000, (x, f(x))
print("OK")
'''},
         {"guess.py": '''def f(x):
    return (x * x * 3 + 7) % 1000
'''}, lang="reverse")

    # -------------------------------------------------- 6. layered encoding
    def wrap(obj, layers):
        data = json.dumps(obj).encode()
        for layer in layers:
            data = {"b64": base64.b64encode, "zlib": zlib.compress, "hex": lambda d: d.hex().encode()}[layer](data)
        return data.decode()
    payload = wrap({"user": "ann", "role": "admin", "n": 7}, ["b64", "zlib", "hex"])
    task("re_layers", "Peel layered encodings", "reverse engineering", 3,
         "payload.txt is a message that was encoded in several layers (the encodings are common ones). Work out the layers and implement unwrap(text) -> dict in unwrap.py. It should detect the layers automatically, because other messages may use a different number or order of layers. Make test_unwrap.py pass.",
         {"payload.txt": payload + "\n", "unwrap.py": '''def unwrap(text):
    raise NotImplementedError
'''},
         {"test_unwrap.py": '''import base64
import json
import zlib

from unwrap import unwrap


def wrap(obj, layers):
    data = json.dumps(obj).encode()
    for layer in layers:
        data = {"b64": base64.b64encode, "zlib": zlib.compress, "hex": lambda d: d.hex().encode()}[layer](data)
    return data.decode()


assert unwrap(open("payload.txt").read().strip()) == {"user": "ann", "role": "admin", "n": 7}
obj = {"k": [1, 2, 3], "s": "text", "z": None}
for layers in (["b64"], ["hex"], ["zlib", "b64"], ["b64", "b64", "hex"], ["hex", "zlib", "b64", "hex"], []):
    assert unwrap(wrap(obj, layers)) == obj, layers
try:
    unwrap("this is not any known encoding!!")
    raise SystemExit("must reject unknown data")
except ValueError:
    pass
print("OK")
'''},
         {"unwrap.py": '''import base64
import binascii
import json
import zlib


def unwrap(text):
    data = text.strip().encode() if isinstance(text, str) else text
    for _ in range(20):
        try:
            return json.loads(data.decode())
        except (ValueError, UnicodeDecodeError):
            pass
        for decoder in (_hex, _base64, _zlib):
            out = decoder(data)
            if out is not None:
                data = out
                break
        else:
            raise ValueError("unknown encoding")
    raise ValueError("too many layers")


def _hex(data):
    try:
        return bytes.fromhex(data.decode())
    except (ValueError, UnicodeDecodeError):
        return None


def _base64(data):
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        return None


def _zlib(data):
    try:
        return zlib.decompress(data)
    except zlib.error:
        return None
'''}, lang="reverse")

    # -------------------------------------------------- 7. protocol capture
    def packet(ptype, payload):
        body = bytes([ptype, len(payload)]) + payload
        return b"\x02" + body + bytes([sum(body) % 256]) + b"\x03"
    cap = [("hello from device", packet(1, b"thermo-7")), ("reading while the room was 21.5 C", packet(2, struct.pack(">h", 215))),
           ("reading while the room was -4.0 C", packet(2, struct.pack(">h", -40))), ("server acknowledgement", packet(3, b"")),
           ("reading, 30.1 C", packet(2, struct.pack(">h", 301)))]
    cap_txt = "\n".join("# %s\n%s" % (note, pk.hex(" ")) for note, pk in cap) + "\n"
    task("re_protocol", "Decode a device protocol from a capture", "reverse engineering", 3,
         "capture.txt contains packets sent by a thermostat (hex bytes, each preceded by a comment saying what was happening). Work out the packet layout, including the checksum, and implement decode(packet: bytes) -> dict in proto.py so test_proto.py passes. Invalid packets (bad framing or checksum) must raise ValueError.",
         {"capture.txt": cap_txt, "proto.py": '''def decode(packet):
    raise NotImplementedError
'''},
         {"test_proto.py": '''import struct

from proto import decode


def packet(ptype, payload):
    body = bytes([ptype, len(payload)]) + payload
    return b"\\x02" + body + bytes([sum(body) % 256]) + b"\\x03"


lines = [l for l in open("capture.txt").read().splitlines() if l and not l.startswith("#")]
pk = [bytes.fromhex(l) for l in lines]
assert decode(pk[0]) == {"type": "hello", "device": "thermo-7"}, decode(pk[0])
assert decode(pk[1]) == {"type": "reading", "celsius": 21.5}
assert decode(pk[2]) == {"type": "reading", "celsius": -4.0}
assert decode(pk[3]) == {"type": "ack"}
assert decode(packet(2, struct.pack(">h", -273))) == {"type": "reading", "celsius": -27.3}
assert decode(packet(1, b"x" * 40)) == {"type": "hello", "device": "x" * 40}
good = packet(2, struct.pack(">h", 100))
for bad in (b"", good[:-1], b"\\x00" + good[1:], good[:-2] + bytes([(good[-2] + 1) % 256]) + b"\\x03", packet(9, b"zz")):
    try:
        decode(bad)
        raise SystemExit("must reject %r" % bad)
    except ValueError:
        pass
print("OK")
'''},
         {"proto.py": '''import struct


def decode(packet):
    if len(packet) < 5 or packet[0] != 0x02 or packet[-1] != 0x03:
        raise ValueError("bad framing")
    ptype, length = packet[1], packet[2]
    if len(packet) != length + 5:
        raise ValueError("bad length")
    body = packet[1:-2]
    if sum(body) % 256 != packet[-2]:
        raise ValueError("bad checksum")
    payload = packet[3:3 + length]
    if ptype == 1:
        return {"type": "hello", "device": payload.decode()}
    if ptype == 2:
        return {"type": "reading", "celsius": struct.unpack(">h", payload)[0] / 10}
    if ptype == 3:
        return {"type": "ack"}
    raise ValueError("unknown packet type %d" % ptype)
'''}, lang="reverse")

    # -------------------------------------------------- 8. unknown database
    task("re_unknown_db", "Explore an unknown database", "reverse engineering", 2,
         "dbinfo.py must describe any SQLite database file without knowing it in advance: describe(path) returns {table_name: {\"columns\": [(name, declared_type), ...], \"rows\": row_count}} for every user table (ignore sqlite_ internal tables). Use SQLite's own metadata (sqlite_master and PRAGMA). Make test_dbinfo.py pass.",
         {"dbinfo.py": '''def describe(path):
    raise NotImplementedError
'''},
         {"test_dbinfo.py": '''import os
import sqlite3
import tempfile

from dbinfo import describe

p = os.path.join(tempfile.mkdtemp(), "unknown.db")
db = sqlite3.connect(p)
db.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, score REAL);
CREATE TABLE "order items" (order_id INTEGER, sku TEXT, qty INTEGER DEFAULT 1);
CREATE TABLE empty_one (x BLOB);
CREATE INDEX idx_users_name ON users(name);
INSERT INTO users (name, score) VALUES ('a', 1.5), ('b', 2.5), ('c', NULL);
INSERT INTO "order items" VALUES (1, 'x', 2), (1, 'y', 3);
""")
db.commit()
db.close()
got = describe(p)
assert got == {"users": {"columns": [("id", "INTEGER"), ("name", "TEXT"), ("score", "REAL")], "rows": 3},
               "order items": {"columns": [("order_id", "INTEGER"), ("sku", "TEXT"), ("qty", "INTEGER")], "rows": 2},
               "empty_one": {"columns": [("x", "BLOB")], "rows": 0}}, got
print("OK")
'''},
         {"dbinfo.py": '''import sqlite3


def describe(path):
    db = sqlite3.connect(path)
    try:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
        out = {}
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            cols = [(c[1], c[2]) for c in db.execute("PRAGMA table_info(%s)" % quoted)]
            rows = db.execute("SELECT COUNT(*) FROM %s" % quoted).fetchone()[0]
            out[name] = {"columns": cols, "rows": rows}
        return out
    finally:
        db.close()
'''}, lang="reverse")

    # -------------------------------------------------- 9. bytecode disassembler
    task("re_bytecode", "Write a disassembler for a tiny VM", "reverse engineering", 3,
         "vm.py is the reference interpreter of a small stack machine, and program.hex is a program for it. Read the interpreter to learn the instruction set, then write disassemble(code: bytes) -> list[str] in disasm.py. Each line is the 4-digit hexadecimal address, a space, the mnemonic, and (when the instruction has an operand) a space and the operand in decimal, for example \"0000 PUSH 5\" or \"0003 PRINT\". Unknown opcodes must raise ValueError. Make test_disasm.py pass.",
         {"vm.py": VM_SOURCE, "program.hex": PROGRAM.hex() + "\n", "disasm.py": '''def disassemble(code):
    raise NotImplementedError
'''},
         {"test_disasm.py": '''from disasm import disassemble
from vm import run

prog = bytes.fromhex(open("program.hex").read().strip())
assert disassemble(prog) == ["0000 PUSH 5", "0002 DUP", "0003 PRINT", "0004 DEC", "0005 DUP", "0006 JNZ 2", "0008 POP", "0009 HALT"], disassemble(prog)
assert run(prog) == [5, 4, 3, 2, 1]
assert disassemble(bytes([0x01, 200, 0x01, 3, 0x03, 0x04, 0xFF])) == ["0000 PUSH 200", "0002 PUSH 3", "0004 MUL", "0005 PRINT", "0006 HALT"]
assert disassemble(b"") == []
for bad in (bytes([0x42]), bytes([0x01]), bytes([0x05])):
    try:
        disassemble(bad)
        raise SystemExit("must reject %r" % bad)
    except ValueError:
        pass
print("OK")
'''},
         {"disasm.py": '''from vm import OPCODES


def disassemble(code):
    lines, pc = [], 0
    while pc < len(code):
        op = code[pc]
        if op not in OPCODES:
            raise ValueError("unknown opcode 0x%02x at %d" % (op, pc))
        name, size = OPCODES[op]
        if size and pc + 1 >= len(code):
            raise ValueError("truncated instruction at %d" % pc)
        line = "%04x %s" % (pc, name)
        if size:
            line += " %d" % code[pc + 1]
        lines.append(line)
        pc += 1 + size
    return lines
'''}, lang="reverse")
