"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Vehicle = {
  id: number;
  make: string;
  model: string;
  archived: boolean;
  available: boolean;
};

type MaintenanceEntry = {
  id: number;
  vehicle_id: number;
  entry_type: "maintenance" | "defect";
  description: string;
  service_date: string | null;
  status: "completed" | "open" | "resolved";
  reported_at: string;
  resolved_at: string | null;
  resolution_notes: string | null;
};

type Inspection = {
  id: number;
  vehicle_id: number;
  fuel_level?: string | number | null;
  mileage?: number | null;
  condition?: string | null;
  notes?: string | null;
  inspected_at?: string | null;
  created_at?: string | null;
};

function formatDate(value: string | null) {
  if (!value) return "Not supplied";
  const parsed = new Date(value.includes("T") ? value : value + "T12:00:00");
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleDateString("en-CA", {
    year: "numeric", month: "short", day: "numeric",
  });
}

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

export default function MaintenanceHistoryPage() {
  const [staffKey, setStaffKey] = useState("");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [vehicleId, setVehicleId] = useState("");
  const [entries, setEntries] = useState<MaintenanceEntry[]>([]);
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [inspectionNote, setInspectionNote] = useState("");
  const [type, setType] = useState<"maintenance" | "defect">("maintenance");
  const [description, setDescription] = useState("");
  const [serviceDate, setServiceDate] = useState("");
  const [resolving, setResolving] = useState<number | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);

  const auth = { "X-Staff-Key": staffKey };
  const vehicle = vehicles.find((item) => String(item.id) === vehicleId);

  async function loadVehicles() {
    if (!staffKey.trim()) {
      setError("Enter your staff API key first.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/staff/maintenance/vehicles`, {
        headers: auth, cache: "no-store",
      });
      const result = await parseResponse(response);
      if (!Array.isArray(result)) throw new Error("Invalid vehicle response");
      setVehicles(result as Vehicle[]);
      if (!vehicleId && result.length > 0) setVehicleId(String(result[0].id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load fleet");
    } finally {
      setLoading(false);
    }
  }

  async function loadHistory(id: string) {
    if (!staffKey.trim() || !id) return;
    setError("");
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/staff/vehicles/${id}/maintenance`, {
        headers: auth, cache: "no-store",
      });
      const result = await parseResponse(response);
      if (!Array.isArray(result)) throw new Error("Invalid maintenance response");
      setEntries(result as MaintenanceEntry[]);
      // REP-2A is maintained separately. Attempt its inspection endpoint only
      // when one exists; absence must never prevent maintenance history loading.
      const possiblePaths = [
        `/staff/vehicles/${id}/inspections`,
        `/vehicles/${id}/inspections`,
      ];
      let found = false;
      for (const path of possiblePaths) {
        const inspectionResponse = await fetch(API_URL + path, {
          headers: auth, cache: "no-store",
        });
        if (inspectionResponse.status === 404 || inspectionResponse.status === 405) continue;
        if (!inspectionResponse.ok) {
          setInspectionNote("Inspection history is not available through the current API.");
          break;
        }
        const inspectionsResult: unknown = await inspectionResponse.json();
        if (Array.isArray(inspectionsResult)) {
          setInspections(inspectionsResult as Inspection[]);
          setInspectionNote("");
          found = true;
        }
        break;
      }
      if (!found) {
        setInspections([]);
        setInspectionNote("Inspection history will appear when REP-2A is integrated.");
      }
    } catch (reason) {
      setEntries([]);
      setInspections([]);
      setError(reason instanceof Error ? reason.message : "Could not load maintenance history");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setEntries([]);
    setInspections([]);
    setNotice("");
  }, [vehicleId]);

  async function createEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vehicleId || !staffKey) return;
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/staff/vehicles/${vehicleId}/maintenance`, {
        method: "POST",
        headers: { ...auth, "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_type: type,
          description,
          service_date: serviceDate || null,
        }),
      });
      await parseResponse(response);
      setDescription("");
      setServiceDate("");
      setNotice(type === "defect" ? "Defect recorded as open." : "Maintenance activity recorded.");
      await loadHistory(vehicleId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save record");
    } finally {
      setBusy(false);
    }
  }

  async function resolveEntry(record: MaintenanceEntry) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const response = await fetch(
        `${API_URL}/staff/vehicles/${vehicleId}/maintenance/${record.id}/resolve`,
        {
          method: "PATCH",
          headers: { ...auth, "Content-Type": "application/json" },
          body: JSON.stringify({ resolution_notes: resolutionNotes }),
        },
      );
      await parseResponse(response);
      setResolving(null);
      setResolutionNotes("");
      setNotice("Defect marked resolved; the record remains in history.");
      await loadHistory(vehicleId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not resolve defect");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="maintenance-page">
      <p><Link className="text-link" href="/staff">← Back to fleet management</Link></p>
      <p className="eyebrow">STAFF OPERATIONS · REP-2B</p>
      <h1>Vehicle maintenance history.</h1>
      <p className="muted">Track completed work, reported defects, and defect resolutions. Previous records are retained for audit and upkeep.</p>

      <section className="maintenance-panel">
        <h2>Staff access and vehicle</h2>
        <div className="maintenance-grid">
          <label>Staff API key
            <input type="password" autoComplete="off" value={staffKey}
              onChange={(event) => setStaffKey(event.target.value)}
              placeholder="Same key as fleet management" />
          </label>
          <label>Vehicle
            <select value={vehicleId} onChange={(event) => setVehicleId(event.target.value)}>
              <option value="">Select a vehicle</option>
              {vehicles.map((item) => (
                <option key={item.id} value={String(item.id)}>
                  #{item.id} · {item.make} {item.model}{item.archived ? " (archived)" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="maintenance-actions">
          <button type="button" disabled={loading || !staffKey.trim()} onClick={() => void loadVehicles()}>
            {loading ? "Loading..." : "Load vehicles"}
          </button>
          <button type="button" className="secondary-button" disabled={loading || !vehicleId || !staffKey.trim()}
            onClick={() => void loadHistory(vehicleId)}>Refresh history</button>
        </div>
      </section>

      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      {vehicle && (
        <>
          <section className="maintenance-panel">
            <h2>Log an activity for {vehicle.make} {vehicle.model}</h2>
            <p className="muted">Maintenance is completed work; defects remain open until a staff member records their resolution.</p>
            <form onSubmit={createEntry} className="maintenance-form">
              <label>Record type
                <select value={type} onChange={(event) => setType(event.target.value as "maintenance" | "defect")}>
                  <option value="maintenance">Maintenance activity</option>
                  <option value="defect">Defect report</option>
                </select>
              </label>
              <label>Service date (optional)
                <input type="date" value={serviceDate} onChange={(event) => setServiceDate(event.target.value)} />
              </label>
              <label className="maintenance-wide">Details
                <textarea required minLength={3} maxLength={500} rows={3}
                  value={description} onChange={(event) => setDescription(event.target.value)}
                  placeholder={type === "defect" ? "Describe the defect..." : "Describe the service performed..."} />
              </label>
              <button type="submit" disabled={busy || !staffKey.trim()}>Save record</button>
            </form>
          </section>

          <section className="maintenance-panel">
            <div className="maintenance-topline">
              <h2>Maintenance and defect records ({entries.length})</h2>
              <span className="maintenance-open-count">
                {entries.filter((entry) => entry.status === "open").length} open defects
              </span>
            </div>
            {entries.length === 0 && <p className="muted">No maintenance records loaded. Choose Refresh history to load this vehicle's records.</p>}
            <div className="maintenance-list">
              {entries.map((entry) => (
                <article key={entry.id} className="maintenance-record">
                  <div className="maintenance-topline">
                    <div>
                      <span className="eyebrow">{entry.entry_type === "defect" ? "DEFECT" : "MAINTENANCE"} #{entry.id}</span>
                      <h3>{entry.description}</h3>
                    </div>
                    <span className={`maintenance-pill maintenance-${entry.status}`}>{entry.status}</span>
                  </div>
                  <p className="muted">Recorded {formatDate(entry.reported_at)} · Service date {formatDate(entry.service_date)}</p>
                  {entry.resolution_notes && <p><strong>Resolution:</strong> {entry.resolution_notes} ({formatDate(entry.resolved_at)})</p>}
                  {entry.entry_type === "defect" && entry.status === "open" && (
                    resolving === entry.id
                      ? <div className="maintenance-resolve">
                          <label>Resolution details
                            <textarea rows={2} required minLength={3} maxLength={500}
                              value={resolutionNotes} onChange={(event) => setResolutionNotes(event.target.value)} />
                          </label>
                          <button type="button" disabled={busy || resolutionNotes.trim().length < 3}
                            onClick={() => void resolveEntry(entry)}>Confirm resolution</button>
                          <button type="button" className="secondary-button" onClick={() => setResolving(null)}>Cancel</button>
                        </div>
                      : <button type="button" className="secondary-button" onClick={() => {
                          setResolving(entry.id);
                          setResolutionNotes("");
                        }}>Resolve defect</button>
                  )}
                </article>
              ))}
            </div>
          </section>

          <section className="maintenance-panel">
            <h2>Previous inspections ({inspections.length})</h2>
            {inspectionNote && <p className="muted">{inspectionNote}</p>}
            {inspections.map((item) => (
              <article key={item.id} className="maintenance-record">
                <strong>Inspection #{item.id}</strong>
                <p className="muted">{formatDate(item.inspected_at ?? item.created_at ?? null)}</p>
                <p>{item.condition ?? "Condition not supplied"}{item.mileage != null ? ` · ${item.mileage} km` : ""}</p>
                {item.notes && <p>{item.notes}</p>}
              </article>
            ))}
          </section>
        </>
      )}
    </main>
  );
}
