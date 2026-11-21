from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Website:
    id: int
    name: str
    expected_url: str
    expected_status_code: int = 200
    expected_final_url: Optional[str] = None
    expected_text: Optional[str] = None
    enabled: bool = True
    allow_scheme_mismatch: bool = False

    @classmethod
    def from_row(cls, row: Any) -> "Website":
        return cls(
            id=row["id"],
            name=row["name"],
            expected_url=row["expected_url"],
            expected_status_code=row["expected_status_code"],
            expected_final_url=row["expected_final_url"],
            expected_text=row["expected_text"],
            enabled=bool(row["enabled"]),
            allow_scheme_mismatch=bool(row["allow_scheme_mismatch"]),
        )


@dataclass
class CheckResult:
    website_id: int
    checked_at: str
    status: str
    http_status_code: Optional[int]
    expected_url: str
    actual_url: Optional[str]
    response_time_ms: Optional[float]
    error_message: Optional[str]
    dns_ok: bool
    connection_ok: bool
    redirect_chain: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "website_id": self.website_id,
            "checked_at": self.checked_at,
            "status": self.status,
            "http_status_code": self.http_status_code,
            "expected_url": self.expected_url,
            "actual_url": self.actual_url,
            "response_time_ms": self.response_time_ms,
            "error_message": self.error_message,
            "dns_ok": self.dns_ok,
            "connection_ok": self.connection_ok,
            "redirect_chain": self.redirect_chain,
        }