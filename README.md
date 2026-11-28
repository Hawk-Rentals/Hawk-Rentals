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
completed, cancelled), and booking cost estimate where known.
New bookings snapshot the daily rate when reserved. A date change recalculates
the estimate using the saved rate, and a vehicle change snapshots the new
vehicle's current rate. Staff price edits and vehicle archiving do not change
saved rates. Historical
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

## Modify a reservation (USER-7)

Open **My booking** (`/reservations`) and enter the booking number and private
access code. For an upcoming confirmed booking, select **Edit reservation**,
change the dates, vehicle, or customer name, and re-enter the driver's licence
details. **Save changes** checks availability and displays the updated
confirmation. Customers keep the same booking number and access code. If a
change is rejected, the saved booking stays intact.

## Vehicle Maintenance History (REP-2B)

Open **Staff Fleet Management** (`/staff`) and choose **Vehicle maintenance history**
(`/staff/maintenance`). Enter the same `STAFF_API_KEY` used for staff fleet changes,
select a vehicle, and choose **Refresh history**. Staff can view archived vehicles'
maintenance records, log completed maintenance activities, report open defects,
and resolve defects with mandatory resolution notes. Resolved records remain in
history, including timestamps. All history and mutations require `X-Staff-Key`.

API routes:
- `GET /staff/maintenance/vehicles`: all fleet vehicles, including archived
- `GET /staff/vehicles/{id}/maintenance`: history of maintenance and defects
- `POST /staff/vehicles/{id}/maintenance`: add `maintenance` or `defect`
- `PATCH /staff/vehicles/{id}/maintenance/{record_id}/resolve`: resolve an open defect

Maintenance is completed when logged; defects start open and are resolved with
notes. Creating or resolving a defect does **not** automatically change the
vehicle's availability: vehicle safety decisions remain with REP-2A's inspection
workflow. REP-2B has a dedicated SQLite table to avoid modifying REP-2A's
inspection schema. The inspection-history panel probes the protected REP-2A
inspection endpoint when available; integration of the final endpoint must be
confirmed after REP-2A merges. No maintenance or inspection history is publicly
exposed. Records remain accessible when a vehicle is archived.

Demo: open the staff maintenance page, authorize with the staff key, select a
vehicle, record a maintenance activity, record a defect, resolve the defect with
notes, and refresh to demonstrate that every entry is preserved. Run
`python -m pytest tests/test_maintenance_history.py -q` in `backend`.

## Fleet Utilization Summary (REP-1A)

Staff can open `http://localhost:3000/staff/reports` (linked from `/staff`), enter the staff API key, and choose a date range to see how much of the fleet was rented.

- `GET /staff/reports/utilization?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` requires `X-Staff-Key`.
- Utilization = booked days / days in the period. The period is inclusive of both dates; a reservation counts the nights from pickup up to (not including) return, matching billing.
- Only confirmed reservations count. Cancelled bookings (USER-3) are excluded and modified bookings (USER-7) use their current dates.
- Reservations that cross the period boundary are clipped, so utilization never exceeds 100%.
- Results include fleet totals, a per-category breakdown, and per-vehicle rows sorted busiest first. Archived vehicles are excluded unless `include_archived=true`.
- With no dates, the report covers the last 30 days. Periods longer than 366 days are rejected.

The endpoint only reads the existing `vehicle` and `reservation` tables; it adds no new tables.

## Vehicle Utilization Rankings (REP-1B)

The staff utilization report also displays a ranked vehicle table for the selected date range. Vehicles are numbered from highest to lowest utilization, with ties kept in the stable vehicle-ID order supplied by the backend. The ranking reuses the per-vehicle results from REP-1A; it does not add another endpoint or duplicate utilization calculations. Archived vehicles appear only when the report's **Include archived vehicles** option is selected.


## Tests

```sh
cd backend
python -m pytest
```

The vehicle management tests use a temporary SQLite database and a test-only staff key.
