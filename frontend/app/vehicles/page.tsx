"use client";

// USER-2: Filter By Type
// Vehicle listing page with a category dropdown.
// Served at http://localhost:3000/vehicles (Next.js maps app/vehicles/page.tsx to /vehicles).
//
// This file is self-contained on purpose: it does not import from or edit page.tsx,
// so it cannot conflict with the reservation form (USER-1) or AvailabilityFilter (USER-5).

import VehicleCard from "../VehicleCard";
import { useEffect, useState, type FormEvent } from "react";

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

  // USER-4: price range. The *Input values are what the user is typing; `appliedPrice`
  // only changes when they press "Apply", so we do not call the backend on every keystroke.
  const [minInput, setMinInput] = useState("");
  const [maxInput, setMaxInput] = useState("");
  const [appliedPrice, setAppliedPrice] = useState({ min: "", max: "" });
  const [priceError, setPriceError] = useState("");

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

    // Only add the parameters that are set, so "All categories" / empty prices send nothing.
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (appliedPrice.min) params.set("min_price", appliedPrice.min);
    if (appliedPrice.max) params.set("max_price", appliedPrice.max);
    const query = params.toString() ? `?${params}` : "";

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
  }, [category, appliedPrice]); // re-fetch when the category OR the applied price range changes

  // USER-4: validate in the browser first, then apply the price range.
  function applyPrice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (minInput && maxInput && Number(minInput) > Number(maxInput)) {
      setPriceError("Minimum price cannot be greater than maximum price.");
      return;
    }
    setPriceError("");
    setAppliedPrice({ min: minInput, max: maxInput });
  }

  function clearPrice() {
    setMinInput("");
    setMaxInput("");
    setPriceError("");
    setAppliedPrice({ min: "", max: "" });
  }

  const priceActive = Boolean(appliedPrice.min || appliedPrice.max);

  return (
    <main className="fleet-page">
      <p className="eyebrow">GOOD CARS. GREAT POSSIBILITIES.</p>
      <h1>A car for every plan.</h1>
      <p className="muted">Keep it practical, make room for adventure, or take the scenic route. Find your next drive.</p>

      <p className="category-filter">
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

      {/* USER-4: Filter By Price (daily rate, in dollars; both ends inclusive) */}
      <form onSubmit={applyPrice}>
        <p>
          <label>
            Min price/day: $
            <input type="number" min="0" step="1" value={minInput} onChange={(event) => setMinInput(event.target.value)} />
          </label>{" "}
          <label>
            Max price/day: $
            <input type="number" min="0" step="1" value={maxInput} onChange={(event) => setMaxInput(event.target.value)} />
          </label>{" "}
          <button type="submit">Apply</button>{" "}
          <button type="button" onClick={clearPrice}>Clear price</button>
        </p>
      </form>
      {priceError && <p role="alert">{priceError}</p>}

      {error && <p role="alert">{error}</p>}
      {loading && <p>Loading vehicles...</p>}

      {/* Empty state: shown when the request worked but nothing matches. */}
      {!loading && !error && vehicles.length === 0 && (
        <p>
          No vehicles found{category ? ` in the ${category} category` : ""}
          {priceActive ? " within this price range" : ""}.
        </p>
      )}

      <div className="fleet-results"><span>{vehicles.length} vehicles{category ? ` · ${category}` : " · all categories"}</span><a className="text-link" href="/photo-credits">About the photos</a></div>
      <div className="vehicle-grid">
        {vehicles.map((vehicle) => (
          <VehicleCard key={vehicle.id} vehicle={vehicle} />
        ))}
      </div>

      <p>
        <a href="/">Reserve a vehicle</a>
      </p>
    </main>
  );
}
