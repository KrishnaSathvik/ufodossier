"use client";

interface Props {
  plottedCount: number;
  unplottedCount: number;
}

const PILLS = [
  { color: "#c8302a", label: "Unresolved" },
  { color: "#66aa88", label: "Identified" },
  { color: "#888888", label: "Insufficient data" },
  { color: "#ff9933", label: "Cluster" },
] as const;

export function MapLegend({ plottedCount, unplottedCount }: Props) {
  return (
    <div className="absolute top-3 left-3 right-3 z-10 flex flex-wrap items-center gap-2 pointer-events-none md:left-12 md:right-auto md:max-w-[calc(100%-8rem)]">
      <div
        className="flex flex-wrap items-center gap-1.5 border border-[#2a2925]/35 px-2 py-1.5 shadow-sm"
        style={{ backgroundColor: "rgba(232, 230, 224, 0.94)" }}
      >
        {PILLS.map((pill) => (
          <span
            key={pill.label}
            className="inline-flex items-center gap-1.5 border border-[#2a2925]/25 px-2 py-0.5 text-[11px] text-[#1a1916]"
            style={{ backgroundColor: "rgba(255, 255, 255, 0.55)" }}
          >
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: pill.color }}
            />
            {pill.label}
          </span>
        ))}
        <span className="text-[11px] text-[#3a3935] px-1">
          {plottedCount.toLocaleString()} plotted
          {unplottedCount > 0 ? ` · ${unplottedCount.toLocaleString()} unmapped` : ""}
        </span>
      </div>
    </div>
  );
}
