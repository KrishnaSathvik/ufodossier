"use client";

import dynamic from "next/dynamic";
import { type MapIncident } from "./MapView";
import { MapLegend } from "@/components/MapLegend";

const MapView = dynamic(() => import("./MapView").then((m) => m.MapView), { ssr: false });

interface Props {
  incidents: MapIncident[];
  unplottedCount: number;
}

export function MapClient({ incidents, unplottedCount }: Props) {
  return (
    <div className="relative w-full h-full min-h-0 overflow-hidden">
      <MapView incidents={incidents} />
      <MapLegend plottedCount={incidents.length} unplottedCount={unplottedCount} />
    </div>
  );
}
