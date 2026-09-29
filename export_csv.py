from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def export_session(session_dir: Path) -> list[Path]:
    workers_dir = session_dir / "workers"
    output_dir = session_dir / "csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    exported: list[Path] = []
    for database in sorted(workers_dir.glob("worker_*.sqlite3")):
        target = output_dir / f"{database.stem}.csv"
        export_database(database, target)
        exported.append(target)

    return exported


def export_database(database: Path, target: Path) -> None:
    connection = sqlite3.connect(database)
    try:
        cursor = connection.execute(
            """
            SELECT
                frame_index, worker_id, worker_seed, frame_seed,
                width, height, timestamp_ns, threshold_mode, top_percent,
                mvp_score, mvp_threshold, mvp_passed, mvp_metrics_json,
                robust_score, robust_threshold, robust_passed,
                robust_metrics_json
            FROM frames
            ORDER BY frame_index
            """
        )
        columns = [item[0] for item in cursor.description]

        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            writer.writerows(cursor)
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export all worker SQLite logs in one experiment to CSV."
    )
    parser.add_argument("session_dir", type=Path)
    args = parser.parse_args()

    exported = export_session(args.session_dir)
    if not exported:
        raise SystemExit("No worker SQLite databases found.")

    for path in exported:
        print(path)


if __name__ == "__main__":
    main()
