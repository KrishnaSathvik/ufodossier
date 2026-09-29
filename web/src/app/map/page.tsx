import { HeaderShell } from "@/components/HeaderShell";
import { getGeocodePendingCount, getMapIncidents } from "@/lib/incidents";
import { MapClient } from "./MapClient";
import type { Metadata } from "next";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Incident Map",
  description: "Map of UAP incidents that have a location in the U.S. government's declassified files.",
  alternates: { canonical: "/map" },
};

export default async function MapPage() {
  const [incidents, unplottedCount] = await Promise.all([
    getMapIncidents(),
    getGeocodePendingCount(),
  ]);

  return (
    <>
      <HeaderShell active="map" />
      <main className="flex flex-col h-[calc(100vh-96px)] md:h-[calc(100vh-56px)]">
        <div className="flex-1 relative overflow-hidden">
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
