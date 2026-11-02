"use client";

import { useEffect, useState, type FormEvent } from "react";

type Vehicle = {
  id: number;
  make: string;
  model: string;
  category: string;
  daily_rate: number;
  available: boolean;
  archived: boolean;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function StaffFleetPage() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [staffKey, setStaffKey] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [category, setCategory] = useState("compact");
  const [dailyRate, setDailyRate] = useState("60");
  const [available, setAvailable] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadVehicles() {
    setError("");
    try {
      const response = await fetch(`${API_URL}/vehicles`, { cache: "no-store" });
      if (!response.ok) throw new Error("Could not load vehicle catalog");
      setVehicles((await response.json()) as Vehicle[]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load vehicles");
    }
  }

  useEffect(() => {
    void loadVehicles();
  }, []);

  function resetForm() {
    setEditingId(null);
    setMake("");
    setModel("");
    setCategory("compact");
    setDailyRate("60");
    setAvailable(true);
  }

  function startEdit(vehicle: Vehicle) {
    setEditingId(vehicle.id);
    setMake(vehicle.make);
    setModel(vehicle.model);
    setCategory(vehicle.category);
    setDailyRate(String(vehicle.daily_rate));
    setAvailable(vehicle.available);
    setMessage(`Editing ${vehicle.make} ${vehicle.model}`);
    setError("");
  }

  async function saveVehicle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const response = await fetch(
        editingId === null ? `${API_URL}/vehicles` : `${API_URL}/vehicles/${editingId}`,
        {
          method: editingId === null ? "POST" : "PATCH",
          headers: { "Content-Type": "application/json", "X-Staff-Key": staffKey },
          body: JSON.stringify({ make, model, category, daily_rate: Number(dailyRate), available }),
        },
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Unable to save vehicle");
      setMessage(editingId === null ? "Vehicle added successfully." : "Vehicle updated successfully.");
      resetForm();
      await loadVehicles();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save vehicle");
    } finally {
      setLoading(false);
    }
  }

  async function archiveVehicle(vehicle: Vehicle) {
    if (!window.confirm(`Archive ${vehicle.make} ${vehicle.model}?`)) return;
    setError("");
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/vehicles/${vehicle.id}/archive`, {
        method: "PATCH",
        headers: { "X-Staff-Key": staffKey },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Unable to archive vehicle");
      setMessage(`${vehicle.make} ${vehicle.model} archived. It is no longer shown in the customer catalog.`);
      if (editingId === vehicle.id) resetForm();
      await loadVehicles();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to archive vehicle");
    }
  }

  const styles = {
    page: { maxWidth: 1050, margin: "40px auto", padding: "0 24px", color: "#172033", fontFamily: "Arial, sans-serif" } as const,
    panel: { border: "1px solid #d8dee9", borderRadius: 12, padding: 20, marginTop: 24 } as const,
    field: { display: "grid", gap: 6, marginBottom: 14 } as const,
    input: { padding: 10, border: "1px solid #aeb8c8", borderRadius: 6, fontSize: 15, width: "100%", boxSizing: "border-box" as const },
    button: { padding: "9px 14px", border: "1px solid #9aa6b8", borderRadius: 6, background: "#f5f7fa", cursor: "pointer", marginRight: 8 },
  };

  return (
    <main style={styles.page}>
      <p><a href="/">← Customer home</a></p>
      <h1>Staff Fleet Management</h1>
      <p>Add vehicles, update listing details, or archive vehicles from the customer catalog.</p>

      <section style={styles.panel}>
        <h2>Staff authorization</h2>
        <label style={styles.field}>
          Staff API key
          <input style={styles.input} type="password" value={staffKey} onChange={(event) => setStaffKey(event.target.value)} placeholder="Enter the STAFF_API_KEY configured on the backend" autoComplete="off" />
        </label>
        <p style={{ fontSize: 13, color: "#536176" }}>The key is kept only in this page's memory and sent to the backend for staff changes.</p>
      </section>

      <section style={styles.panel}>
        <h2>{editingId === null ? "Add a vehicle" : "Edit vehicle"}</h2>
        <form onSubmit={saveVehicle}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
            <label style={styles.field}>Make<input style={styles.input} required value={make} onChange={(event) => setMake(event.target.value)} /></label>
            <label style={styles.field}>Model<input style={styles.input} required value={model} onChange={(event) => setModel(event.target.value)} /></label>
            <label style={styles.field}>Category<select style={styles.input} value={category} onChange={(event) => setCategory(event.target.value)}><option value="compact">Compact</option><option value="sedan">Sedan</option><option value="suv">SUV</option><option value="sports">Sports</option><option value="truck">Truck</option><option value="van">Van</option></select></label>
            <label style={styles.field}>Daily rate ($)<input style={styles.input} required type="number" min="0.01" step="0.01" value={dailyRate} onChange={(event) => setDailyRate(event.target.value)} /></label>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center", margin: "8px 0 16px" }}><input type="checkbox" checked={available} onChange={(event) => setAvailable(event.target.checked)} /> Available for reservations</label>
          <button style={styles.button} type="submit" disabled={loading || !staffKey.trim()}>{loading ? "Saving…" : editingId === null ? "Add vehicle" : "Save changes"}</button>
          {editingId !== null && <button style={styles.button} type="button" onClick={resetForm}>Cancel edit</button>}
        </form>
      </section>

      <section style={styles.panel}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2>Active vehicle catalog</h2>
          <button style={styles.button} type="button" onClick={() => void loadVehicles()}>Refresh catalog</button>
        </div>
        {vehicles.length === 0 ? <p>No active vehicles found.</p> : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead><tr>{["Vehicle", "Category", "Daily rate", "Availability", "Actions"].map((heading) => <th key={heading} style={{ padding: 10, borderBottom: "2px solid #d8dee9" }}>{heading}</th>)}</tr></thead>
              <tbody>{vehicles.map((vehicle) => (
                <tr key={vehicle.id}>
                  <td style={{ padding: 10, borderBottom: "1px solid #e5e9f0" }}>{vehicle.make} {vehicle.model}</td>
                  <td style={{ padding: 10, borderBottom: "1px solid #e5e9f0" }}>{vehicle.category}</td>
                  <td style={{ padding: 10, borderBottom: "1px solid #e5e9f0" }}>${vehicle.daily_rate.toFixed(2)}</td>
                  <td style={{ padding: 10, borderBottom: "1px solid #e5e9f0" }}>{vehicle.available ? "Available" : "Unavailable"}</td>
                  <td style={{ padding: 10, borderBottom: "1px solid #e5e9f0", whiteSpace: "nowrap" }}>
                    <button style={styles.button} type="button" onClick={() => startEdit(vehicle)}>Edit</button>
                    <button style={styles.button} type="button" disabled={!staffKey.trim()} onClick={() => void archiveVehicle(vehicle)}>Archive</button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
      {error && <p role="alert" style={{ color: "#b42318", marginTop: 18 }}>{error}</p>}
      {message && <p role="status" style={{ color: "#176b3a", marginTop: 18 }}>{message}</p>}
    </main>
  );
}
