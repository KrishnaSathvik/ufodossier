import Link from "next/link";
import { releaseLabel } from "@/lib/labels";

export function IncidentRow({ incident }: { incident: any }) {
  const date = incident.occurred_at ?? incident.occurred_at_text ?? null;
  const branch = incident.branch ?? incident.source_agency ?? null;
  const status = incident.resolution_status ?? null;
  const href = `/incident/${incident.slug || incident.id}`;

  return (
    <Link
      href={href}
      className="incident-row group flex flex-col lg:grid sm:flex-row sm:items-baseline gap-1 sm:gap-0 lg:gap-x-6 py-3.5 border-b border-rule hover:bg-bg-elev transition-colors px-1 -mx-1"
    >
      {/* Date */}
      <span className="incident-date text-sm font-mono text-ink-faint lg:text-ink-dim w-28 lg:w-auto shrink-0">
        {date ?? "Undated"}
      </span>

      {/* Title */}
      <span className="text-[15px] lg:text-base lg:leading-relaxed font-serif text-ink group-hover:text-accent transition-colors flex-1 min-w-0">
        {incident.title}
      </span>

      {/* Branch + Status */}
      <span className="incident-metadata flex lg:grid items-center gap-3 shrink-0 sm:ml-4 lg:ml-0">
        {incident.tranche_number ? (
          <span className="incident-release text-xs font-mono text-ink-faint lg:text-ink-dim uppercase">
            {releaseLabel(incident.tranche_number)}
          </span>
        ) : null}
        {branch && (
          <span className="incident-agency text-xs font-mono text-ink-faint lg:text-ink-dim uppercase">
            {branch}
          </span>
        )}
        {status && (
          <span className={`incident-status text-xs font-mono uppercase ${
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
