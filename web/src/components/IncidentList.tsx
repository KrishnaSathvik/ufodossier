"use client";

import { useState, useMemo } from "react";
import { IncidentRow } from "./IncidentRow";

const PAGE_SIZE = 30;

interface IncidentListProps {
  incidents: any[];
  showSearch?: boolean;
  paginated?: boolean;
}

export function IncidentList({ incidents, showSearch = false, paginated = false }: IncidentListProps) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [visible, setVisible] = useState(PAGE_SIZE);

  const filtered = useMemo(() => {
    if (!query.trim()) return incidents;
    const q = query.toLowerCase();
    return incidents.filter(
      (inc) =>
        inc.title?.toLowerCase().includes(q) ||
        inc.location_text?.toLowerCase().includes(q) ||
        inc.country?.toLowerCase().includes(q) ||
        inc.branch?.toLowerCase().includes(q) ||
        inc.source_agency?.toLowerCase().includes(q) ||
        inc.case_id?.toLowerCase().includes(q) ||
        inc.summary?.toLowerCase().includes(q)
    );
  }, [incidents, query]);

  if (incidents.length === 0) {
    return (
      <p className="py-12 text-center text-ink-faint">
        No incidents yet. Pipeline pending.
      </p>
    );
  }

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const shown = paginated
    ? filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
    : filtered.slice(0, visible);
  const hasMore = !paginated && visible < filtered.length;

  return (
    <>
      {showSearch && (
        <div className="mb-6">
          <input
            type="text"
            placeholder="Search incidents by title, location, branch, agency..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            className="w-full px-4 py-2.5 bg-bg-elev border border-rule text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent transition-colors"
          />
        </div>
      )}

      {filtered.length === 0 ? (
        <p className="py-12 text-center text-ink-faint">
          No incidents match &ldquo;{query}&rdquo;
        </p>
      ) : (
        <>
          {shown.map((inc) => (
            <IncidentRow key={inc.id} incident={inc} />
          ))}

          {paginated ? (
            <div className="flex items-center justify-between pt-6">
              <span className="text-sm text-ink-faint">
                Page {page} of {totalPages} &middot; {filtered.length} incidents
              </span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 border border-rule text-sm font-medium hover:border-ink-faint transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  &larr; Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 border border-rule text-sm font-medium hover:border-ink-faint transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  Next &rarr;
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between pt-6">
              <span className="text-sm text-ink-faint">
                Showing {shown.length} of {filtered.length}
              </span>
              {hasMore && (
                <button
                  onClick={() => setVisible((v) => v + PAGE_SIZE)}
                  className="text-sm font-medium text-accent hover:text-accent-dim transition-colors"
                >
                  Show more &darr;
                </button>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
