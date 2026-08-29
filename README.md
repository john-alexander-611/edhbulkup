# edhbulkup
# EDH Bulk Up

## Run the legacy backend app

The original FastAPI app remains on port 8000 and should be left alone while working on the Next.js UI.

From the repository root in PowerShell:

```powershell
.\run_app.ps1 -Action start
```

Use `restart` after code changes or `stop` to release port 8000:

```powershell
.\run_app.ps1 -Action restart
.\run_app.ps1 -Action stop
```

If GNU Make is installed, the equivalent commands are:

```text
make start
make restart
make stop
make test
```

The legacy backend app is available at http://127.0.0.1:8000.

## Run the React/Next.js frontend

Open a terminal in the frontend directory:

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

The frontend expects the analysis API to be running at http://127.0.0.1:8001, which is the dedicated port for the new UI.

## Frontend build check

To verify the Next.js app compiles cleanly:

```powershell
cd .\frontend
npm run build
```

This is useful after making UI or routing changes.