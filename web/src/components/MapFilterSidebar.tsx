"use client";

import { useMemo } from "react";

export interface MapFilters {
  search: string;
  decades: Set<string>;
  branches: Set<string>;
  sensors: Set<string>;
  statuses: Set<string>;
}

export const EMPTY_FILTERS: MapFilters = {
  search: "",
  decades: new Set(),
  branches: new Set(),
  sensors: new Set(),
  statuses: new Set(),
};

interface Props {
  incidents: any[];
  filteredCount: number;
  filters: MapFilters;
  onFiltersChange: (f: MapFilters) => void;
}

function getDecade(occurred_at: string | null): string {
  if (!occurred_at) return "Undated";
  const year = parseInt(occurred_at.split("-")[0]);
  if (isNaN(year)) return "Undated";
  return `${Math.floor(year / 10) * 10}s`;
}

function countBy<T>(items: T[], key: (item: T) => string): [string, number][] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const k = key(item);
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  return [...counts.entries()];
}

function countByArray<T>(items: T[], key: (item: T) => string[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const item of items) {
    for (const k of key(item)) {
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

function toggleSet(set: Set<string>, value: string): Set<string> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

/** Normalize branch: treat null, "null", empty string as "Unknown" */
function normBranch(branch: string | null | undefined): string {
  if (!branch || branch === "null") return "Unknown";
  return branch;
}

export function MapFilterSidebar({ incidents, filteredCount, filters, onFiltersChange }: Props) {
  const decades = useMemo(() => {
    const entries = countBy(incidents, (i) => getDecade(i.occurred_at));

    if (process.env.NODE_ENV === "development") {
      const decadeMap = new Map<string, number>();
      let nullCount = 0;
      for (const inc of incidents) {
        if (!inc.occurred_at) { nullCount++; continue; }
        const year = parseInt(inc.occurred_at.split("-")[0]);
        if (isNaN(year)) { nullCount++; continue; }
        const decade = `${Math.floor(year / 10) * 10}s`;
        decadeMap.set(decade, (decadeMap.get(decade) ?? 0) + 1);
      }
      console.log("[MapFilter] Decade distribution (geolocated):", Object.fromEntries([...decadeMap.entries()].sort()));
      console.log("[MapFilter] occurred_at IS NULL (geolocated):", nullCount);
      // TODO: If 1990s/2000s/2010s are missing, investigate whether the extractor
      // is failing to parse dates for those decades or if source documents lack them.
    }

    return entries.sort((a, b) => {
      if (a[0] === "Undated") return 1;
      if (b[0] === "Undated") return -1;
      return a[0].localeCompare(b[0]);
    });
  }, [incidents]);

  const branches = useMemo(() =>
    countBy(incidents, (i) => normBranch(i.branch)).sort((a, b) => b[1] - a[1]),
    [incidents]
  );

  const sensors = useMemo(() =>
    countByArray(incidents, (i) => (i.sensor_types as string[] | null) ?? []),
    [incidents]
  );

  const statuses = useMemo(() =>
    countBy(incidents, (i) => i.resolution_status ?? "unknown").sort((a, b) => b[1] - a[1]),
    [incidents]
  );

  const hasActiveFilters = filters.search || filters.decades.size || filters.branches.size || filters.sensors.size || filters.statuses.size;

  function clearAll() {
    onFiltersChange(EMPTY_FILTERS);
  }

  const content = (
    <div className="h-full p-3 space-y-3 overflow-y-auto">
      {/* Search */}
      <input
        type="text"
        value={filters.search}
        onChange={(e) => onFiltersChange({ ...filters, search: e.target.value })}
        placeholder="Search incidents..."
        className="w-full bg-bg border border-rule focus:border-accent px-3 py-1.5 text-xs text-ink outline-none transition-colors"
      />

      {/* Honesty line */}
      <p className="text-xs text-ink-faint">
        Showing {filteredCount} of {incidents.length} geolocated.
        {hasActiveFilters ? (
          <button onClick={clearAll} className="text-accent hover:underline ml-1">
            Clear
          </button>
        ) : null}
      </p>

      {/* Legend */}
      <div className="border border-rule px-2.5 py-2" style={{ backgroundColor: "rgba(35, 33, 27, 0.9)" }}>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#c8302a] inline-block shrink-0" />
            <span className="text-[11px] text-ink-dim">Unresolved</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#66aa88] inline-block shrink-0" />
            <span className="text-[11px] text-ink-dim">Identified</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#888888] inline-block shrink-0" />
            <span className="text-[11px] text-ink-dim">Insufficient data</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#ff9933] inline-block shrink-0" />
            <span className="text-[11px] text-ink-dim">Cluster (count)</span>
          </div>
        </div>
      </div>

      {/* Filters — inline chip toggles */}
      <ChipSection
        label="Decade"
        items={decades}
        selected={filters.decades}
        onToggle={(v) => onFiltersChange({ ...filters, decades: toggleSet(filters.decades, v) })}
      />

      <ChipSection
        label="Branch"
        items={branches}
        selected={filters.branches}
        onToggle={(v) => onFiltersChange({ ...filters, branches: toggleSet(filters.branches, v) })}
      />

      <ChipSection
        label="Sensors"
        items={sensors}
        selected={filters.sensors}
        onToggle={(v) => onFiltersChange({ ...filters, sensors: toggleSet(filters.sensors, v) })}
      />

      <ChipSection
        label="Status"
        items={statuses}
        selected={filters.statuses}
        onToggle={(v) => onFiltersChange({ ...filters, statuses: toggleSet(filters.statuses, v) })}
        formatLabel={(v) => v.replace("_", " ")}
      />
    </div>
  );

  return (
    <div className="hidden md:flex w-72 shrink-0 border-r border-rule bg-bg flex-col overflow-hidden">
      {content}
    </div>
  );
}

function ChipSection({ label, items, selected, onToggle, formatLabel }: {
  label: string;
  items: [string, number][];
  selected: Set<string>;
  onToggle: (v: string) => void;
  formatLabel?: (v: string) => string;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="text-[11px] font-mono uppercase tracking-tracked text-ink-faint mb-1.5">{label}</h3>
      <div className="flex flex-wrap gap-1">
        {items.map(([value, count]) => {
          const active = selected.has(value);
          return (
            <button
              key={value}
              onClick={() => onToggle(value)}
              className={`px-2 py-0.5 text-[11px] border transition-colors ${
                active
                  ? "border-accent text-accent bg-accent/10"
                  : "border-rule text-ink-dim hover:border-ink-faint hover:text-ink"
              }`}
            >
              {formatLabel ? formatLabel(value) : value} <span className="text-ink-faint">{count}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
