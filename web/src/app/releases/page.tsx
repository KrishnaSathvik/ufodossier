import { HeaderShell } from "@/components/HeaderShell";
import { Footer } from "@/components/Footer";
import { JsonLd } from "@/components/JsonLd";
import { listReleases } from "@/lib/corpus/catalog";
import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "PURSUE Releases",
  description: "The six public PURSUE releases of U.S. government UAP records.",
  alternates: { canonical: "/releases" },
};

export default function ReleasesPage() {
  const releases = listReleases();

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: "PURSUE Releases — UFO Dossier",
        description: "Public PURSUE releases indexed by UFO Dossier.",
        url: "https://www.ufodossier.com/releases",
      }} />
      <HeaderShell active="releases" />
      <main className="max-w-content mx-auto px-4 md:px-6 py-10 md:py-14">
        <h1 className="font-serif text-2xl md:text-4xl font-medium mb-3">PURSUE releases</h1>
        <p className="text-ink-dim max-w-prose mb-8">
          Official files grouped by the government release they arrived in.
          A file count is not a sighting count. Checked passages are quotes verified against the original file.
          Several passages can describe one sighting.
        </p>
        {releases.length === 0 ? (
          <p className="text-ink-faint">No releases are listed yet.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {releases.map((release) => (
              <Link
                key={release.release}
                href={`/releases/${String(release.release).padStart(2, "0")}`}
                className="border border-rule p-5 hover:border-ink-faint transition-colors"
              >
                <h2 className="font-serif text-2xl mb-3">{release.label}</h2>
                <dl className="grid grid-cols-2 gap-y-2 text-sm">
                  <Stat label="Records" value={release.records} />
                  <Stat label="PDFs" value={release.pdfs} />
                  <Stat label="Media" value={release.media} />
                  <Stat label="Checked passages" value={release.acceptedFragments} />
                </dl>
                <p className="mt-3 text-xs font-mono text-ink-faint">
                  {release.agencies.join(" · ") || "Agency not recorded"}
                </p>
              </Link>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-ink-faint text-xs">{label}</dt>
      <dd className="tabular-nums">{value.toLocaleString()}</dd>
    </div>
  );
}
