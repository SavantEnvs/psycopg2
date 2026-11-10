"""Python side of the embedded-CPython libFuzzer harnesses (mayhem/fuzz_embed.c).

Each entry point takes the raw fuzz input as bytes. Errors psycopg2 reports through the Python API
(any Exception except SystemError, which flags a C function that failed without setting an error)
are normal outcomes of malformed input; memory and UB bugs in psycopg/*.c surface through ASan/UBSan.
"""
import datetime
import decimal
import pickle
import struct

import psycopg2
import psycopg2.errors
import psycopg2.extensions as ext
import psycopg2.extras

# Typecasters need a cursor, and the cursor a connection object, both run through their real
# __init__ (connection_setup creates string_types/binary_types, cursor_setup sets cursor->conn and
# tzinfo_factory). No PostgreSQL server is involved: connecting to a nonexistent unix-socket
# directory fails at once, after connection_setup has built the object's state. The cursor is shared
# across inputs; the casters only swap and restore its `caster` field, so it carries no state.
_conn = ext.connection.__new__(ext.connection, "")
try:
    _conn.__init__("host=/nonexistent-psycopg2-fuzz dbname=fuzz")
except psycopg2.OperationalError:
    pass
else:
    raise RuntimeError("unexpectedly connected to a PostgreSQL server")
assert isinstance(_conn.string_types, dict)
_cur = ext.cursor(_conn)

_casters = []
for _t in (list(ext.string_types.values()) + [
        ext.PYDATE, ext.PYTIME, ext.PYDATETIME, ext.PYDATETIMETZ, ext.PYINTERVAL,
        ext.UNICODE, ext.BYTES, ext.PYDATEARRAY, ext.PYTIMEARRAY, ext.PYDATETIMEARRAY,
        ext.PYDATETIMETZARRAY, ext.PYINTERVALARRAY, ext.UNICODEARRAY, ext.BYTESARRAY]):
    if _t not in _casters:
        _casters.append(_t)
# Array casters over every element caster, as register_type(new_array_type(...)) builds them.
for _t in list(_casters):
    if not _t.name.endswith("ARRAY"):
        _casters.append(ext.new_array_type((0xFFFF,), "A" + str(_t.name), _t))


def typecast(data):
    if not data:
        return 0
    caster = _casters[data[0] % len(_casters)]
    try:
        caster(data[1:], _cur)
    except SystemError:
        raise
    except Exception:
        pass
    return 0


def _text(b):
    return b.decode("utf-8", "replace")


def _values(b):
    """Decode b into a list of Python objects of the kinds psycopg2 adapts."""
    out = []
    i = 0
    while i < len(b) and len(out) < 8:
        kind = b[i] % 10
        n = b[i + 1] % 16 if i + 1 < len(b) else 0
        chunk = b[i + 2:i + 2 + n]
        i += 2 + n
        if kind == 0:
            out.append(None)
        elif kind == 1:
            out.append(int.from_bytes(chunk, "little", signed=True))
        elif kind == 2:
            out.append(struct.unpack("<d", chunk.ljust(8, b"\0")[:8])[0])
        elif kind == 3:
            out.append(_text(chunk))
        elif kind == 4:
            out.append(bytes(chunk))
        elif kind == 5:
            out.append(decimal.Decimal(_text(chunk)))
        elif kind == 6:
            out.append(bool(chunk[:1] and chunk[0] & 1))
        elif kind == 7:
            out.append(_values(chunk))
        elif kind == 8:
            out.append(tuple(_values(chunk)))
        else:
            out.append(memoryview(bytes(chunk)))
    return out


def _op_qstring(p):
    q = ext.QuotedString(_text(p))
    q.getquoted()
    q = ext.QuotedString(bytes(p))
    q.encoding = "utf-8"
    q.getquoted()


def _op_binary(p):
    ext.Binary(p).getquoted()
    ext.Binary(bytearray(p)).getquoted()


def _op_dsn(p):
    s = _text(p)
    d = ext.parse_dsn(s)
    ext.make_dsn(s)
    ext.make_dsn(s, **{k: v for k, v in d.items() if k != "password"})


def _op_xid(p):
    x = ext.Xid.from_string(_text(p))
    str(x), repr(x), len(x), tuple(x)
    ext.Xid(1, _text(p[:8]), _text(p[8:]))


def _op_adapt(p):
    for v in _values(p):
        ext.adapt(v).getquoted()
    ext.adapt(_values(p)).getquoted()


def _op_numbers(p):
    d = decimal.Decimal(_text(p))
    ext.adapt(d).getquoted()
    ext.adapt(float(_text(p))).getquoted()
    ext.adapt(int(_text(p), 0)).getquoted()


def _op_datetime(p):
    a = struct.unpack("<7i", p.ljust(28, b"\0")[:28])
    for f in (
            lambda: datetime.date(a[0], a[1], a[2]),
            lambda: datetime.time(a[3], a[4], a[5], a[6]),
            lambda: datetime.datetime(a[0], a[1], a[2], a[3], a[4], a[5], a[6]),
            lambda: datetime.datetime(a[0], a[1], a[2], tzinfo=datetime.timezone(
                datetime.timedelta(minutes=a[3]))),
            lambda: datetime.timedelta(a[0], a[1], a[2]),
            lambda: datetime.timedelta(days=a[0], microseconds=a[1] * a[2])):
        try:
            v = f()
        except (ValueError, OverflowError):
            continue
        ext.adapt(v).getquoted()


def _op_column(p):
    f = [_text(p[i:i + 2]) if i < 2 else (p[i] if i < len(p) else None) for i in range(9)]
    c = ext.Column(*f)
    repr(c)
    len(c)
    c == c
    for i in range(len(c)):
        c[i]
    c.name, c.type_code, c.table_oid
    pickle.loads(pickle.dumps(c))
    ext.Column(name=_text(p), type_code=len(p))


def _op_extras(p):
    s = _text(p)
    psycopg2.extras.Inet(s).getquoted()
    psycopg2.extras.Json({"k": s, "b": s[:4]}).getquoted()
    psycopg2.extras.HstoreAdapter.parse(s, _cur)
    psycopg2.extras.NumericRange(len(p), len(s)).lower
    psycopg2.errors.lookup(s)
    ext.Notify(len(p), s, s[::-1]) == ext.Notify(len(p), s, s)
    psycopg2.Error(s).pgerror


_ops = [_op_qstring, _op_binary, _op_dsn, _op_xid, _op_adapt, _op_numbers, _op_datetime,
        _op_column, _op_extras]


def adapt(data):
    if not data:
        return 0
    try:
        _ops[data[0] % len(_ops)](data[1:])
    except SystemError:
        raise
    except Exception:
        pass
    return 0
