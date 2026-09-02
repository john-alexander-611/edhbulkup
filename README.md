# EDH Bulk Up

edhbulkup.com

## What It Does

I often see people ask on Reddit - what decks can I build with cards I already have? EDH Bulk Up hopes to answer that question.

EDH Bulk Up takes the average decklists from EDHRec(www.edhrec.com) and compares them against the cards in a user's collection. It will give the user the percentage based
on how many of the cards they already own. Then it gives suggestions for cards that could replace the cards the user is missing from the average decklist. The user
can also choose to pick a distinct color identity, or choose to include/exclude certain colors.

Card suggestions work on a combination of Scryfall(www.scryfall.com) tags and EDHRec data. First we identify what tags from the preset categories a card has on
Scryfall (ramp, removal, etc). Then the tool finds all other cards that also have that tag that exist on a card's EDHRec page, but aren't in the average decklist.
For each card/category EDH Bulk Up suggests those cards to replace the missing cards.

## Installation Instructions
EDH Bulk Up has two services that run at the same time:

- a FastAPI/uvicorn backend (Python)
- a Next.js frontend (npm)

## Prerequisites

- Python and Node.js/npm
- GNU Make

On Windows, install GNU Make once:

```powershell
winget install -e --id GnuWin32.Make
```

Restart VS Code or open a new terminal afterward so `make` is available on the `PATH`. You can use either PowerShell or Git Bash; the Make targets work from both.

Install project dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
npm --prefix frontend install
```

## Run the application

From the repository root, use separate terminals for the two long-running servers:

```powershell
make run-backend
make run-frontend
```

The backend runs at `http://127.0.0.1:8001` and the frontend runs at `http://localhost:3000`.

The Make targets run these commands:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
npm run dev -- --port 3000
```

For the direct frontend command, run it from `frontend/`. The Make target runs it there automatically.

Override ports when they are occupied:

```powershell
make run-backend BACKEND_PORT=8002
make run-frontend FRONTEND_PORT=3001
```

In Git Bash, the backend override can also be written as:

```bash
BACKEND_PORT=8002 make run-backend
```

## Build and test

```powershell
make build
make test
make run-tests
```

`make build` runs the production Next.js build. `make test` and `make run-tests` both run the Python test suite.

### Coverage

Install the coverage plugin once:

```powershell
python -m pip install pytest-cov
```

Run the focused application coverage report:

```powershell
python -m pytest --cov=app --cov=models --cov=services --cov=scryfall --cov=parse_input --cov=commander_specific --cov=find_deck_matches --cov-report=term-missing -q
```

This excludes standalone cache-building scripts from the metric while reporting coverage for application code.

## API configuration

The frontend reads `NEXT_PUBLIC_API_BASE_URL` from `frontend/.env.local`; it defaults to `http://127.0.0.1:8001`. To use an overridden backend port, add this line to `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8002
```