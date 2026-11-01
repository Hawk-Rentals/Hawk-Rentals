from datetime import date

from sqlmodel import Field, SQLModel


class Vehicle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    make: str
    model: str
    category: str
    daily_rate: float
    available: bool = True


class Reservation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    vehicle_id: int = Field(foreign_key="vehicle.id")
    customer_name: str
    start_date: date
    end_date: date


class ReservationCreate(SQLModel):
    vehicle_id: int
    customer_name: str
    driver_license_number: str
    driver_license_expiry: date
    start_date: date
    end_date: date
