"use client";

import { useEffect, useState, type FormEvent } from "react";
import VehicleCard from "./VehicleCard";

type VehicleStatus = "available" | "booked" | "unavailable";

type VehicleWithStatus = {
  id: number;
  make: string;
  model: string;
  category: string;
  daily_rate: number;
  available: boolean;
  status: VehicleStatus;
};

const API_URL = "http://localhost:8000";

export default function AvailabilityFilter() {
  const [pickupDate, setPickupDate] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [status, setStatus] = useState("");
  const [vehicles, setVehicles] = useState<VehicleWithStatus[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [searchedDates, setSearchedDates] = useState({ pickup: "", return: "" });

  async function loadVehicles(params: URLSearchParams) {
    setError("");
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/vehicles?${params}`);
      const result = await response.json();
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : "Could not load vehicles");
      }
      setVehicles(result as VehicleWithStatus[]);
      setSearchedDates({ pickup: params.get("start_date") ?? "", return: params.get("end_date") ?? "" });
    } catch (reason) {
      setVehicles([]);
      setError(reason instanceof Error ? reason.message : "Could not load vehicles");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadVehicles(new URLSearchParams());
  }, []);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (pickupDate || returnDate) {
      params.set("start_date", pickupDate);
      params.set("end_date", returnDate);
    }
    if (status) params.set("status", status);
    loadVehicles(params);
  }

  return (
    <section className="availability-section">
      <p className="eyebrow">THE RIGHT VEHICLE. THE RIGHT TIME.</p>
      <h2>Find your next drive.</h2>
      <p>Leave the dates empty to see each vehicle&apos;s status for today.</p>
      <form className="search-form" onSubmit={search}>
        <p>
          <label>
            Pickup date:{" "}
            <input type="date" required={Boolean(returnDate)} value={pickupDate} onChange={(event) => setPickupDate(event.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Return date:{" "}
            <input type="date" required={Boolean(pickupDate)} value={returnDate} onChange={(event) => setReturnDate(event.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Show:{" "}
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All vehicles</option>
              <option value="available">Available only</option>
              <option value="booked">Booked only</option>
              <option value="unavailable">Out of service only</option>
            </select>
          </label>
        </p>
        <button type="submit" disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>
      {loading && <p role="status">Finding your next drive…</p>}
      {error && <p role="alert">{error}</p>}
      {!error && !loading && vehicles.length === 0 && <p role="status">No vehicles match this filter.</p>}
      {vehicles.length > 0 && <><div className="fleet-results"><span>{vehicles.length} vehicles to explore</span><a className="text-link" href="/photo-credits">About the photos</a></div><div className="vehicle-grid">{vehicles.map((vehicle) => <VehicleCard key={vehicle.id} vehicle={vehicle} pickupDate={searchedDates.pickup} returnDate={searchedDates.return} />)}</div></>}
    </section>
  );
}
