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

## Demo fleet and photos

Fresh databases start with twelve demo vehicles across compact, sedan, SUV,
sports, electric, and luxury categories. Prices are illustrative demo rates.
To add missing demo vehicles to an existing database, run the following from `backend`:

```sh
python seed_demo_fleet.py
```

This explicit command preserves staff edits, archived cars, and existing reservations.
Normal startup still seeds only an empty fleet. Model photos are bundled in
`frontend/public/vehicles`; sources, photographers, and licences are recorded in
`frontend/app/vehiclePhotos.json` and displayed at `/photo-credits`.
Photos illustrate the models; the year, colour, and trim may differ.

## Manage and cancel reservations (USER-3)

New booking confirmations include a booking number and a private access code.
Save both, then use **My booking** (`/reservations`) to look up the booking.
Select **Cancel reservation**, then confirm or choose **Keep reservation**.
Cancelled bookings remain saved, display a Cancelled status, and no longer block
vehicle availability or new reservations for those dates. Out-of-service and
archived vehicles remain unavailable.

The application does not have customer accounts yet. The private access code
acts as the booking credential; only its SHA-256 hash is stored in SQLite.
Lookup (`GET /reservations/{id}`) and cancellation
(`POST /reservations/{id}/cancel`) require it in the `X-Booking-Token` header.
Existing bookings are preserved by an automatic additive schema migration, but
bookings created before this feature have no access code and cannot be managed
through the customer lookup. Create a new booking for the demo.

Cancellation is allowed only when the pickup date is after the server's current
date. Date-only bookings cannot express a precise 24-hour cutoff. Payments and
refunds are not implemented; no refund is claimed or issued by this feature.
The backlog's 24-hour refund policy still needs clarification before adding payments.

Demo: reserve a vehicle for future dates, save the confirmation details, check
that the vehicle is booked for those dates, open My booking, choose Keep
reservation once, then cancel and confirm. Reload the booking to show the saved
Cancelled status, then search the same dates to show restored availability.

## Rental history (USER-6)

Customers can view rental history at `/history`. The history page only loads bookings
whose booking number **and** private access code are known, using
`GET /reservations/{id}/history` with the `X-Booking-Token` header.

There is no customer login system, so **do not search for all reservations
by customer name**. Each booking is authorized separately with its original
access code; users can add existing bookings or optionally save new bookings
to this browser's local storage. This is intended for personal devices only.
Users can remove stored booking credentials without cancelling the booking.
A different browser or device needs the access code entered again.

The page shows the vehicle, dates, customer, status (upcoming, in progress,
completed, cancelled), and original booking cost estimate where known.
New bookings snapshot the daily rate when reserved; later price edits or
vehicle archiving do not retroactively change the estimate. Historical
bookings without a price snapshot display "Not recorded" instead of
inventing a rate. No payment or refund status is asserted by the estimate.
Bookings made before private access codes were introduced cannot be
imported without a secure account-recovery mechanism.

### USER-6 demo

1. Start the backend and frontend as described above.
2. Create a future booking on the home page and note its ID/access code.
3. Choose **Save to rental history on this device**, then open `/history`.
4. Verify the booking appears with its status, rental dates, vehicle name
   and original estimate.
5. Use **Remove from this device** and re-add the booking with its code.
6. For cancellation integration, cancel an upcoming booking in `/reservations`,
   then refresh `/history` to see the updated Cancelled status.

Run `python -m pytest tests/test_rental_history.py -q` from the backend
directory to run USER-6's automated API tests.

## Tests

```sh
cd backend
python -m pytest
```

The vehicle management tests use a temporary SQLite database and a test-only staff key.
