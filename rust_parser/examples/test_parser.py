"""Run after `maturin develop --release` from rust_parser/.

Usage:
  python examples/test_parser.py /path/to/chat.txt
  python examples/test_parser.py /path/to/archive.zip
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import whatsapp_parser


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python examples/test_parser.py <txt|zip|rar>")
        raise SystemExit(1)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"File does not exist: {target}")
        raise SystemExit(1)

    if target.suffix.lower() in {".zip", ".rar"}:
        rows = whatsapp_parser.parse_zip(str(target))
    else:
        rows = whatsapp_parser.parse_file(str(target))

    print(f"Parser version: {whatsapp_parser.get_parser_version()}")
    print(f"Parsed rows: {len(rows)}")
    for idx, row in enumerate(rows[:5], start=1):
        print(f"--- row {idx} ---")
        print(json.dumps(row.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
