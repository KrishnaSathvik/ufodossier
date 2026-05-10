"use client";

import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import { type MapIncident } from "./MapView";
import { MapFilterSidebar, EMPTY_FILTERS, type MapFilters } from "@/components/MapFilterSidebar";

const MapView = dynamic(() => import("./MapView").then((m) => m.MapView), { ssr: false });

function getDecade(occurred_at: string | null): string {
  if (!occurred_at) return "Undated";
  const year = parseInt(occurred_at.split("-")[0]);
  if (isNaN(year)) return "Undated";
  return `${Math.floor(year / 10) * 10}s`;
}

interface Props {
  incidents: MapIncident[];
  totalCount: number;
}

export function MapClient({ incidents, totalCount }: Props) {
  const [filters, setFilters] = useState<MapFilters>(EMPTY_FILTERS);

  const filtered = useMemo(() => {
    return incidents.filter((inc) => {
      // Search filter
      if (filters.search) {
        const q = filters.search.toLowerCase();
        if (
          !inc.title.toLowerCase().includes(q) &&
          !inc.case_id.toLowerCase().includes(q) &&
          !(inc.location_text?.toLowerCase().includes(q))
        ) {
          return false;
        }
      }

      // Decade filter
      if (filters.decades.size > 0) {
        if (!filters.decades.has(getDecade(inc.occurred_at))) return false;
      }

      // Branch filter (normalize "null" string to "Unknown")
      if (filters.branches.size > 0) {
        const branch = (!inc.branch || inc.branch === "null") ? "Unknown" : inc.branch;
        if (!filters.branches.has(branch)) return false;
      }

      // Sensor filter
      if (filters.sensors.size > 0) {
        const sensors = inc.sensor_types ?? [];
        if (!sensors.some((s) => filters.sensors.has(s))) return false;
      }

      // Status filter
      if (filters.statuses.size > 0) {
        if (!filters.statuses.has(inc.resolution_status ?? "unknown")) return false;
      }

      return true;
    });
  }, [incidents, filters]);

  return (
    <div className="w-full h-full flex relative overflow-hidden">
      <MapFilterSidebar
        incidents={incidents}
        filteredCount={filtered.length}
        filters={filters}
        onFiltersChange={setFilters}
      />
      <div className="flex-1 relative h-full">
        <MapView incidents={filtered} />
      </div>
    </div>
  );
}
