# edhbulkup
# EDH Bulk Up

## Run the web app

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

The app is available at http://127.0.0.1:8000.