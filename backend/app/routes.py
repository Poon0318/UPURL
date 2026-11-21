import asyncio
import csv
import io
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from . import database
from .config import settings
from .schemas import CheckOutput, WebsiteBatchOutput, WebsiteBulkInput, WebsiteInput, WebsiteOutput


router = APIRouter(prefix="/api")
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_IMPORT_RECORDS = 5000


def website_dict(site) -> dict:
    return {
        "id": site.id,
        "name": site.name,
        "expected_url": site.expected_url,
        "expected_status_code": site.expected_status_code,
        "expected_final_url": site.expected_final_url,
        "expected_text": site.expected_text,
        "enabled": site.enabled,
        "allow_scheme_mismatch": site.allow_scheme_mismatch,
    }


@router.get("/websites", response_model=list[WebsiteOutput])
def list_websites():
    return [website_dict(site) for site in database.list_websites()]


@router.post("/websites/import", status_code=status.HTTP_201_CREATED, response_model=WebsiteBatchOutput)
async def import_websites(request: Request):
    content = await request.body()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV file must be 2 MB or smaller")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV is empty")
        reader.fieldnames = [header.strip() if header else "" for header in reader.fieldnames]
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise HTTPException(status_code=400, detail="CSV column names must be unique")
        missing = {"name", "expected_url"} - set(reader.fieldnames)
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required CSV columns: {', '.join(sorted(missing))}")

        values_list = []
        for row_number, row in enumerate(reader, start=2):
            if row_number > MAX_IMPORT_RECORDS + 1:
                raise HTTPException(status_code=413, detail=f"CSV is limited to {MAX_IMPORT_RECORDS} websites per import")
            values = {key: value.strip() if isinstance(value, str) else value for key, value in row.items() if key}
            if not values.get("expected_status_code"):
                values.pop("expected_status_code", None)
            for optional in ("expected_final_url", "expected_text"):
                if values.get(optional) == "":
                    values[optional] = None
            try:
                values_list.append(WebsiteInput.model_validate(values).model_dump(mode="json"))
            except ValidationError as exc:
                raise HTTPException(status_code=400, detail=f"CSV row {row_number}: {exc.errors()[0]['msg']}")
        if not values_list:
            raise HTTPException(status_code=400, detail="CSV contains no website rows")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must use UTF-8 encoding")
    except csv.Error as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}")

    websites = await run_in_threadpool(database.create_websites, values_list)
    return {"inserted": len(websites), "websites": [website_dict(site) for site in websites]}


@router.get("/websites/{website_id}", response_model=WebsiteOutput)
def get_website(website_id: int):
    site = database.get_website(website_id)
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    return website_dict(site)


@router.post("/websites", status_code=status.HTTP_201_CREATED, response_model=WebsiteOutput)
def create_website(payload: WebsiteInput):
    return website_dict(database.create_website(payload.model_dump(mode="json")))


@router.post("/websites/bulk", status_code=status.HTTP_201_CREATED, response_model=WebsiteBatchOutput)
async def create_websites_bulk(payload: WebsiteBulkInput):
    values_list = [website.model_dump(mode="json") for website in payload.websites]
    websites = await run_in_threadpool(database.create_websites, values_list)
    return {"inserted": len(websites), "websites": [website_dict(site) for site in websites]}


@router.put("/websites/{website_id}", response_model=WebsiteOutput)
def update_website(website_id: int, payload: WebsiteInput):
    site = database.update_website(website_id, payload.model_dump(mode="json"))
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    return website_dict(site)


@router.delete("/websites/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_website(website_id: int):
    if not database.delete_website(website_id):
        raise HTTPException(status_code=404, detail="Website not found")


@router.get("/status")
def get_status(request: Request):
    sites = database.list_websites()
    latest = database.latest_results()
    rows = []
    for site in sites:
        result = latest.get(site.id)
        if result:
            result = {**result, "result_id": result["id"]}
            result.pop("id")
        rows.append({**website_dict(site), **(result or {}), "status": result["status"] if result else "UNKNOWN"})
    counts = {
        "total": len(sites),
        "enabled": sum(site.enabled for site in sites),
        "up": sum(row["status"] == "UP" for row in rows),
        "down": sum(row["status"] == "DOWN" for row in rows),
        "url_mismatch": sum(row["status"] == "URL_MISMATCH" for row in rows),
        "http_error": sum(row["status"] == "HTTP_ERROR" for row in rows),
    }
    checked = [row["checked_at"] for row in rows if row.get("checked_at")]
    return {
        "summary": counts,
        "websites": rows,
        "last_updated": max(checked) if checked else None,
        "monitoring_interval_seconds": request.app.state.settings.check_interval_seconds,
        "monitoring_active": not request.app.state.monitoring_task.done(),
    }


@router.get("/status/{website_id}")
def get_website_status(website_id: int):
    site = database.get_website(website_id)
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    latest = database.latest_results().get(website_id)
    return {
        "website": website_dict(site),
        "latest": latest,
        "last_successful_check": database.last_check_by_status(website_id, "UP"),
        "last_failed_check": next(
            (
                item["checked_at"]
                for item in reversed(database.get_history(website_id))
                if item["status"] != "UP"
            ),
            None,
        ),
    }


@router.get("/history/{website_id}")
def get_website_history(website_id: int, limit: int = 500):
    if not database.get_website(website_id):
        raise HTTPException(status_code=404, detail="Website not found")
    return database.get_history(website_id, max(1, min(limit, 2000)))


async def run_checks(monitor, sites) -> list[dict]:
    results = await monitor.check_many(sites)
    await run_in_threadpool(database.save_results, results)
    return [result.as_dict() for result in results]


@router.post("/check")
async def check_all(request: Request):
    sites = await run_in_threadpool(database.list_websites)
    sites = [site for site in sites if site.enabled]
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "results": await run_checks(request.app.state.monitor, sites)}


@router.post("/check/{website_id}", response_model=CheckOutput)
async def check_one(website_id: int, request: Request):
    site = await run_in_threadpool(database.get_website, website_id)
    if not site:
        raise HTTPException(status_code=404, detail="Website not found")
    if not site.enabled:
        raise HTTPException(status_code=409, detail="Website monitoring is disabled")
    result = await run_checks(request.app.state.monitor, [site])
    return result[0]


async def monitoring_loop(app) -> None:
    while True:
        started = time.monotonic()
        try:
            sites = await run_in_threadpool(database.list_websites)
            enabled = [site for site in sites if site.enabled]
            if enabled:
                await run_checks(app.state.monitor, enabled)
        except asyncio.CancelledError:
            raise
        except Exception:
            app.state.logger.exception("Scheduled monitoring cycle failed")
        remaining = app.state.settings.check_interval_seconds - (time.monotonic() - started)
        await asyncio.sleep(max(0, remaining))