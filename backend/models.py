from datetime import date
from typing import Literal

from pydantic import ConfigDict, field_validator
from sqlmodel import Field, SQLModel

VehicleStatus = Literal["available", "booked", "unavailable"]


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


class VehicleAvailability(SQLModel):
    id: int
    make: str
    model: str
    category: str
    daily_rate: float
    available: bool
    archived: bool
    status: VehicleStatus
    # USER-5: for a booked vehicle, the first date it is free again after the
    # requested pickup date (back-to-back bookings are chained). None otherwise.
    booked_until: date | None = None


class Reservation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    vehicle_id: int = Field(foreign_key="vehicle.id")
    customer_name: str
    start_date: date
    end_date: date
    status: str = "confirmed"
    management_token_hash: str | None = None
    booked_daily_rate: float | None = None


class ReservationRead(SQLModel):
    id: int
    vehicle_id: int
    customer_name: str
    start_date: date
    end_date: date
    status: Literal["confirmed", "cancelled"]


class ReservationConfirmation(ReservationRead):
    management_token: str


class ReservationCreate(SQLModel):
    vehicle_id: int
    customer_name: str
    driver_license_number: str
    driver_license_expiry: date
    start_date: date
    end_date: date


class RentalHistoryRead(SQLModel):
    """Verified booking details used by the customer rental-history page."""

    id: int
    vehicle_id: int
    vehicle_make: str
    vehicle_model: str
    customer_name: str
    start_date: date
    end_date: date
    status: Literal["confirmed", "cancelled"]
    rental_state: Literal["upcoming", "ongoing", "completed", "cancelled"]
    booked_daily_rate: float | None
    original_total: float | None
