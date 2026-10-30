from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session, SQLModel, create_engine, select

from models import Reservation, Vehicle

engine = create_engine("sqlite:///hawkdrive.db", connect_args={"check_same_thread": False})


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(lifespan=lifespan)


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
