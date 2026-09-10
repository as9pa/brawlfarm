"""Fail if the repo contains a legacy account identifier or a Discord import.

The identifiers themselves never appear here: the check compares SHA-256 hashes of
lowercase tokens against a fixed set, so publishing this file reveals nothing.
Run: uv run python tools/scrub_check.py  (exit 1 on any hit)
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

# sha256 of lowercase tokens: three legacy player tags (with and without the leading
# '#'), three legacy account nicknames, and the legacy machine's user name.
FORBIDDEN_SHA256: frozenset[str] = frozenset(
    {
        "e571ad0b63e2aff44a1557adabe80093cdc3d3e3d6ca45dc25abdc58ecf688af",
        "6a51aa76773df41d7dc0ba5a4b37f4a567b363d9be317edbd21b2bbfe02f6ec8",
        "9bd320a413eed31d21577f0e3b8f904547bf155468b6b791b70c8c2430dad392",
        "8e81eaa8a6719ec6cc1cc39ab93bfd8b391d1d9011b5e7ac54a8525e090bb330",
        "a64654a48b4cb2c8d5e45dfcb2df116a0089a932a6593c0818f7aeff64b4d3b4",
        "9e4807c28c77922e03edb58914dd2e258aa8bd817ca08c31db83a8269d416d87",
        "16d1551686f4cb08f88335d39d505708f5618bd8762c62fba9f9d1d3f3bdb850",
        "7fb26a8732f70c7392214b9056c2cd60f5b2d8a6e64d2356ae396297fd750b4a",
        "bc98bb50e8094b2ac3ceb90ba2512587c0513cd294a07efcfdcf467198da6266",
        "7764735c5d4d88ae3ef1c0d6c0a5769e4187c341895db19a82ba7d4e17b8c914",
    }
)

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".txt",
    ".json",
    ".ps1",
    ".cfg",
    ".ini",
    ".html",
    ".css",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".csv",
    ".env",
    ".example",
}
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".worktrees",
}
TOKEN_RE = re.compile(r"#?[A-Za-z0-9]+")
DISCORD_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+discord\b")


def _hash(token: str) -> str:
    return hashlib.sha256(token.lower().encode()).hexdigest()


def _tracked_files(root: Path) -> list[Path]:
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        files = [root / p for p in out.split("\0") if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = [p for p in root.rglob("*") if p.is_file()]
    return [
        p for p in files if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS)
    ]


def scan(root: Path, extra_hashes: frozenset[str] = frozenset()) -> list[str]:
    forbidden = FORBIDDEN_SHA256 | extra_hashes
    hits: list[str] = []
    for path in sorted(_tracked_files(root)):
        rel = path.relative_to(root).as_posix()
        if any(_hash(t) in forbidden for t in TOKEN_RE.findall(path.name)):
            hits.append(f"{rel}:0: forbidden identifier in filename")
        if (path.suffix.lower() or path.name.lower()) not in TEXT_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            if any(_hash(t) in forbidden for t in TOKEN_RE.findall(line)):
                hits.append(f"{rel}:{n}: forbidden identifier")
            if path.suffix == ".py" and DISCORD_IMPORT_RE.match(line):
                hits.append(f"{rel}:{n}: discord import")
    return hits


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(__file__).resolve().parents[1]
    hits = scan(root)
    for h in hits:
        print(h)
    print(f"scrub check: {len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
