# UPURL Website Monitor

A local website health dashboard built with FastAPI, SQLite, asyncio/httpx, React, and Vite. Health is determined by HTTP(S), final URL, expected status, and optional page text. ICMP ping is not used as an application health signal.

## Requirements

- macOS 12 or newer
- Python 3.9 or newer
- Node.js 18 or newer with npm

## Run locally on macOS

From Terminal, run the backend:

```sh
cd ~/Desktop/UPURL-monitor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second Terminal window, run the dashboard:

```sh
cd ~/Desktop/UPURL-monitor/frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. The API is at <http://127.0.0.1:8000>; interactive API docs are at <http://127.0.0.1:8000/docs>.

If Node.js is not installed, install it with Homebrew using `brew install node`, or use the official macOS installer from <https://nodejs.org/>.

## Host the app publicly

The Netlify site hosts only the static React frontend. The FastAPI backend must also be deployed to a public Python host. The provided `render.yaml` configures a Render Free web service, which avoids a paid persistent disk but has important limitations: free services can spin down after inactivity, and their local filesystem is ephemeral. This setup is suitable for trying the shared dashboard, not dependable continuous monitoring or permanent storage. Monitoring pauses while the backend is asleep, and its SQLite website configuration and history can be lost when the service restarts or redeploys. The backend receives regular requests while someone is viewing the dashboard, which may keep it awake during that time.

1. Push this project to a Git provider such as GitHub, then create a Render Blueprint from that repository and apply `render.yaml`.
2. Wait for the Render service to deploy. Confirm `https://<your-render-service>.onrender.com/api/health` returns `{"status":"ok"}`.
3. In the Netlify site settings, set the environment variable `VITE_API_URL` to `https://<your-render-service>.onrender.com/api` (include `/api`). Then trigger a new deploy. Vite embeds this value during the frontend build; changing it requires rebuilding and redeploying the site.
4. In Render, set `CORS_ORIGINS` to a comma-separated list of exact frontend origins, including `https://idyllic-speculoos-ddc1b8.netlify.app`. Add any custom domain used by the site as another origin, with no trailing slash, and redeploy the backend.

On the Free service, SQLite uses the temporary path `/tmp/monitor.db`; the local `data/monitor.db` is not uploaded. Export or otherwise back up any data you need before a restart or redeploy. For durable history and uninterrupted checks, use a paid always-on backend with persistent storage or change the app to use a separately hosted persistent database and an always-running scheduler. For production use, review the target websites before adding them, because the hosted backend will make outbound HTTP requests to each configured URL.

## Configure websites

The app imports `data/websites.csv` into SQLite the first time it starts, and only seeds when the database has no websites. The included public URLs are labeled as samples; the HTTPBin 404 entry is intentionally unhealthy so error handling is visible. Replace or extend these rows before the first run if desired.

After startup, add, edit, pause, or remove targets with the dashboard. Each target stores a name, configured URL, expected final status, optional expected final URL, optional expected response text, enabled state, and whether an HTTP/HTTPS scheme difference is acceptable. The UI and API can manage 100+ records without source changes. `data/monitor.db` contains the configuration and check history; back it up to preserve both.

Use **Add website** in the dashboard to add one or more targets directly. For multiple targets, enter URLs separated by commas or new lines; each target is named from its domain. No spreadsheet or CSV file is needed.

For bulk configuration, prepare the CSV before the first launch using these columns:

```csv
name,expected_url,expected_status_code,expected_final_url,expected_text,enabled,allow_scheme_mismatch
Sample: Example Domain,https://example.com/,200,,,true,false
```

Once the database has been initialized, manage ongoing changes in the dashboard or through the website CRUD API. The CSV is an initial seed, not a continuously synchronized source.

For an existing database, select **Import CSV** in the dashboard and choose a UTF-8 CSV with the same columns. The import validates every row before inserting any, accepts up to 5,000 websites per file (2 MB maximum), and adds rows without replacing existing websites. Upload only new rows to avoid duplicates.

## Monitoring behavior

- Enabled websites are checked concurrently with an asyncio semaphore, limited to 20 concurrent checks by default and capped at 100.
- The scheduler starts a check cycle at startup and then targets a 60-second interval.
- DNS is resolved before the HTTP request. HTTP(S) response, not DNS or ping alone, determines health.
- If the async connection fails on a dual-stack hostname, the monitor retries over IPv4 when DNS also returned an IPv4 address. This handles hosts whose IPv6 route is broken without forcing all checks off IPv6.
- Redirects are followed up to 10 hops and retained in history. Hostnames are case-normalized, default ports and trailing slashes are normalized, and fragments are ignored when comparing URLs. Scheme equivalence is opt-in per website or globally.
- `DOWN` includes DNS, connection, timeout, TLS, redirect-loop, and HTTP 5xx failures. Unexpected final destinations are `URL_MISMATCH`. Unexpected non-5xx status codes or missing expected text are `HTTP_ERROR`.
- Each result is stored in SQLite with HTTP status, actual URL, response time, DNS and connection results, error details, and redirect chain.
- Backend logs include timestamp, website, outcome, HTTP status, response time, and error.
- The dashboard refreshes status every 15 seconds and supports a manual all-sites or per-site check.

## Environment settings

Copy `backend/.env.example` to `backend/.env` and adjust as needed:

| Setting | Default | Purpose |
| --- | --- | --- |
| `DATABASE_PATH` | `data/monitor.db` | SQLite database path, relative to the project root unless absolute |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact browser origins allowed to call the API |
| `CHECK_INTERVAL_SECONDS` | `60` | Scheduler interval; values below 10 are raised to 10 |
| `REQUEST_TIMEOUT_SECONDS` | `12` | Per-request timeout |
| `MAX_CONCURRENT_CHECKS` | `20` | Maximum concurrent checks and HTTP connections |
| `ALLOW_SCHEME_MISMATCH` | `false` | Treat HTTP and HTTPS as equivalent globally |

No credentials or tokens are required. The API binds to localhost in the documented run command and is intended for local use.

## API

- `GET /api/websites` and `GET /api/websites/{id}`
- `POST /api/websites`, `POST /api/websites/bulk`, `PUT /api/websites/{id}`, `DELETE /api/websites/{id}`
- `POST /api/websites/import` with a raw UTF-8 `text/csv` request body
- `GET /api/status` and `GET /api/status/{id}`
- `GET /api/history/{id}?limit=500`
- `POST /api/check` and `POST /api/check/{id}`
- `GET /api/health`

The JSON shape for website creation and updates is:

```json
{
  "name": "Customer portal",
  "expected_url": "https://portal.example.com/",
  "expected_status_code": 200,
  "expected_final_url": null,
  "expected_text": null,
  "enabled": true,
  "allow_scheme_mismatch": false
}
```

## Tests

```sh
cd ~/Desktop/UPURL-monitor
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
cd frontend
npm run build
```