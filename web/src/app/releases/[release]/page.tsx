import { HeaderShell } from "@/components/HeaderShell";
import { Footer } from "@/components/Footer";
import { JsonLd } from "@/components/JsonLd";
import { getRelease, listSources } from "@/lib/corpus/catalog";
import { processingStateLabel, recordTypeLabel } from "@/lib/labels";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ release: string }> }): Promise<Metadata> {
  const { release } = await params;
  const number = Number(release);
  const row = getRelease(number);
  if (!row) return { title: "Release" };
  return {
    title: row.label,
    description: `${row.records} official records in ${row.label}.`,
    alternates: { canonical: `/releases/${String(number).padStart(2, "0")}` },
  };
}

export default async function ReleaseDetailPage({ params }: { params: Promise<{ release: string }> }) {
  const { release } = await params;
  const number = Number(release);
  if (!Number.isInteger(number)) notFound();
  const row = getRelease(number);
  if (!row) notFound();
  const sources = listSources({ release: number });

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "Dataset",
        name: `${row.label} — UFO Dossier`,
        description: `Official PURSUE ${row.label} records in the UFO Dossier catalog.`,
        url: `https://www.ufodossier.com/releases/${String(number).padStart(2, "0")}`,
        creator: { "@type": "Organization", name: "U.S. Department of War" },
      }} />
      <HeaderShell active="releases" />
      <main className="max-w-content mx-auto px-4 md:px-6 py-10 md:py-14">
        <Link href="/releases" className="text-sm text-ink-faint hover:text-ink">&larr; Releases</Link>
        <h1 className="font-serif text-3xl md:text-4xl font-medium mt-4 mb-3">{row.label}</h1>
        <p className="text-ink-dim max-w-prose mb-6">
          {row.records.toLocaleString()} official files, {row.pdfs.toLocaleString()} PDFs,{" "}
          {row.media.toLocaleString()} media files, {row.acceptedFragments.toLocaleString()} checked passages.
        </p>
        <ul className="divide-y divide-rule border-y border-rule">
          {sources.map((source) => (
            <li key={source.externalId}>
              <Link href={`/source/${source.externalId}`} className="block py-3 hover:bg-bg-elev px-2">
                <div className="font-serif">{source.title}</div>
                <div className="text-xs font-mono text-ink-faint mt-1">
                  {source.externalId} · {recordTypeLabel(source.type)} · {source.agency} · {processingStateLabel(source.processingState)}
                  {source.acceptedFragmentCount > 0 ? ` · ${source.acceptedFragmentCount} checked ${source.acceptedFragmentCount === 1 ? "passage" : "passages"}` : ""}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </main>
      <Footer />
    </>
  );
}
