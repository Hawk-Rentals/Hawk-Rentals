"use client";

import { useState } from "react";
import photos from "./vehiclePhotos.json";

type Vehicle = {
  id: number;
  make: string;
  model: string;
  category: string;
  daily_rate: number;
  available: boolean;
  status?: string;
};

export function VehiclePhoto({ make, model }: { make: string; model: string }) {
  const [failed, setFailed] = useState(false);
  const photo = photos.find((item) => item.vehicle.toLowerCase() === `${make} ${model}`.toLowerCase());
  return (
    <div className="vehicle-photo">
      {photo && !failed ? <img src={photo.src} alt={`${make} ${model}`} width={960} height={600} loading="lazy" onError={() => setFailed(true)} /> : <div className="vehicle-photo-placeholder"><span aria-hidden="true">↗</span><span>{make} {model}</span><small>Photo coming soon</small></div>}
    </div>
  );
}

export default function VehicleCard({ vehicle, pickupDate = "", returnDate = "" }: { vehicle: Vehicle; pickupDate?: string; returnDate?: string }) {
  const status = vehicle.status ?? (vehicle.available ? "available" : "unavailable");
  const params = new URLSearchParams({ vehicle: String(vehicle.id) });
  if (pickupDate && returnDate) {
    params.set("pickup", pickupDate);
    params.set("return", returnDate);
  }
  return (
    <article className="vehicle-card">
      <div className="vehicle-card-image"><VehiclePhoto make={vehicle.make} model={vehicle.model} /><span className={`status status-${status}`}>{status === "available" ? "Available" : status === "booked" ? "Booked" : "Out of service"}</span></div>
      <div className="vehicle-card-body">
        <p className="vehicle-category">{vehicle.category}</p>
        <h3>{vehicle.make} {vehicle.model}</h3>
        <div className="vehicle-card-bottom"><p className="vehicle-price">${vehicle.daily_rate.toFixed(0)}<span> / day</span></p>{vehicle.available && <a className="vehicle-book" href={`/?${params}#reserve`} aria-label={`Choose ${vehicle.make} ${vehicle.model}`}>{status === "booked" ? "Other dates" : "Choose car"} <span aria-hidden="true">↗</span></a>}</div>
      </div>
    </article>
  );
}
