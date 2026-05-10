import { TopBar } from "@/components/TopBar";
import { getMapIncidents, getTotalIncidentCount } from "@/lib/incidents";
import { MapClient } from "./MapClient";
import type { Metadata } from "next";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Incident Map",
  description: "Interactive map of geolocated UAP incidents from the U.S. government's declassified files.",
  alternates: { canonical: "/map" },
};

export default async function MapPage() {
  const [incidents, totalCount] = await Promise.all([
    getMapIncidents(),
    getTotalIncidentCount(),
  ]);

  return (
    <>
      <TopBar active="map" />
      <main className="flex flex-col h-[calc(100vh-96px)] md:h-[calc(100vh-56px)]">
        <div className="flex-1 relative overflow-hidden">
          {incidents.length > 0 ? (
            <MapClient incidents={incidents} totalCount={totalCount} />
          ) : (
            <div className="flex items-center justify-center h-full text-ink-faint">
              <p>No geolocated incidents available.</p>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
