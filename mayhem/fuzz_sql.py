#!/usr/bin/env python3
# Port of OSS-Fuzz's projects/psycopg2/fuzz_sql.py: psycopg2.sql composition under atheris.
import sys

import atheris

sys.path[:0] = ["/mayhem/build/oracle/lib"]
with atheris.instrument_imports(include=["psycopg2"]):
    from psycopg2 import sql


def TestInput(data):
    fdp = atheris.FuzzedDataProvider(data)

    try:
        # Create an SQL statement and perform a set of operations on it.
        query = sql.SQL(fdp.ConsumeString(100))
        i1 = sql.Identifier(fdp.ConsumeString(25))
        i2 = sql.Identifier(fdp.ConsumeString(25))
        i3 = sql.Identifier(fdp.ConsumeString(25))
        i4 = sql.Identifier(fdp.ConsumeString(25))
        i5 = sql.Identifier(fdp.ConsumeString(25))
        q1 = sql.SQL(fdp.ConsumeString(100))
        q1.join([i1, i2])
        query.format(q1, i3, i4)
        sql.Composed([query, i5])
    except (AttributeError, TypeError, ValueError, KeyError, IndexError):
        pass


def main():
    atheris.Setup(sys.argv, TestInput, enable_python_coverage=True)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
