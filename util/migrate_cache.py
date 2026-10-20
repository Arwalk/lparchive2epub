"""Rewrite the keys of an aiohttp-client-cache SQLite cache for the installed version of the library.

    uv run python util/migrate_cache.py CACHE.sqlite | DIR [--dry-run]

A directory stands for every *.sqlite file in it: the per-LP caches of an archive-wide run (OUTPUT_DIR/cache/<slug>.sqlite,
see all_archives.py).

aiohttp-client-cache 0.15 (2026-10-07) computes another key for the same request than 0.14 did (the parts are hashed
length-prefixed), so a cache written before the upgrade is never hit again: every page and picture downloaded once more
and stored a second time, the file twice the size (seen on 2026-10-20: 135 URLs, each stored twice). The rows themselves
are fine, the schema and the pickles are unchanged.

So this reads every stored response, takes the URL it was requested at (the first of its redirects when it had any, its
own otherwise), computes the key the installed library makes for that request, and rewrites the key in place; the
redirects table is rebuilt from the histories. A row the installed library would already find is left alone, so the
script can run twice; a row an identical request was stored under after the upgrade (fresher) wins over the old one,
which is dropped; a row that does not unpickle is kept and counted. One transaction per file: a crash leaves the file as
it was. The requests of lparchive2epub carry no parameters, body or key-relevant headers, so the method and the URL are
the whole key.
"""
import argparse
import os
import pickle
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp_client_cache.cache_keys import create_key


@dataclass
class Report:
    path: str
    rows: int = 0               # responses in the file
    current: int = 0            # already under the key the installed library makes
    rewritten: int = 0          # keys replaced
    dropped: int = 0            # older rows of a request also stored under the current key
    unreadable: int = 0         # rows that do not unpickle, kept
    redirects: int = 0          # redirect aliases rebuilt from the histories
    seconds: float = 0.0
    error: str | None = None
    unreadable_keys: list[str] = field(default_factory=list)

    def line(self) -> str:
        if self.error:
            return f"{self.path}: {self.error}"
        return (f"{self.path}: {self.rows} responses, {self.current} current, {self.rewritten} rewritten, "
                f"{self.dropped} dropped, {self.unreadable} unreadable, {self.redirects} redirects, {self.seconds:.1f}s")


def requested_url(response) -> str:
    """The URL a cached response was asked for: where its redirects started, else where it was answered."""
    return str(response.history[0].url if response.history else response.url)


def migrate(path: str, dry_run: bool = False) -> Report:
    report = Report(path)
    started = time.monotonic()
    con = sqlite3.connect(path)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"responses", "redirects"} <= tables:
            report.error = "not an aiohttp-client-cache SQLite cache (no responses and redirects tables)"
            return report
        new_keys: dict[str, str] = {}          # old key -> the key the installed library makes
        aliases: dict[str, str] = {}           # redirect key -> response key, rebuilt from every history
        owners: dict[str, str] = {}            # current key -> the stored key that will hold it
        drop: list[str] = []
        for key, value in con.execute("SELECT key, value FROM responses"):
            report.rows += 1
            try:
                response = pickle.loads(value)
                current = create_key(response.method, requested_url(response))
                history = [(create_key(r.method, str(r.url))) for r in response.history]
            except Exception:
                report.unreadable += 1
                report.unreadable_keys.append(key)
                continue
            if owners.get(current) == current:                  # the same request, stored after the upgrade: it wins
                drop.append(key)
                continue
            if current in owners:                               # the same request under two old keys, or this row
                drop.append(owners[current])                    # is the one stored after the upgrade
                new_keys.pop(owners[current], None)
            owners[current] = key
            if key == current:
                report.current += 1
            else:
                new_keys[key] = current
            for alias in history:
                aliases[alias] = current
        report.rewritten = len(new_keys)
        report.dropped = len(drop)
        report.redirects = len(aliases)
        if not dry_run:
            with con:
                con.executemany("DELETE FROM responses WHERE key = ?", [(k,) for k in drop])
                con.executemany("UPDATE responses SET key = ? WHERE key = ?", [(new, old) for old, new in new_keys.items()])
                con.execute("DELETE FROM redirects")
                con.executemany("INSERT INTO redirects (key, value) VALUES (?, ?)", list(aliases.items()))
            if drop:
                con.execute("VACUUM")
    except sqlite3.Error as e:
        report.error = f"sqlite: {e}"
    finally:
        con.close()
        report.seconds = time.monotonic() - started
    return report


def cache_files(target: str) -> list[str]:
    if os.path.isdir(target):
        return sorted(str(p) for p in Path(target).glob("*.sqlite"))
    return [target]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rewrite the keys of aiohttp-client-cache SQLite caches for the installed "
                                                 "version of the library (0.15 keys differ from 0.14's)")
    parser.add_argument("target", metavar="CACHE.sqlite|DIR", help="one cache, or a directory of *.sqlite caches")
    parser.add_argument("--dry-run", action="store_true", help="count what would change, write nothing")
    args = parser.parse_args(argv)
    files = cache_files(args.target)
    if not files:
        print(f"no *.sqlite file in {args.target}", file=sys.stderr)
        return 2
    failed = 0
    totals = Report("total")
    for path in files:
        report = migrate(path, dry_run=args.dry_run)
        print(report.line(), file=sys.stderr)
        if report.error:
            failed += 1
            continue
        for name in ("rows", "current", "rewritten", "dropped", "unreadable", "redirects", "seconds"):
            setattr(totals, name, getattr(totals, name) + getattr(report, name))
    if len(files) > 1:
        print(("would be: " if args.dry_run else "") + totals.line() + f", {failed} file(s) failed", file=sys.stderr)
    elif args.dry_run:
        print("(dry run: nothing written)", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
