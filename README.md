# edhbulkup
# EDH Bulk Up

The app has two parts that need to run at the same time:

- a FastAPI/uvicorn backend (Python)
- a Next.js frontend (npm)

## Run the backend (uvicorn)

The frontend expects the API on **port 8001**, so start the backend with that port.

From the repository root in PowerShell:

```powershell
.\run_app.ps1 -Action start -Port 8001
```

Use `restart` after code changes, or `stop` to release the port:

```powershell
.\run_app.ps1 -Action restart -Port 8001
.\run_app.ps1 -Action stop -Port 8001
```

If GNU Make is installed, `make start` / `make restart` / `make stop` run the same script on the default port (8000) — pass a port explicitly if you need 8001.

The backend is then available at http://127.0.0.1:8001.

## Run the frontend (Next.js)

In a separate terminal, from the repository root:

```powershell
cd .\frontend
npm install
npm run dev
```

Then open the app in your browser:

```text
http://localhost:3000
```

If port 3000 is already occupied, Next.js will automatically select the next available port, such as 3001.

The frontend reads the API base URL from `frontend/.env.example` / `.env.local` (`NEXT_PUBLIC_API_BASE_URL`), which defaults to http://127.0.0.1:8001 — make sure this matches the port the backend is running on.

## Tests

```powershell
make test
```

## Frontend build check

To verify the Next.js app compiles cleanly:

```powershell
cd .\frontend
npm run build
```

This is useful after making UI or routing changes.