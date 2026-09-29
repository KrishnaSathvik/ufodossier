import { listSources, sourceFacets } from "@/lib/corpus/catalog";
import { documentClassLabel, processingStateLabel, recordTypeLabel, releaseLabel } from "@/lib/labels";
import Link from "next/link";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Source Records",
  description: "Official files from the PURSUE releases, filtered by release, agency, file type, and document type.",
  alternates: { canonical: "/sources" },
  openGraph: {
    title: "Sources — UFO Dossier",
    description: "Official files, documents, recordings, and released source records.",
    images: [{ url: "/og/sources.png", width: 1200, height: 630, alt: "Sources — UFO Dossier" }],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og/sources.png"],
  },
};

type Search = Record<string, string | string[] | undefined>;

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default async function SourcesPage({ searchParams }: { searchParams: Promise<Search> }) {
  const params = await searchParams;
  const release = one(params.release);
  const agency = one(params.agency);
  const type = one(params.type);
  const documentClass = one(params.class);
  const state = one(params.state);
  const facets = sourceFacets();
  const sources = listSources({
    release: release ? Number(release) : undefined,
    agency: agency || undefined,
    type: type || undefined,
    documentClass: documentClass || undefined,
    state: state || undefined,
  });

  return (
    <>

      <main className="site-shell py-10 md:py-14">
        <h1 className="lg:text-4xl font-serif text-2xl md:text-4xl font-medium mb-3">Source records</h1>
        <p className="text-ink-dim max-w-prose mb-6">
          {sources.length.toLocaleString()} files match these filters. A file can be a sighting report,
          program paperwork, or a photo, video, or audio recording.
        </p>
        <form method="get" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-8 text-sm">
          <Select name="release" label="Release" value={release} options={facets.releases.map((n) => [String(n), `Release ${String(n).padStart(2, "0")}`])} />
          <Select name="agency" label="Agency" value={agency} options={facets.agencies.map((item) => [item, item])} />
          <Select name="type" label="File type" value={type} options={facets.types.map((item) => [item, recordTypeLabel(item)])} />
          <Select name="class" label="Document type" value={documentClass} options={facets.classes.map((item) => [item, documentClassLabel(item)])} />
          <Select name="state" label="Status" value={state} options={facets.states.map((item) => [item, processingStateLabel(item)])} />
          <div className="flex items-end gap-2">
            <button type="submit" className="border border-rule px-3 py-2 hover:border-ink-faint">Apply</button>
            <Link href="/sources" className="border border-rule px-3 py-2 text-ink-dim hover:text-ink">Clear</Link>
          </div>
        </form>
        {sources.length === 0 ? (
          <p className="text-ink-faint">No source records match these filters.</p>
        ) : (
          <ul className="divide-y divide-rule border-y border-rule [overflow-wrap:anywhere]">
            {sources.map((source) => (
              <li key={source.slug}>
                <Link href={`/source/${source.slug}`} className="block py-3 px-2 hover:bg-bg-elev">
                  <div className="font-serif">{source.title}</div>
                  <div className="text-xs font-mono text-ink-faint mt-1">
                    {releaseLabel(source.release)} · {source.agency} · {recordTypeLabel(source.type)} · {documentClassLabel(source.classification)} · {processingStateLabel(source.processingState)}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>

    </>
  );
}

function Select({ name, label, value, options }: { name: string; label: string; value: string; options: [string, string][] }) {
  return (
    <label className="block min-w-0">
      <span className="block text-xs font-mono uppercase tracking-tracked text-ink-faint mb-1">{label}</span>
      <select name={name} defaultValue={value} className="w-full min-w-0 max-w-full bg-bg border border-rule px-2 py-2 text-ink">
        <option value="">Any</option>
        {options.map(([id, text]) => (
          <option key={id} value={id}>{text}</option>
        ))}
      </select>
    </label>
  );
}
