from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class WebsiteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    expected_url: HttpUrl
    expected_status_code: int = Field(default=200, ge=100, le=599)
    expected_final_url: Optional[HttpUrl] = None
    expected_text: Optional[str] = Field(default=None, max_length=500)
    enabled: bool = True
    allow_scheme_mismatch: bool = False


class WebsiteOutput(BaseModel):
    id: int
    name: str
    expected_url: str
    expected_status_code: int
    expected_final_url: Optional[str]
    expected_text: Optional[str]
    enabled: bool
    allow_scheme_mismatch: bool


class WebsiteBatchOutput(BaseModel):
    inserted: int
    websites: list[WebsiteOutput]


class WebsiteBulkInput(BaseModel):
    websites: list[WebsiteInput] = Field(min_length=1, max_length=5000)


class CheckOutput(BaseModel):
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
    redirect_chain: list[dict]