"""Sample CPU/RSS/threads for a running app process during a load test."""

import argparse
import csv
import time
from pathlib import Path

import psutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    process = psutil.Process(args.pid)
    process.cpu_percent(interval=None)
    started = time.perf_counter()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["elapsed_seconds", "cpu_percent", "rss_mb", "threads"])
        while time.perf_counter() - started < args.duration:
            elapsed = time.perf_counter() - started
            memory = process.memory_info()
            writer.writerow(
                [
                    round(elapsed, 2),
                    process.cpu_percent(interval=None),
                    round(memory.rss / (1024 * 1024), 1),
                    process.num_threads(),
                ]
            )
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
