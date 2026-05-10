"use client";

import { useState } from "react";
import { IncidentRow } from "./IncidentRow";

const PAGE_SIZE = 30;

export function IncidentList({ incidents }: { incidents: any[] }) {
  const [visible, setVisible] = useState(PAGE_SIZE);

  if (incidents.length === 0) {
    return (
      <p className="py-12 text-center text-ink-faint">
        No incidents yet. Pipeline pending.
      </p>
    );
  }

  const shown = incidents.slice(0, visible);
  const hasMore = visible < incidents.length;

  return (
    <>
      {shown.map((inc) => (
        <IncidentRow key={inc.id} incident={inc} />
      ))}

      <div className="flex items-center justify-between pt-6">
        <span className="text-sm text-ink-faint">
          Showing {shown.length} of {incidents.length}
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
    </>
  );
}
