import hashlib
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from models import (
    Reservation,
    ReservationConfirmation,
    ReservationCreate,
    ReservationRead,
    Vehicle,
    VehicleAvailability,
    VehicleCreate,
    VehicleStatus,
    VehicleUpdate,
)

engine = create_engine(
    "sqlite:///hawkdrive.db", connect_args={"check_same_thread": False, "timeout": 10}
)

INITIAL_VEHICLES = [
    {"make": "Toyota", "model": "Corolla", "category": "compact", "daily_rate": 55.0},
    {"make": "Honda", "model": "Civic", "category": "compact", "daily_rate": 60.0},
    {"make": "Toyota", "model": "RAV4", "category": "suv", "daily_rate": 85.0},
    {"make": "Ford", "model": "Mustang", "category": "sports", "daily_rate": 120.0},
    {"make": "Mazda", "model": "3", "category": "compact", "daily_rate": 58.0},
    {"make": "Hyundai", "model": "Elantra", "category": "compact", "daily_rate": 52.0},
    {"make": "Tesla", "model": "Model 3", "category": "electric", "daily_rate": 105.0},
    {"make": "BMW", "model": "3 Series", "category": "luxury", "daily_rate": 135.0},
    {"make": "Jeep", "model": "Wrangler", "category": "suv", "daily_rate": 110.0},
    {"make": "Mazda", "model": "MX-5", "category": "sports", "daily_rate": 115.0},
    {"make": "Kia", "model": "Sportage", "category": "suv", "daily_rate": 82.0},
    {"make": "Nissan", "model": "Altima", "category": "sedan", "daily_rate": 68.0},
]


def seed_initial_vehicles() -> None:
    """Insert the starter fleet once, without overwriting existing staff changes."""
    with Session(engine) as session:
        if session.exec(select(Vehicle.id)).first() is None:
            session.add_all(Vehicle(**vehicle) for vehicle in INITIAL_VEHICLES)
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    migrate_existing_database()
    seed_initial_vehicles()
    yield


def migrate_existing_database() -> None:
    """Add missing columns to existing SQLite databases without replacing data."""
    with engine.begin() as connection:
        for table, additions in {
            "vehicle": {"archived": "BOOLEAN NOT NULL DEFAULT 0"},
            "reservation": {
                "status": "VARCHAR NOT NULL DEFAULT 'confirmed'",
                "management_token_hash": "VARCHAR",
            },
        }.items():
            columns = {column["name"] for column in inspect(connection).get_columns(table)}
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "PATCH", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "X-Staff-Key", "X-Booking-Token"],
)


def require_staff(x_staff_key: str | None = Header(default=None, alias="X-Staff-Key")) -> None:
    configured_key = os.getenv("STAFF_API_KEY")
    if not configured_key:
        raise HTTPException(status_code=503, detail="Staff access is not configured")
    if not x_staff_key or not secrets.compare_digest(x_staff_key, configured_key):
        raise HTTPException(status_code=401, detail="Valid staff credentials are required")


@app.get("/health")
def health():
    return {"status": "ok"}


def booked_until_date(reservations: list[Reservation], start_date: date, end_date: date) -> date | None:
    """USER-5: return when a vehicle becomes free again, or None if it is free for the whole period.

    Two periods overlap when existing pickup < requested return and existing return > requested
    pickup (the same rule USER-1 uses to reject double bookings). Back-to-back bookings are
    chained so the customer sees the real date the car is next free.
    """
    if not any(r.start_date < end_date and r.end_date > start_date for r in reservations):
        return None
    free_from = start_date
    for reservation in sorted(reservations, key=lambda r: r.start_date):
        if reservation.start_date <= free_from < reservation.end_date:
            free_from = reservation.end_date
        elif reservation.start_date > free_from:
            break
    if free_from == start_date:
        # Free at pickup but booked later in the requested period.
        free_from = max(r.end_date for r in reservations if r.start_date < end_date and r.end_date > start_date)
    return free_from


@app.get("/vehicles", response_model=list[VehicleAvailability])
def get_vehicles(
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    status: VehicleStatus | None = None,
    # USER-4: optional daily-rate range, e.g. /vehicles?min_price=50&max_price=100
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
):
    # USER-4: a range where the minimum is above the maximum can never match anything.
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="Minimum price cannot be greater than maximum price")
    # Without dates, report each vehicle's status for today.
    if (start_date is None) != (end_date is None):
        raise HTTPException(status_code=400, detail="Pickup and return dates must be given together")
    if start_date is None:
        start_date = date.today()
        end_date = start_date + timedelta(days=1)
    elif start_date >= end_date:
        raise HTTPException(status_code=400, detail="Return date must be after pickup date")

    with Session(engine) as session:
        # Archived vehicles remain in the DB for existing reservations/auditing.
        query = select(Vehicle).where(Vehicle.archived == False)  # noqa: E712
        if category:
           query = query.where(Vehicle.category == category)
        if min_price is not None:
            query = query.where(Vehicle.daily_rate >= min_price)
        if max_price is not None:
            query = query.where(Vehicle.daily_rate <= max_price)
        vehicles = session.exec(query).all()
        # USER-5: confirmed reservations that end after the requested pickup date.
        # Cancelled reservations (USER-3) are ignored, so cancelling frees the car.
        upcoming = session.exec(
            select(Reservation).where(
                Reservation.status == "confirmed",
                Reservation.end_date > start_date,
            )
        ).all()

    reservations_by_vehicle: dict[int, list[Reservation]] = {}
    for reservation in upcoming:
        reservations_by_vehicle.setdefault(reservation.vehicle_id, []).append(reservation)

    results = []
    for vehicle in vehicles:
        booked_until = None
        if not vehicle.available:
            vehicle_status = "unavailable"
        else:
            booked_until = booked_until_date(reservations_by_vehicle.get(vehicle.id, []), start_date, end_date)
            vehicle_status = "booked" if booked_until else "available"
        if status is None or vehicle_status == status:
            results.append(
                VehicleAvailability(**vehicle.model_dump(), status=vehicle_status, booked_until=booked_until)
            )
    return results


@app.post("/vehicles", response_model=Vehicle, dependencies=[Depends(require_staff)])
def create_vehicle(request: VehicleCreate):
    with Session(engine) as session:
        vehicle = Vehicle(**request.model_dump())
        session.add(vehicle)
        session.commit()
        session.refresh(vehicle)
        return vehicle


@app.patch(
    "/vehicles/{vehicle_id}",
    response_model=Vehicle,
    dependencies=[Depends(require_staff)],
)
def edit_vehicle(vehicle_id: int, request: VehicleUpdate):
    updates = request.model_dump(exclude_unset=True)
    if not updates or any(value is None for value in updates.values()):
        raise HTTPException(status_code=422, detail="Provide valid vehicle fields to update")

    with Session(engine) as session:
        vehicle = session.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.archived:
            raise HTTPException(status_code=404, detail="Active vehicle not found")
        for key, value in updates.items():
            setattr(vehicle, key, value)
        session.add(vehicle)
        session.commit()
        session.refresh(vehicle)
        return vehicle


@app.patch(
    "/vehicles/{vehicle_id}/archive",
    response_model=Vehicle,
    dependencies=[Depends(require_staff)],
)
def archive_vehicle(vehicle_id: int):
    with Session(engine) as session:
        vehicle = session.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.archived:
            raise HTTPException(status_code=404, detail="Active vehicle not found")
        vehicle.archived = True
        vehicle.available = False
        session.add(vehicle)
        session.commit()
        session.refresh(vehicle)
        return vehicle


@app.post("/reservations", response_model=ReservationConfirmation, status_code=201)
def create_reservation(request: ReservationCreate):
    if request.start_date >= request.end_date:
        raise HTTPException(status_code=400, detail="Return date must be after pickup date")
    if not request.customer_name.strip():
        raise HTTPException(status_code=400, detail="Customer name is required")
    if len(request.driver_license_number.strip()) < 5:
        raise HTTPException(status_code=400, detail="Driver's licence number is required")
    if request.driver_license_expiry < request.end_date:
        raise HTTPException(status_code=400, detail="Driver's licence expires before return date")

    with Session(engine) as session:
        session.exec(text("BEGIN IMMEDIATE"))
        vehicle = session.get(Vehicle, request.vehicle_id)
        if vehicle is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if vehicle.archived or not vehicle.available:
            raise HTTPException(status_code=409, detail="Vehicle is unavailable")

        overlapping = session.exec(
            select(Reservation).where(
                Reservation.status == "confirmed",
                Reservation.vehicle_id == request.vehicle_id,
                Reservation.start_date < request.end_date,
                Reservation.end_date > request.start_date,
            )
        ).first()
        if overlapping is not None:
            raise HTTPException(status_code=409, detail="Vehicle already booked for these dates")

        management_token = secrets.token_urlsafe(32)
        reservation = Reservation(
            vehicle_id=request.vehicle_id,
            customer_name=request.customer_name.strip(),
            start_date=request.start_date,
            end_date=request.end_date,
            management_token_hash=hashlib.sha256(management_token.encode()).hexdigest(),
        )
        session.add(reservation)
        session.commit()
        session.refresh(reservation)
        return ReservationConfirmation(
            **reservation.model_dump(exclude={"management_token_hash"}),
            management_token=management_token,
        )


def find_customer_reservation(session: Session, reservation_id: int, token: str | None) -> Reservation:
    reservation = session.get(Reservation, reservation_id)
    supplied_hash = hashlib.sha256((token or "").encode()).hexdigest()
    if (
        reservation is None
        or reservation.management_token_hash is None
        or not secrets.compare_digest(reservation.management_token_hash, supplied_hash)
    ):
        raise HTTPException(
            status_code=404,
            detail="Reservation not found. Check your booking number and access code.",
        )
    return reservation


@app.get("/reservations/{reservation_id}", response_model=ReservationRead)
def get_reservation(
    reservation_id: int,
    x_booking_token: str | None = Header(default=None, alias="X-Booking-Token"),
):
    with Session(engine) as session:
        return find_customer_reservation(session, reservation_id, x_booking_token)


@app.post("/reservations/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(
    reservation_id: int,
    x_booking_token: str | None = Header(default=None, alias="X-Booking-Token"),
):
    with Session(engine) as session:
        session.exec(text("BEGIN IMMEDIATE"))
        reservation = find_customer_reservation(session, reservation_id, x_booking_token)
        if reservation.status == "cancelled":
            raise HTTPException(status_code=409, detail="This reservation has already been cancelled.")
        if reservation.start_date <= date.today():
            raise HTTPException(status_code=409, detail="Only upcoming reservations can be cancelled. Pickup must be after today.")
        reservation.status = "cancelled"
        session.add(reservation)
        session.commit()
        session.refresh(reservation)
        return reservation
