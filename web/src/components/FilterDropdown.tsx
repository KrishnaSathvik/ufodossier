"use client";

interface FilterDropdownProps {
  label: string;
  value: string;
  options: { value: string; label: string; count?: number }[];
  onChange: (value: string) => void;
}

export function FilterDropdown({ label, value, options, onChange }: FilterDropdownProps) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none bg-bg-elev border border-rule text-sm text-ink pl-3 pr-8 py-1.5 font-sans cursor-pointer hover:border-ink-faint transition-colors focus:outline-none focus:border-accent"
        aria-label={label}
      >
        <option value="">{label}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}{opt.count !== undefined ? ` (${opt.count})` : ""}
          </option>
        ))}
      </select>
      <svg
        className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-ink-faint"
        width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </div>
  );
}
