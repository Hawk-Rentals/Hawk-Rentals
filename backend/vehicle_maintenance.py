"""REP-2B: staff-only vehicle maintenance and defect history."""
from datetime import date, datetime, timezone
from typing import Callable, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import ConfigDict, field_validator
from sqlmodel import Field, Session, SQLModel, select

from models import Vehicle

EntryType = Literal["maintenance", "defect"]
EntryStatus = Literal["completed", "open", "resolved"]


class VehicleMaintenance(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    vehicle_id: int = Field(foreign_key="vehicle.id", index=True)
    entry_type: str
    description: str
    service_date: date | None = None
    status: str
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    resolution_notes: str | None = None


class MaintenanceCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    entry_type: EntryType
    description: str = Field(min_length=3, max_length=500)
    service_date: date | None = None

    @field_validator("description")
    @classmethod
    def nonblank_description(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Describe the work or defect in at least three characters")
        return value


class MaintenanceResolve(SQLModel):
    model_config = ConfigDict(extra="forbid")

    resolution_notes: str = Field(min_length=3, max_length=500)

    @field_validator("resolution_notes")
    @classmethod
    def nonblank_notes(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Resolution notes are required")
        return value


class MaintenanceRead(SQLModel):
    id: int
    vehicle_id: int
    entry_type: EntryType
    description: str
    service_date: date | None
    status: EntryStatus
    reported_at: datetime
    resolved_at: datetime | None
    resolution_notes: str | None


def register_maintenance_routes(
    app: FastAPI, get_engine: Callable, require_staff: Callable
) -> None:
    """Keep REP-2B independent of REP-2A's inspection schema and endpoints."""
    router = APIRouter(prefix="/staff", tags=["Vehicle maintenance"])

    def vehicle_or_404(session: Session, vehicle_id: int) -> Vehicle:
        vehicle = session.get(Vehicle, vehicle_id)
        if vehicle is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return vehicle

    @router.get("/maintenance/vehicles", response_model=list[Vehicle],
                dependencies=[Depends(require_staff)])
    def staff_maintenance_vehicles():
        with Session(get_engine()) as session:
            return session.exec(select(Vehicle).order_by(Vehicle.make, Vehicle.model)).all()

    @router.get("/vehicles/{vehicle_id}/maintenance",
                response_model=list[MaintenanceRead], dependencies=[Depends(require_staff)])
    def get_vehicle_maintenance(vehicle_id: int):
        with Session(get_engine()) as session:
            vehicle_or_404(session, vehicle_id)
            return session.exec(
                select(VehicleMaintenance)
                .where(VehicleMaintenance.vehicle_id == vehicle_id)
                .order_by(VehicleMaintenance.reported_at.desc(), VehicleMaintenance.id.desc())
            ).all()

    @router.post("/vehicles/{vehicle_id}/maintenance",
                 response_model=MaintenanceRead, status_code=201,
                 dependencies=[Depends(require_staff)])
    def create_vehicle_maintenance(vehicle_id: int, payload: MaintenanceCreate):
        with Session(get_engine()) as session:
            vehicle_or_404(session, vehicle_id)
            record = VehicleMaintenance(
                vehicle_id=vehicle_id,
                entry_type=payload.entry_type,
                description=payload.description,
                service_date=payload.service_date,
                status="open" if payload.entry_type == "defect" else "completed",
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    @router.patch("/vehicles/{vehicle_id}/maintenance/{record_id}/resolve",
                  response_model=MaintenanceRead, dependencies=[Depends(require_staff)])
    def resolve_vehicle_defect(vehicle_id: int, record_id: int, payload: MaintenanceResolve):
        with Session(get_engine()) as session:
            vehicle_or_404(session, vehicle_id)
            record = session.get(VehicleMaintenance, record_id)
            if record is None or record.vehicle_id != vehicle_id:
                raise HTTPException(status_code=404, detail="Maintenance record not found")
            if record.entry_type != "defect":
                raise HTTPException(status_code=409, detail="Only defect records can be resolved")
            if record.status != "open":
                raise HTTPException(status_code=409, detail="Defect is already resolved")
            record.status = "resolved"
            record.resolved_at = datetime.now(timezone.utc)
            record.resolution_notes = payload.resolution_notes
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    app.include_router(router)
