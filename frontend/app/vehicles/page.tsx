"use client";

// USER-2: Filter By Type
// Vehicle listing page with a category dropdown.
// Served at http://localhost:3000/vehicles (Next.js maps app/vehicles/page.tsx to /vehicles).
//
// This file is self-contained on purpose: it does not import from or edit page.tsx,
// so it cannot conflict with the reservation form (USER-1) or AvailabilityFilter (USER-5).

import { useEffect, useState } from "react";

// Shape of one vehicle returned by GET /vehicles.
// `status` is optional because it only exists once USER-5's backend change is merged.
type Vehicle = {
  id: number;
  make: string;
  model: string;
  category: string;
  daily_rate: number;
  available: boolean;
  status?: string;
};

const API_URL = "http://localhost:8000";

export default function VehicleListingPage() {
  // "" means "All categories" (no filter).
  const [category, setCategory] = useState("");
  // Vehicles currently shown (already filtered by the backend).
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  // Every category that exists, used to build the dropdown options.
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Step 1 (runs once): fetch ALL vehicles to discover which categories exist.
  // Building the dropdown from real data means categories that staff add later
  // (STAFF-1) show up automatically and the spelling always matches the database.
  useEffect(() => {
    fetch(`${API_URL}/vehicles`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load vehicle categories");
        return response.json() as Promise<Vehicle[]>;
      })
      .then((all) => {
        // Set removes duplicates; sort() keeps the dropdown tidy.
        setCategories(Array.from(new Set(all.map((v) => v.category))).sort());
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  // Step 2 (runs on load AND every time `category` changes): ask the backend
  // for only the vehicles in the selected category. Filtering happens on the
  // server via GET /vehicles?category=..., not in the browser.
  useEffect(() => {
    // `cancelled` stops an old, slow response from overwriting a newer one
    // if the user changes the dropdown quickly.
    let cancelled = false;
    setLoading(true);
    setError("");

    // Leave the query string off entirely for "All categories".
    const query = category ? `?category=${encodeURIComponent(category)}` : "";

    fetch(`${API_URL}/vehicles${query}`)
      .then((response) => {
        if (!response.ok) throw new Error("Could not load vehicles");
        return response.json() as Promise<Vehicle[]>;
      })
      .then((data) => {
        if (!cancelled) setVehicles(data);
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setVehicles([]);
          setError(reason.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    // Cleanup runs before the next effect, marking this request as stale.
    return () => {
      cancelled = true;
    };
  }, [category]);

  return (
    <main>
      <h1>Hawk Rentals</h1>
      <h2>Browse vehicles</h2>

      <p>
        <label>
          Category:{" "}
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">All categories</option>
            {categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </p>

      {error && <p role="alert">{error}</p>}
      {loading && <p>Loading vehicles...</p>}

      {/* Empty state: shown when the request worked but nothing matches. */}
      {!loading && !error && vehicles.length === 0 && (
        <p>No vehicles found{category ? ` in the ${category} category` : ""}.</p>
      )}

      <ul>
        {vehicles.map((vehicle) => (
          <li key={vehicle.id}>
            <strong>
              {vehicle.make} {vehicle.model}
            </strong>{" "}
            ({vehicle.category}) - ${vehicle.daily_rate}/day
            {/* Flag vehicles staff marked out of service. */}
            {!vehicle.available && " - Currently unavailable"}
          </li>
        ))}
      </ul>

      <p>
        <a href="/">Reserve a vehicle</a>
      </p>
    </main>
  );
}