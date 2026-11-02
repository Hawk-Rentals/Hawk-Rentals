from datetime import date

from pydantic import ConfigDict, field_validator
from sqlmodel import Field, SQLModel


class Vehicle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    make: str
    model: str
    category: str
    daily_rate: float
    available: bool = True
    archived: bool = False


class VehicleCreate(SQLModel):
    make: str
    model: str
    category: str
    daily_rate: float = Field(gt=0)
    available: bool = True

    @field_validator("make", "model", "category")
    @classmethod
    def nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class VehicleUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    make: str | None = None
    model: str | None = None
    category: str | None = None
    daily_rate: float | None = Field(default=None, gt=0)
    available: bool | None = None

    @field_validator("make", "model", "category")
    @classmethod
    def nonempty_if_provided(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


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
