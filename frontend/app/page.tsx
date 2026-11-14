"use client";

import { useEffect, useState, type FormEvent } from "react";

import AvailabilityFilter from "./AvailabilityFilter";
import Link from "next/link";
import { VehiclePhoto } from "./VehicleCard";

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
  management_token: string;
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
  const [confirmation, setConfirmation] = useState<Reservation | null>(null);
  const [savedNotice, setSavedNotice] = useState("");
  const selectedVehicle = vehicles.find((vehicle) => String(vehicle.id) === vehicleId);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("pickup")) setPickupDate(params.get("pickup")!);
    if (params.get("return")) setReturnDate(params.get("return")!);
    fetch(`${API_URL}/vehicles`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load vehicles");
        return response.json() as Promise<Vehicle[]>;
      })
      .then((data) => {
        const available = data.filter((vehicle) => vehicle.available);
        setVehicles(available);
        if (available.length > 0) {
          const selected = available.find((vehicle) => String(vehicle.id) === params.get("vehicle"));
          setVehicleId(String((selected ?? available[0]).id));
        }
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function reserve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setConfirmation(null);
    setSavedNotice("");
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
      setConfirmation(result as Reservation);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Reservation failed");
    } finally {
      setSubmitting(false);
    }
  }

  function rememberBooking() {
    if (!confirmation) return;
    try {
      const key = "hawk-rentals-history-access-v1";
      const previous = JSON.parse(localStorage.getItem(key) ?? "[]");
      const valid = Array.isArray(previous) ? previous.filter((entry) => entry &&
        Number.isSafeInteger(entry.id) && typeof entry.token === "string" &&
        entry.id !== confirmation.id) : [];
      valid.push({ id: confirmation.id, token: confirmation.management_token });
      localStorage.setItem(key, JSON.stringify(valid));
      setSavedNotice("Saved to rental history on this device. Do not use this on a shared computer.");
    } catch {
      setSavedNotice("This browser could not save the booking. Keep your access code instead.");
    }
  }

  return (
    <main>
      <section className="hero">
        <div className="hero-copy"><p className="eyebrow">YOUR PLANS. YOUR PACE.</p><h1>Your next move.<br /><span>A better drive.</span></h1><p className="hero-description">The everyday commute. The weekend escape. Find the right vehicle for wherever life takes you.</p><a className="button" href="#availability">Find your drive <span aria-hidden="true">↗</span></a></div>
        <div className="hero-art" aria-hidden="true"><span className="road-line" /><span className="hero-word">GO.</span><div className="road-caption">A LITTLE FREEDOM.<br />A LOT OF POSSIBILITY.</div><span className="compass">↗</span></div>
        <div className="hero-bottom"><span>01 / THE OPEN ROAD IS CALLING</span><span>COMPACT · SUV · SPORTS</span></div>
      </section>
      <div className="intro-strip"><span>Made for your kind of journey.</span><span>Everyday essentials</span><span>Room to explore</span><span>Something more exciting ↗</span></div>
      <div id="availability">
      <AvailabilityFilter />
      </div>
      <section id="reserve" className="reservation-section"><div className="reservation-intro"><p className="eyebrow">LET’S GET YOU MOVING</p><h2>One step closer<br />to your next trip.</h2><p>Choose your vehicle, add your details, and reserve your drive.</p><span className="reservation-arrow" aria-hidden="true">↗</span></div><div className="reservation-panel"><h2>Reserve a vehicle</h2><p className="muted">Your next journey starts with the details.</p>
      <form className="reservation-form" onSubmit={reserve}>
        {selectedVehicle && <div className="selected-vehicle-photo"><VehiclePhoto make={selectedVehicle.make} model={selectedVehicle.model} /></div>}
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
      {confirmation && <div className="booking-access"><h3>Keep your booking details</h3><p>Save this access code to view or cancel your reservation. Treat it like a password.</p><label>Booking access code<input readOnly value={confirmation.management_token} onFocus={(event) => event.target.select()} /></label><Link className="button" href={`/reservations#${confirmation.id}:${confirmation.management_token}`}>Manage reservation</Link><button type="button" onClick={rememberBooking}>Save to rental history on this device</button><Link className="text-link" href="/history">View rental history</Link>{savedNotice && <p role="status">{savedNotice}</p>}</div>}
      </div></section>
    </main>
  );
}
