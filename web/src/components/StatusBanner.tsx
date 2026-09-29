import Link from "next/link";
import { listReleases } from "@/lib/corpus/catalog";
import { releaseLabel } from "@/lib/labels";

export function StatusBanner() {
  const releases = listReleases();
  const latest = releases.length > 0 ? releases[releases.length - 1] : null;
  const latestName = latest ? releaseLabel(latest.release) : "latest release";
  const href = latest ? `/releases/${String(latest.release).padStart(2, "0")}` : "/releases";

  return (
    <div className="border-t border-rule bg-bg">
      <div className="max-w-content mx-auto px-4 md:px-6 h-8 flex items-center gap-3">
        <span className="stamp shrink-0 scale-90 origin-left">New</span>
        <p className="font-mono text-[11px] uppercase tracking-tracked text-ink-dim truncate">
          Archive updated with {latestName}
          <span className="text-ink-faint"> — </span>
          <Link href={href} className="text-critical hover:underline">
            View release
          </Link>
        </p>
      </div>
    </div>
  );
}
