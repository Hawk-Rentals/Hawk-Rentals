"""Run explicitly to add missing demo cars to an existing database."""

from sqlmodel import Session, select

from main import INITIAL_VEHICLES, engine, migrate_existing_database
from models import SQLModel, Vehicle


def add_missing_demo_vehicles():
    SQLModel.metadata.create_all(engine)
    migrate_existing_database()
    with Session(engine) as session:
        # Include archived cars so this never reintroduces a removed vehicle.
        existing = {(v.make.casefold(), v.model.casefold()) for v in session.exec(select(Vehicle)).all()}
        added = 0
        for data in INITIAL_VEHICLES:
            key = (data["make"].casefold(), data["model"].casefold())
            if key not in existing:
                session.add(Vehicle(**data))
                existing.add(key)
                added += 1
        session.commit()
    return added


if __name__ == "__main__":
    print(f"Added {add_missing_demo_vehicles()} demo vehicles. Existing vehicles were preserved.")
