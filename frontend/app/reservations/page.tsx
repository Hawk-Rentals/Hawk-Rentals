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
  const dialog = useRef<HTMLDialogElement>(null);

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
      <p className="muted">Plans change. Find your reservation below to view the details or cancel an upcoming trip.</p>
      <form className="booking-lookup" onSubmit={lookup}>
        <label>Booking number<input required type="number" min="1" step="1" value={bookingId} onChange={(event) => setBookingId(event.target.value)} /></label>
        <label>Access code<input required type="password" autoComplete="off" value={accessCode} onChange={(event) => setAccessCode(event.target.value)} /></label>
        <button disabled={busy}>{busy ? "Please wait..." : "Find my booking"}</button>
      </form>
      <p className="muted">Use the number and private access code shown when you reserved your vehicle.</p>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {reservation && (
        <section className="booking-card" aria-label="Reservation details">
          <div className="booking-heading"><h2>Reservation #{reservation.id}</h2><span className={`status status-${reservation.status === "confirmed" ? "available" : "unavailable"}`}>{reservation.status === "confirmed" ? "Confirmed" : "Cancelled"}</span></div>
          <dl className="booking-details">
            <div><dt>Customer</dt><dd>{reservation.customer_name}</dd></div>
            <div><dt>Vehicle number</dt><dd>#{reservation.vehicle_id}</dd></div>
            <div><dt>Pickup date</dt><dd>{displayDate(reservation.start_date)}</dd></div>
            <div><dt>Return date</dt><dd>{displayDate(reservation.end_date)}</dd></div>
          </dl>
          {reservation.status === "confirmed" ? <><p className="muted">Online cancellation is available before the pickup date. Reservations starting today or earlier cannot be cancelled here.</p><button className="danger-button" disabled={busy} onClick={() => dialog.current?.showModal()}>Cancel reservation</button></> : <p>This reservation is cancelled. <Link className="text-link" href="/#availability">Find your next drive</Link></p>}
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
