import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .config import settings
from .models import CheckResult, Website


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                expected_url TEXT NOT NULL,
                expected_status_code INTEGER NOT NULL DEFAULT 200,
                expected_final_url TEXT,
                expected_text TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                allow_scheme_mismatch INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                website_id INTEGER NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL,
                http_status_code INTEGER,
                expected_url TEXT NOT NULL,
                actual_url TEXT,
                response_time_ms REAL,
                error_message TEXT,
                dns_ok INTEGER NOT NULL,
                connection_ok INTEGER NOT NULL,
                redirect_chain TEXT NOT NULL DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS idx_results_website_checked
                ON check_results(website_id, checked_at DESC);
            """
        )


def seed_from_csv(csv_path: Path) -> None:
    import csv

    with connect() as db:
        if db.execute("SELECT COUNT(*) FROM websites").fetchone()[0]:
            return
        if not csv_path.exists():
            return
        with csv_path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                db.execute(
                    """INSERT INTO websites
                    (name, expected_url, expected_status_code, expected_final_url,
                     expected_text, enabled, allow_scheme_mismatch)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["name"].strip(),
                        row["expected_url"].strip(),
                        int(row.get("expected_status_code") or 200),
                        row.get("expected_final_url", "").strip() or None,
                        row.get("expected_text", "").strip() or None,
                        int(row.get("enabled", "true").lower() in {"true", "1", "yes"}),
                        int(row.get("allow_scheme_mismatch", "false").lower() in {"true", "1", "yes"}),
                    ),
                )


def list_websites() -> list[Website]:
    with connect() as db:
        return [Website.from_row(row) for row in db.execute("SELECT * FROM websites ORDER BY name COLLATE NOCASE")]


def get_website(website_id: int) -> Optional[Website]:
    with connect() as db:
        row = db.execute("SELECT * FROM websites WHERE id = ?", (website_id,)).fetchone()
        return Website.from_row(row) if row else None


def create_website(values: dict) -> Website:
    return create_websites([values])[0]


def create_websites(values_list: list[dict]) -> list[Website]:
    created = []
    with connect() as db:
        for values in values_list:
            cursor = db.execute(
                """INSERT INTO websites
                (name, expected_url, expected_status_code, expected_final_url, expected_text,
                 enabled, allow_scheme_mismatch)
                VALUES (:name, :expected_url, :expected_status_code, :expected_final_url, :expected_text,
                 :enabled, :allow_scheme_mismatch)""",
                {**values, "enabled": int(values["enabled"]), "allow_scheme_mismatch": int(values["allow_scheme_mismatch"])},
            )
            row = db.execute("SELECT * FROM websites WHERE id = ?", (cursor.lastrowid,)).fetchone()
            created.append(Website.from_row(row))
    return created


def update_website(website_id: int, values: dict) -> Optional[Website]:
    with connect() as db:
        db.execute(
            """UPDATE websites SET name = :name, expected_url = :expected_url,
            expected_status_code = :expected_status_code, expected_final_url = :expected_final_url,
            expected_text = :expected_text, enabled = :enabled,
            allow_scheme_mismatch = :allow_scheme_mismatch, updated_at = CURRENT_TIMESTAMP
            WHERE id = :id""",
            {
                **values,
                "id": website_id,
                "enabled": int(values["enabled"]),
                "allow_scheme_mismatch": int(values["allow_scheme_mismatch"]),
            },
        )
        row = db.execute("SELECT * FROM websites WHERE id = ?", (website_id,)).fetchone()
        return Website.from_row(row) if row else None


def delete_website(website_id: int) -> bool:
    with connect() as db:
        cursor = db.execute("DELETE FROM websites WHERE id = ?", (website_id,))
        return cursor.rowcount > 0


def save_results(results: list[CheckResult]) -> None:
    with connect() as db:
        db.executemany(
            """INSERT INTO check_results
            (website_id, checked_at, status, http_status_code, expected_url, actual_url,
             response_time_ms, error_message, dns_ok, connection_ok, redirect_chain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    result.website_id,
                    result.checked_at,
                    result.status,
                    result.http_status_code,
                    result.expected_url,
                    result.actual_url,
                    result.response_time_ms,
                    result.error_message,
                    int(result.dns_ok),
                    int(result.connection_ok),
                    json.dumps(result.redirect_chain),
                )
                for result in results
            ],
        )


def latest_results() -> dict[int, dict]:
    with connect() as db:
        rows = db.execute(
            """SELECT r.* FROM check_results r
            JOIN (SELECT website_id, MAX(id) AS latest_id FROM check_results GROUP BY website_id) latest
            ON latest.latest_id = r.id"""
        )
        return {row["website_id"]: result_from_row(row) for row in rows}


def get_history(website_id: int, limit: int = 500) -> list[dict]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM check_results WHERE website_id = ? ORDER BY id DESC LIMIT ?",
            (website_id, limit),
        )
        return [result_from_row(row) for row in reversed(list(rows))]


def last_check_by_status(website_id: int, status: str) -> Optional[str]:
    with connect() as db:
        row = db.execute(
            "SELECT checked_at FROM check_results WHERE website_id = ? AND status = ? ORDER BY id DESC LIMIT 1",
            (website_id, status),
        ).fetchone()
        return row["checked_at"] if row else None


def result_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "website_id": row["website_id"],
        "checked_at": row["checked_at"],
        "status": row["status"],
        "http_status_code": row["http_status_code"],
        "expected_url": row["expected_url"],
        "actual_url": row["actual_url"],
        "response_time_ms": row["response_time_ms"],
        "error_message": row["error_message"],
        "dns_ok": bool(row["dns_ok"]),
        "connection_ok": bool(row["connection_ok"]),
        "redirect_chain": json.loads(row["redirect_chain"]),
    }