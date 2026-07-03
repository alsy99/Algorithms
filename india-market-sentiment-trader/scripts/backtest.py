#!/usr/bin/env python3
"""Replay stored sentiment + price snapshots for threshold tuning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest sentiment trading thresholds")
    parser.add_argument("--data", type=Path, default=Path("data/backtest_sample.json"))
    args = parser.parse_args()

    if not args.data.exists():
        print(f"No backtest data at {args.data}. Run the bot to collect TimescaleDB exports first.")
        return

    rows = json.loads(args.data.read_text(encoding="utf-8"))
    wins = 0
    total = 0
    for row in rows:
        sentiment = row.get("sentiment", 0)
        momentum = row.get("momentum", 0)
        pnl = row.get("pnl", 0)
        if sentiment > 0.35 and momentum > 0:
            total += 1
            if pnl > 0:
                wins += 1
    hit_rate = (wins / total * 100) if total else 0.0
    print(f"Signals: {total}, wins: {wins}, hit rate: {hit_rate:.1f}%")


if __name__ == "__main__":
    main()
