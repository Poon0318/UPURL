import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / "backend" / ".env")


def database_path() -> Path:
    value = Path(os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "monitor.db")))
    return value if value.is_absolute() else PROJECT_ROOT / value


@dataclass(frozen=True)
class Settings:
    database_path: Path = database_path()
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    )
    check_interval_seconds: int = max(10, int(os.getenv("CHECK_INTERVAL_SECONDS", "60")))
    request_timeout_seconds: float = max(1.0, float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12")))
    max_concurrent_checks: int = min(100, max(1, int(os.getenv("MAX_CONCURRENT_CHECKS", "20"))))
    allow_scheme_mismatch: bool = os.getenv("ALLOW_SCHEME_MISMATCH", "false").lower() == "true"


settings = Settings()