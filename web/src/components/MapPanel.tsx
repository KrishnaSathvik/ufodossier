"use client";

import Link from "next/link";
import Image from "next/image";
import { RedactedExcerpt } from "@/components/RedactedExcerpt";

interface MapPanelProps {
  incident: any;
  onClose: () => void;
}

export function MapPanel({ incident, onClose }: MapPanelProps) {
  const thumbSrc = incident.image_url || incident.cover_image_url || incident.source_cover_image_url;

  return (
    <div className="absolute bottom-0 inset-x-2 max-h-[50vh] rounded-t-xl md:inset-x-auto md:bottom-auto md:right-4 md:top-4 md:w-80 md:max-h-[calc(100%-2rem)] md:rounded-none bg-bg border border-rule shadow-lg z-10 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-start gap-3 p-3 md:p-4 border-b border-rule shrink-0 min-w-0">
        {/* Inline thumbnail on mobile, hidden on desktop */}
        {thumbSrc && (
          <div className="relative w-12 h-12 shrink-0 rounded overflow-hidden border border-rule md:hidden">
            <Image src={thumbSrc} alt="" fill sizes="48px" className="object-cover" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <span className="text-xs font-mono text-ink-faint block truncate">{incident.case_id}</span>
          <h3 className="font-serif text-sm md:text-base font-medium leading-snug mt-0.5 line-clamp-2 break-words">
            {incident.title}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-ink-faint hover:text-ink transition-colors shrink-0 mt-0.5 p-1"
          aria-label="Close"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="p-3 md:p-4 space-y-2 md:space-y-3 overflow-y-auto min-w-0">
        {/* Large thumbnail — desktop only */}
        {thumbSrc && (
          <div className="relative aspect-[3/2] bg-bg-quiet overflow-hidden mb-2 border border-rule hidden md:block">
            <Image src={thumbSrc} alt="" fill sizes="320px" className="object-cover" />
            {incident.video_url && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-8 h-8 rounded-full bg-ink/60 flex items-center justify-center">
                  <svg className="text-bg ml-0.5" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                </div>
              </div>
            )}
            {!incident.image_url && !incident.video_url && (
              <span className="absolute bottom-1 left-1 bg-bg/80 px-1.5 py-0.5 text-[9px] font-mono uppercase text-ink-faint">
                Document
              </span>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-dim">
          <span>{incident.occurred_at ?? incident.occurred_at_text ?? "Undated"}</span>
          {incident.location_text && <span className="truncate">{incident.location_text}</span>}
        </div>

        <div className="flex items-center gap-3">
          {incident.branch && (
            <span className="text-xs font-mono uppercase text-ink-faint">{incident.branch}</span>
          )}
          <span className={`text-xs font-mono uppercase ${
            incident.resolution_status === "unresolved" ? "text-critical" : "text-ink-faint"
          }`}>
            {incident.resolution_status?.replace("_", " ")}
          </span>
        </div>

        {incident.summary && (
          <p className="text-sm text-ink-dim leading-relaxed line-clamp-3 break-words">
            {incident.summary}
          </p>
        )}

        {incident.raw_excerpt && (
          <blockquote className="border-l-2 border-accent pl-3 py-1 hidden md:block">
            <p className="text-xs text-ink-dim italic line-clamp-3 break-words">
              &ldquo;<RedactedExcerpt text={incident.raw_excerpt} />&rdquo;
            </p>
          </blockquote>
        )}

        <Link
          href={`/incident/${incident.slug || incident.id}`}
          className="block text-sm text-accent hover:text-accent-dim transition-colors pt-1"
        >
          View case file &rarr;
        </Link>
      </div>
    </div>
  );
}
