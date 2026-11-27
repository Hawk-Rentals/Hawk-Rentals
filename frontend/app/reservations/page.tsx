"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Reservation = {
  id: number;
  vehicle_id: number;
  customer_name: string;
  start_date: string;
  end_date: string;
  status: "confirmed" | "cancelled";
};

type Vehicle = { id: number; make: string; model: string; available: boolean };

function displayDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric",
  });
}

export default function ManageReservation() {
  const [bookingId, setBookingId] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [reservation, setReservation] = useState<Reservation | null>(null);
  const [loadedCode, setLoadedCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [editing, setEditing] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const canEdit = reservation?.status === "confirmed" && new Date(`${reservation.start_date}T00:00:00`) > today;
  const bookedVehicle = vehicles.find((vehicle) => vehicle.id === reservation?.vehicle_id);
  const selectableVehicles = vehicles.filter((vehicle) => vehicle.available);

  useEffect(() => {
    // Fragments keep the private code out of server request URLs and logs.
    const [id, code] = window.location.hash.slice(1).split(":");
    if (id && code) {
      setBookingId(id);
      setAccessCode(code);
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  async function lookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    setReservation(null);
    setEditing(false);
    try {
      const response = await fetch(`${API_URL}/reservations/${bookingId}`, {
        headers: { "X-Booking-Token": accessCode.trim() }, cache: "no-store",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Could not find this reservation.");
      setReservation(result);
      setLoadedCode(accessCode.trim());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load your reservation. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function startEditing() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/vehicles`, { cache: "no-store" });
      if (!response.ok) throw new Error("Could not load vehicles. Please try again.");
      setVehicles(await response.json());
      setEditing(true);
    } catch {
      setError("Could not load vehicles. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function saveChanges(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reservation || busy) return;
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/reservations/${reservation.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Booking-Token": loadedCode },
        body: JSON.stringify({ ...fields, vehicle_id: Number(fields.vehicle_id) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Check the booking details and try again.");
      setReservation(result);
      setEditing(false);
      setMessage(`Reservation #${result.id} has been updated and confirmed. You can keep using your existing access code.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update your reservation. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!reservation || busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/reservations/${reservation.id}/cancel`, {
        method: "POST", headers: { "X-Booking-Token": loadedCode },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Cancellation failed.");
      setReservation(result);
      setMessage(`Reservation #${result.id} has been cancelled. It no longer holds the vehicle for these dates.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not cancel your reservation. Please try again.");
    } finally {
      setBusy(false);
      dialog.current?.close();
    }
  }

  return (
    <main className="manage-page">
      <p className="eyebrow">YOUR JOURNEY, YOUR PLANS</p>
      <h1>Manage your booking.</h1>
      <p className="muted">Find your reservation to view the details, edit an upcoming trip, or cancel it.</p>
      <form className="booking-lookup" onSubmit={lookup}>
        <label>Booking number<input required type="number" min="1" step="1" value={bookingId} onChange={(event) => setBookingId(event.target.value)} /></label>
        <label>Access code<input required type="password" autoComplete="off" value={accessCode} onChange={(event) => setAccessCode(event.target.value)} /></label>
        <button disabled={busy}>{busy ? "Please wait..." : "Find my booking"}</button>
      </form>
      <p className="muted">Use the number and private access code shown when you reserved your vehicle.</p>
      {error && !editing && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {reservation && (
        <section className="booking-card" aria-label="Reservation details">
          <div className="booking-heading"><h2>Reservation #{reservation.id}</h2><span className={`status status-${reservation.status === "confirmed" ? "available" : "unavailable"}`}>{reservation.status === "confirmed" ? "Confirmed" : "Cancelled"}</span></div>
          <dl className="booking-details">
            <div><dt>Customer</dt><dd>{reservation.customer_name}</dd></div>
            <div><dt>Vehicle</dt><dd>{bookedVehicle && `${bookedVehicle.make} ${bookedVehicle.model} `}#{reservation.vehicle_id}</dd></div>
            <div><dt>Pickup date</dt><dd>{displayDate(reservation.start_date)}</dd></div>
            <div><dt>Return date</dt><dd>{displayDate(reservation.end_date)}</dd></div>
          </dl>
          {editing ? (
            <form aria-label="Edit reservation" onSubmit={saveChanges}>
              <h3>Edit reservation</h3>
              <p className="muted">Availability is checked when you save. Re-enter your driver&apos;s licence details so we can check them against your updated dates.</p>
              {error && <p role="alert">{error}</p>}
              {selectableVehicles.length === 0 && <p role="status">There are no vehicles available to select right now.</p>}
              <fieldset className="booking-edit-fields" disabled={busy}>
                <label>Customer name<input name="customer_name" defaultValue={reservation.customer_name} required /></label>
                <label>Vehicle
                  <select name="vehicle_id" defaultValue={reservation.vehicle_id} required>
                    {!bookedVehicle?.available && <option value={reservation.vehicle_id} disabled>Current vehicle #{reservation.vehicle_id} (unavailable)</option>}
                    {selectableVehicles.map((vehicle) => (
                      <option key={vehicle.id} value={vehicle.id}>{vehicle.make} {vehicle.model} #{vehicle.id}</option>
                    ))}
                  </select>
                </label>
                <label>Pickup date<input name="start_date" type="date" defaultValue={reservation.start_date} required /></label>
                <label>Return date<input name="end_date" type="date" defaultValue={reservation.end_date} required /></label>
                <label>Driver&apos;s licence number<input name="driver_license_number" minLength={5} autoComplete="off" required /></label>
                <label>Driver&apos;s licence expiry<input name="driver_license_expiry" type="date" required /></label>
              </fieldset>
              <div className="dialog-actions">
                <button type="submit" disabled={busy || selectableVehicles.length === 0}>{busy ? "Saving..." : "Save changes"}</button>
                <button type="button" className="secondary-button" disabled={busy} onClick={() => { setEditing(false); setError(""); }}>Discard changes</button>
              </div>
            </form>
          ) : reservation.status === "confirmed" ? (
            <>
              <p className="muted">Online changes and cancellation are available before the pickup date.</p>
              <div className="dialog-actions">
                {canEdit && <button disabled={busy} onClick={startEditing}>Edit reservation</button>}
                <button className="danger-button" disabled={busy} onClick={() => dialog.current?.showModal()}>Cancel reservation</button>
              </div>
            </>
          ) : <p>This reservation is cancelled. <Link className="text-link" href="/#availability">Find your next drive</Link></p>}
        </section>
      )}
      <dialog ref={dialog} className="cancel-dialog" aria-labelledby="cancel-title" aria-describedby="cancel-description" onCancel={(event) => { if (busy) event.preventDefault(); }}>
        <h2 id="cancel-title">Cancel this reservation?</h2>
        <p id="cancel-description">Reservation #{reservation?.id} will be marked cancelled and its vehicle will be released for these dates. This cannot be undone.</p>
        <div className="dialog-actions"><button autoFocus className="secondary-button" disabled={busy} onClick={() => dialog.current?.close()}>Keep reservation</button><button className="danger-button" disabled={busy} onClick={cancel}>{busy ? "Cancelling..." : "Yes, cancel reservation"}</button></div>
      </dialog>
    </main>
  );
}
