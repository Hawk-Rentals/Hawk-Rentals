from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from models import Reservation, ReservationCreate, Vehicle

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
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/vehicles")
def get_vehicles(category: str | None = None):
    with Session(engine) as session:
        query = select(Vehicle)
        if category:
            query = query.where(Vehicle.category == category)
        return session.exec(query).all()


@app.post("/vehicles")
def create_vehicle(vehicle: Vehicle):
    with Session(engine) as session:
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
        if not vehicle.available:
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
