"use client";

interface TabToggleProps {
  tabs: { value: string; label: string; count?: number }[];
  active: string;
  onChange: (value: string) => void;
}

export function TabToggle({ tabs, active, onChange }: TabToggleProps) {
  return (
    <div className="inline-flex border border-rule overflow-hidden">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={`px-4 py-1.5 text-sm transition-colors ${
            active === tab.value
              ? "bg-ink text-bg font-medium"
              : "text-ink-dim hover:text-ink"
          }`}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="ml-1.5 text-xs opacity-60">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}
