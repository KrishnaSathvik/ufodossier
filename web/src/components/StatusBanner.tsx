import Link from "next/link";
import { listReleases } from "@/lib/corpus/catalog";
import { releaseLabel } from "@/lib/labels";

export function StatusBanner() {
  const releases = listReleases();
  const latest = releases.length > 0 ? releases[releases.length - 1] : null;
  const latestName = latest ? releaseLabel(latest.release) : "latest release";
  const shortName = latest
    ? `Release ${String(latest.release).padStart(2, "0")}`
    : "Latest release";
  const href = latest ? `/releases/${String(latest.release).padStart(2, "0")}` : "/releases";

  return (
    <div className="border-t border-rule bg-bg">
      <Link
        href={href}
        className="site-shell flex items-center gap-2.5 py-2 min-h-8 lg:h-10 hover:bg-bg-elev/60 transition-colors"
      >
        <span className="stamp shrink-0 scale-[0.8] sm:scale-90 origin-left">New</span>
        {/* Mobile: short line. Desktop: full sentence. */}
        <span className="font-mono text-[11px] lg:text-xs uppercase tracking-tracked text-ink-dim min-w-0">
          <span className="sm:hidden text-critical">
            {shortName} updated &rarr;
          </span>
          <span className="hidden sm:inline">
            Archive updated with {latestName}
            <span className="text-ink-faint"> — </span>
            <span className="text-critical">View release</span>
          </span>
        </span>
      </Link>
    </div>
  );
}
