"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STORAGE_KEY = "hawk-rentals-history-access-v1";

type SavedBooking = { id: number; token: string };
type HistoryItem = {
  id: number;
  vehicle_id: number;
  vehicle_make: string;
  vehicle_model: string;
  customer_name: string;
  start_date: string;
  end_date: string;
  status: "confirmed" | "cancelled";
  rental_state: "upcoming" | "ongoing" | "completed" | "cancelled";
  booked_daily_rate: number | null;
  original_total: number | null;
};

const money = (amount: number) => new Intl.NumberFormat("en-CA", {
  style: "currency", currency: "CAD",
}).format(amount);

const dateLabel = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("en-CA", {
    month: "short", day: "numeric", year: "numeric",
  });

function loadSavedBookings(): SavedBooking[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(raw)) return [];
    return raw.filter((item): item is SavedBooking =>
      typeof item?.id === "number" && Number.isSafeInteger(item.id) &&
      item.id > 0 && typeof item.token === "string" && item.token.length > 0);
  } catch {
    return [];
  }
}

export default function RentalHistoryPage() {
  const [saved, setSaved] = useState<SavedBooking[]>([]);
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [bookingId, setBookingId] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [unavailableIds, setUnavailableIds] = useState<number[]>([]);

  async function lookup(booking: SavedBooking): Promise<HistoryItem> {
    const response = await fetch(`${API_URL}/reservations/${booking.id}/history`, {
      headers: { "X-Booking-Token": booking.token },
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Booking not found or access code is invalid.");
    return response.json() as Promise<HistoryItem>;
  }

  async function refresh(records: SavedBooking[]) {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled(records.map(lookup));
    const visible: HistoryItem[] = [];
    const inaccessible: number[] = [];
    results.forEach((result, index) => {
      if (result.status === "fulfilled") visible.push(result.value);
      else inaccessible.push(records[index].id);
    });
    visible.sort((a, b) => b.start_date.localeCompare(a.start_date) || b.id - a.id);
    setItems(visible);
    setUnavailableIds(inaccessible);
    setLoading(false);
  }

  useEffect(() => {
    const stored = loadSavedBookings();
    setSaved(stored);
    void refresh(stored);
  }, []);

  function saveRecords(records: SavedBooking[]) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    setSaved(records);
  }

  async function addBooking(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    const record = { id: Number(bookingId), token: accessCode.trim() };
    try {
      if (!Number.isSafeInteger(record.id) || record.id <= 0 || !record.token) {
        throw new Error("Enter a valid booking number and access code.");
      }
      await lookup(record);
      const next = [...saved.filter((entry) => entry.id !== record.id), record];
      saveRecords(next);
      setBookingId("");
      setAccessCode("");
      setNotice("Booking verified and saved on this device.");
      await refresh(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not verify booking.");
    } finally {
      setBusy(false);
    }
  }

  async function removeBooking(id: number) {
    const next = saved.filter((entry) => entry.id !== id);
    try {
      saveRecords(next);
      await refresh(next);
      setNotice("Booking access removed from this device. The reservation itself was not changed.");
    } catch {
      setError("Could not update saved booking details in this browser.");
    }
  }

  const countCompleted = items.filter((item) => item.rental_state === "completed").length;

  return (
    <main className="history-page">
      <p className="eyebrow">YOUR DRIVES, ALL IN ONE PLACE</p>
      <h1>Your rental history.</h1>
      <p className="muted">
        View past trips, upcoming reservations, and cancellations for bookings you have
        securely added to this browser. No customer account is required.
      </p>
      <section className="history-panel">
        <h2>Add a booking</h2>
        <p className="muted">Enter the booking number and private access code from your confirmation.
          Only verified bookings can be displayed.</p>
        <form className="history-form" onSubmit={addBooking}>
          <label>Booking number
            <input type="number" min="1" step="1" required value={bookingId}
              onChange={(event) => setBookingId(event.target.value)} />
          </label>
          <label>Private access code
            <input type="password" autoComplete="off" required value={accessCode}
              onChange={(event) => setAccessCode(event.target.value)} />
          </label>
          <button disabled={busy}>{busy ? "Verifying..." : "Add to my history"}</button>
        </form>
        <p className="history-note">Your access codes are kept in this browser's local storage.
          Use only a personal device. Clear any saved booking using Remove below.
          Bookings created before access codes were introduced cannot be imported.</p>
      </section>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {loading ? <p>Loading your saved bookings...</p> : (
        <>
          <p className="history-summary">{items.length} verified bookings · {countCompleted} completed trips</p>
          {items.length === 0 && (
            <section className="history-panel">
              <h2>No rental history yet</h2>
              <p className="muted">Add a booking above, or <Link className="text-link" href="/#reserve">
                make your first reservation</Link>.</p>
            </section>
          )}
          {items.map((item) => (
            <section className="history-card" key={item.id} aria-label={`Booking ${item.id}`}>
              <div className="history-card-heading">
                <div>
                  <p className="eyebrow">RESERVATION #{item.id}</p>
                  <h2>{item.vehicle_make} {item.vehicle_model}</h2>
                </div>
                <span className={`status status-${item.rental_state === "completed" ? "available" :
                    item.rental_state === "cancelled" ? "unavailable" : "booked"}`}>
                  {item.rental_state === "ongoing" ? "In progress" :
                   item.rental_state.charAt(0).toUpperCase() + item.rental_state.slice(1)}
                </span>
              </div>
              <dl className="history-details">
                <div><dt>Customer</dt><dd>{item.customer_name}</dd></div>
                <div><dt>Pickup</dt><dd>{dateLabel(item.start_date)}</dd></div>
                <div><dt>Return</dt><dd>{dateLabel(item.end_date)}</dd></div>
                <div><dt>Original booking estimate</dt>
                  <dd>{item.original_total == null ? "Not recorded" : money(item.original_total)}</dd>
                </div>
              </dl>
              <p className="history-note">
                {item.rental_state === "cancelled"
                  ? "Cancelled booking. The original estimate is not an amount charged or refunded."
                  : "Estimated original rental cost only; payments and refunds are not supported."}
              </p>
              <div className="history-actions">
                {item.rental_state === "upcoming" && <Link className="text-link" href="/reservations">
                  Manage or cancel booking</Link>}
                <button type="button" className="secondary-button"
                  onClick={() => void removeBooking(item.id)}>Remove from this device</button>
              </div>
            </section>
          ))}
          {unavailableIds.length > 0 && (
            <p role="alert">Could not load {unavailableIds.length} saved booking(s).
              They may have invalid access codes or the server may be unavailable.
              Your saved details were not deleted.</p>
          )}
        </>
      )}
    </main>
  );
}
