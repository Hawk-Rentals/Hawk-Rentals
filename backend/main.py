from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from models import (
    Reservation,
    ReservationCreate,
    Vehicle,
    VehicleAvailability,
    VehicleCreate,
    VehicleStatus,
    VehicleUpdate,
)

engine = create_engine(
    "sqlite:///hawkdrive.db", connect_args={"check_same_thread": False, "timeout": 10}
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/vehicles", response_model=list[VehicleAvailability])
def get_vehicles(
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    status: VehicleStatus | None = None,
):
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
        vehicles = session.exec(query).all()
        booked_ids = set(
            session.exec(
                select(Reservation.vehicle_id).where(
                    Reservation.start_date < end_date,
                    Reservation.end_date > start_date,
                )
            ).all()
        )

    results = []
    for vehicle in vehicles:
        if not vehicle.available:
            vehicle_status = "unavailable"
        elif vehicle.id in booked_ids:
            vehicle_status = "booked"
        else:
            vehicle_status = "available"
        if status is None or vehicle_status == status:
            results.append(VehicleAvailability(**vehicle.model_dump(), status=vehicle_status))
    return results


@app.post("/vehicles", response_model=Vehicle)
def create_vehicle(request: VehicleCreate):
    with Session(engine) as session:
        vehicle = Vehicle(**request.model_dump())
        session.add(vehicle)
        session.commit()
        session.refresh(vehicle)
        return vehicle


@app.patch("/vehicles/{vehicle_id}", response_model=Vehicle)
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


@app.patch("/vehicles/{vehicle_id}/archive", response_model=Vehicle)
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


@app.post("/reservations", response_model=Reservation, status_code=201)
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
                Reservation.vehicle_id == request.vehicle_id,
                Reservation.start_date < request.end_date,
                Reservation.end_date > request.start_date,
            )
        ).first()
        if overlapping is not None:
            raise HTTPException(status_code=409, detail="Vehicle already booked for these dates")

        reservation = Reservation(
            vehicle_id=request.vehicle_id,
            customer_name=request.customer_name.strip(),
            start_date=request.start_date,
            end_date=request.end_date,
        )
        session.add(reservation)
        session.commit()
        session.refresh(reservation)
        return reservation
