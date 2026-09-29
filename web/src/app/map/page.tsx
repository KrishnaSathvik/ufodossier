import { getGeocodePendingCount, getMapIncidents } from "@/lib/incidents";
import { MapClient } from "./MapClient";
import type { Metadata } from "next";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Incident Map",
  description: "Map of UAP incidents that have a location in the U.S. government's declassified files.",
  alternates: { canonical: "/map" },
  openGraph: {
    title: "Map — UFO Dossier",
    description: "Sightings and records located across time and place.",
    images: [{ url: "/og/map.png", width: 1200, height: 630, alt: "Map — UFO Dossier" }],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og/map.png"],
  },
};

export default async function MapPage() {
  const [incidents, unplottedCount] = await Promise.all([
    getMapIncidents(),
    getGeocodePendingCount(),
  ]);

  return (
    <>

      <main className="flex flex-col flex-1 min-h-0">
        <div className="flex-1 relative min-h-0 overflow-hidden">
          {incidents.length > 0 ? (
            <MapClient incidents={incidents} unplottedCount={unplottedCount} />
          ) : (
            <div className="flex items-center justify-center h-full text-ink-faint">
              <p>No incidents with a map point are available.</p>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
