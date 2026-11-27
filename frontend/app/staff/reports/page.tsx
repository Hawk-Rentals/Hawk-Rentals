"use client";

/**
 * REP-1A: Fleet Utilization Summary (staff only).
 *
 * Flow:
 *   1. Staff enter their API key (same key as /staff and /staff/maintenance).
 *   2. Pick a date range (defaults to the last 30 days, ending today).
 *   3. "Generate report" calls GET /staff/reports/utilization and shows:
 *        - three summary cards (fleet %, booked vs available days, idle cars)
 *        - a per-category table
 *        - a per-vehicle table sorted busiest first, with a small usage bar
 *
 * Styling reuses the REP-2B "maintenance-*" classes from globals.css so the
 * staff pages look consistent and this story does not need to edit the CSS.
 */
import { useState, type FormEvent } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types mirror the FastAPI response models in backend/fleet_utilization.py
// ---------------------------------------------------------------------------
type Totals = {
  vehicle_count: number;
  booked_days: number;
  available_days: number;
  utilization_pct: number;
  idle_vehicle_count: number;
};

type CategoryRow = Totals & { category: string };

type VehicleRow = {
  vehicle_id: number;
  make: string;
  model: string;
  category: string;
  archived: boolean;
  reservation_count: number;
  booked_days: number;
  available_days: number;
  utilization_pct: number;
};

type Report = {
  start_date: string;
  end_date: string;
  period_days: number;
  fleet: Totals;
  categories: CategoryRow[];
  vehicles: VehicleRow[];
};

/** Format a Date as YYYY-MM-DD in local time (what <input type="date"> expects). */
function toInputDate(value: Date) {
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${value.getFullYear()}-${month}-${day}`;
}

/** Default window: the 30 days ending today (matches the backend default). */
function defaultRange() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 29);
  return { start: toInputDate(start), end: toInputDate(end) };
}

/** Turn a FastAPI error body ({ detail: ... }) into a readable message. */
async function parseResponse(response: Response) {
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let reason = "Request failed";
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      reason = typeof detail === "string" ? detail : JSON.stringify(detail);
    }
    throw new Error(reason);
  }
  return data;
}

/** Small horizontal bar so busy vs idle cars stand out at a glance. */
function UsageBar({ pct }: { pct: number }) {
  return (
    <div
      aria-hidden="true"
      style={{ background: "#edf0e7", borderRadius: 20, height: 8, width: 120, overflow: "hidden" }}
    >
      <div style={{ background: "#9fbf45", height: "100%", width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

// Inline layout for the three summary cards (kept here to avoid editing globals.css).
const cardGrid = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 } as const;
const card = { border: "1px solid var(--line)", borderRadius: 10, padding: 18 } as const;
const bigNumber = { fontFamily: "'Space Grotesk', Arial, sans-serif", fontSize: 34, fontWeight: 700, margin: "4px 0" } as const;

export default function FleetUtilizationPage() {
  const initial = defaultRange();
  const [staffKey, setStaffKey] = useState("");
  const [startDate, setStartDate] = useState(initial.start);
  const [endDate, setEndDate] = useState(initial.end);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function generateReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!staffKey.trim()) {
      setError("Enter your staff API key first.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      // URLSearchParams handles the query-string encoding for us.
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
        include_archived: String(includeArchived),
      });
      const response = await fetch(`${API_URL}/staff/reports/utilization?${params}`, {
        headers: { "X-Staff-Key": staffKey },
        cache: "no-store", // always show live reservation data
      });
      setReport((await parseResponse(response)) as Report);
    } catch (reason) {
      setReport(null);
      setError(reason instanceof Error ? reason.message : "Could not load the report");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="maintenance-page">
      <p><Link className="text-link" href="/staff">← Back to fleet management</Link></p>
      <p className="eyebrow">STAFF REPORTS · REP-1A</p>
      <h1>Fleet utilization summary.</h1>
      <p className="muted">
        See how much of the fleet was rented over a period. Utilization is booked days divided by
        days in the period. Cancelled reservations are excluded.
      </p>

      {/* ---- Inputs ---- */}
      <section className="maintenance-panel">
        <h2>Report period</h2>
        <form onSubmit={generateReport}>
          <div className="maintenance-grid">
            <label className="maintenance-wide">Staff API key
              <input type="password" autoComplete="off" value={staffKey}
                onChange={(event) => setStaffKey(event.target.value)}
                placeholder="Same key as fleet management" />
            </label>
            <label>Start date
              <input type="date" required value={startDate} max={endDate}
                onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label>End date (inclusive)
              <input type="date" required value={endDate} min={startDate}
                onChange={(event) => setEndDate(event.target.value)} />
            </label>
          </div>
          <div className="maintenance-actions">
            <label style={{ flexDirection: "row", alignItems: "center" }}>
              <input type="checkbox" checked={includeArchived}
                onChange={(event) => setIncludeArchived(event.target.checked)} />
              Include archived vehicles
            </label>
            <button type="submit" disabled={loading || !staffKey.trim()}>
              {loading ? "Loading..." : "Generate report"}
            </button>
          </div>
        </form>
      </section>

      {error && <p role="alert">{error}</p>}

      {report && (
        <>
          {/* ---- Summary cards ---- */}
          <section className="maintenance-panel">
            <h2>{report.start_date} to {report.end_date} ({report.period_days} days)</h2>
            <div style={cardGrid}>
              <div style={card}>
                <span className="eyebrow">FLEET UTILIZATION</span>
                <p style={bigNumber}>{report.fleet.utilization_pct}%</p>
                <span className="muted">{report.fleet.vehicle_count} vehicles in report</span>
              </div>
              <div style={card}>
                <span className="eyebrow">BOOKED DAYS</span>
                <p style={bigNumber}>{report.fleet.booked_days}</p>
                <span className="muted">of {report.fleet.available_days} vehicle-days available</span>
              </div>
              <div style={card}>
                <span className="eyebrow">IDLE VEHICLES</span>
                <p style={bigNumber}>{report.fleet.idle_vehicle_count}</p>
                <span className="muted">no bookings in this period</span>
              </div>
            </div>
          </section>

          {/* ---- By category ---- */}
          <section className="maintenance-panel">
            <h2>By category</h2>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr><th>Category</th><th>Vehicles</th><th>Booked / available days</th><th>Idle</th><th>Utilization</th></tr>
                </thead>
                <tbody>
                  {report.categories.map((row) => (
                    <tr key={row.category}>
                      <td style={{ textTransform: "capitalize" }}>{row.category}</td>
                      <td>{row.vehicle_count}</td>
                      <td>{row.booked_days} / {row.available_days}</td>
                      <td>{row.idle_vehicle_count}</td>
                      <td>{row.utilization_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ---- By vehicle (busiest first, sorted by the backend) ---- */}
          <section className="maintenance-panel">
            <h2>By vehicle</h2>
            {report.vehicles.length === 0 && <p className="muted">No vehicles match this report.</p>}
            <div className="table-scroll">
              <table>
                <thead>
                  <tr><th>Vehicle</th><th>Category</th><th>Bookings</th><th>Booked days</th><th>Utilization</th></tr>
                </thead>
                <tbody>
                  {report.vehicles.map((row) => (
                    <tr key={row.vehicle_id}>
                      <td>#{row.vehicle_id} · {row.make} {row.model}{row.archived ? " (archived)" : ""}</td>
                      <td>{row.category}</td>
                      <td>{row.reservation_count}</td>
                      <td>{row.booked_days} / {row.available_days}</td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <UsageBar pct={row.utilization_pct} />
                          {row.utilization_pct}%
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
