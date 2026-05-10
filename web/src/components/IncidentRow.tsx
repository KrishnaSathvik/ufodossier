import Link from "next/link";

export function IncidentRow({ incident }: { incident: any }) {
  const date = incident.occurred_at ?? incident.occurred_at_text ?? null;
  const branch = incident.branch ?? incident.source_agency ?? null;
  const status = incident.resolution_status ?? null;
  const href = `/incident/${incident.slug || incident.id}`;

  return (
    <Link
      href={href}
      className="group flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-0 py-3.5 border-b border-rule hover:bg-bg-elev transition-colors px-1 -mx-1"
    >
      {/* Date */}
      <span className="text-sm font-mono text-ink-faint w-28 shrink-0">
        {date ?? "Undated"}
      </span>

      {/* Title */}
      <span className="text-[15px] font-serif text-ink group-hover:text-accent transition-colors flex-1 min-w-0">
        {incident.title}
      </span>

      {/* Branch + Status */}
      <span className="flex items-center gap-3 shrink-0 sm:ml-4">
        {branch && (
          <span className="text-xs font-mono text-ink-faint uppercase">
            {branch}
          </span>
        )}
        {status && (
          <span className={`text-xs font-mono uppercase ${
            status === "unresolved" ? "text-critical" :
            status === "identified" ? "text-ink-dim" :
            "text-ink-faint"
          }`}>
            {status.replace("_", " ")}
          </span>
        )}
      </span>
    </Link>
  );
}
