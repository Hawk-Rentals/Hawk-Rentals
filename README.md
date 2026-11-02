# Hawk Rentals

Next.js frontend, FastAPI backend, SQLite database.

## Backend

```sh
cd backend
python -m venv .venv
# Activate the virtual environment, then:
python -m pip install -r requirements-dev.txt
```

Configure staff access before starting the API. Copy `.env.example` to `.env` and set a long random `STAFF_API_KEY` value. Export that value in the shell used to run the backend (FastAPI does not automatically load `.env` files):

```sh
# macOS/Linux
export STAFF_API_KEY="your-long-random-secret"
uvicorn main:app --reload
```

```powershell
# Windows PowerShell
$env:STAFF_API_KEY = "your-long-random-secret"
uvicorn main:app --reload
```

The first startup creates the SQLite tables and inserts a starter fleet if the vehicle table is empty. Seeding is idempotent: existing vehicle data and staff edits are not overwritten.

Customer vehicle listings are public at `GET /vehicles`. Vehicle creation, editing, and archiving require the `X-Staff-Key` request header to match `STAFF_API_KEY`.

## Frontend

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/staff` for the staff fleet management page. Enter the same `STAFF_API_KEY` configured for the backend. The page supports adding, editing, archiving, and refreshing vehicles. Archived vehicles remain in the database for reservation history but are excluded from the customer catalog.

## Tests

```sh
cd backend
python -m pytest
```

The vehicle management tests use a temporary SQLite database and a test-only staff key.
