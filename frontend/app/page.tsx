"use client";

import { useEffect, useState, type FormEvent } from "react";

type Vehicle = {
  id: number;
  make: string;
  model: string;
  category: string;
  daily_rate: number;
  available: boolean;
};

type Reservation = {
  id: number;
};

const API_URL = "http://localhost:8000";

export default function Home() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [vehicleId, setVehicleId] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [licenseExpiry, setLicenseExpiry] = useState("");
  const [pickupDate, setPickupDate] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/vehicles`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load vehicles");
        return response.json() as Promise<Vehicle[]>;
      })
      .then((data) => {
        const available = data.filter((vehicle) => vehicle.available);
        setVehicles(available);
        if (available.length > 0) setVehicleId(String(available[0].id));
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function reserve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");
    setSubmitting(true);

    try {
      const response = await fetch(`${API_URL}/reservations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehicle_id: Number(vehicleId),
          customer_name: customerName,
          driver_license_number: licenseNumber,
          driver_license_expiry: licenseExpiry,
          start_date: pickupDate,
          end_date: returnDate,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : "Reservation failed");
      }
      setMessage(`Reservation #${(result as Reservation).id} confirmed.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Reservation failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Hawk Rentals</h1>
      <h2>Reserve a vehicle</h2>
      <form onSubmit={reserve}>
        <p>
          <label>
            Vehicle:{" "}
            <select required value={vehicleId} onChange={(event) => setVehicleId(event.target.value)}>
              {vehicles.length === 0 && <option value="">No vehicles available</option>}
              {vehicles.map((vehicle) => (
                <option key={vehicle.id} value={vehicle.id}>
                  {vehicle.make} {vehicle.model} ({vehicle.category}) - ${vehicle.daily_rate}/day
                </option>
              ))}
            </select>
          </label>
        </p>
        <p>
          <label>
            Name: <input required value={customerName} onChange={(event) => setCustomerName(event.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Driver&apos;s licence number:{" "}
            <input required minLength={5} value={licenseNumber} onChange={(event) => setLicenseNumber(event.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Licence expiry:{" "}
            <input required type="date" value={licenseExpiry} onChange={(event) => setLicenseExpiry(event.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Pickup date:{" "}
            <input required type="date" value={pickupDate} onChange={(event) => setPickupDate(event.target.value)} />
          </label>
        </p>
        <p>
          <label>
            Return date:{" "}
            <input required type="date" value={returnDate} onChange={(event) => setReturnDate(event.target.value)} />
          </label>
        </p>
        <button type="submit" disabled={submitting || !vehicleId}>
          {submitting ? "Reserving..." : "Reserve"}
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
    </main>
  );
}
