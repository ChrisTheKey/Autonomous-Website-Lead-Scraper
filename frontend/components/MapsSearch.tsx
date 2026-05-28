"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { mapsApi } from "@/lib/api";
import { MapPin } from "lucide-react";

interface Business {
  name: string;
  address: string;
  phone: string;
  website: string;
  rating: number;
}

export default function MapsSearch() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [radius, setRadius] = useState(5000);

  const mutation = useMutation({
    mutationFn: () => mapsApi.businessSearch(query, location, radius),
  });

  const results: Business[] = mutation.data?.data?.results ?? [];

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-800">
        <MapPin size={18} className="text-red-500" />
        Google Maps Business Search
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. web design agency"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="e.g. Berlin, Germany"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
        <input
          type="number"
          value={radius}
          onChange={(e) => setRadius(Number(e.target.value))}
          placeholder="Radius (m)"
          className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
      </div>
      <button
        onClick={() => mutation.mutate()}
        disabled={!query || !location || mutation.isPending}
        className="mt-3 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
      >
        {mutation.isPending ? "Searching…" : "Search"}
      </button>

      {results.length > 0 && (
        <div className="mt-4 space-y-2">
          {results.map((b, i) => (
            <div key={i} className="rounded border border-gray-100 p-3 text-sm">
              <p className="font-semibold text-gray-800">{b.name}</p>
              <p className="text-gray-500">{b.address}</p>
              {b.phone && <p className="text-gray-500">{b.phone}</p>}
              {b.website && (
                <a href={b.website} className="text-blue-600 hover:underline" target="_blank" rel="noreferrer">
                  {b.website}
                </a>
              )}
              {b.rating && <p className="text-yellow-600">★ {b.rating}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
