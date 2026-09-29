import { JsonLd } from "@/components/JsonLd";
import { eventsForSource, fragmentsForSource, getSource } from "@/lib/corpus/catalog";
import { documentClassLabel, processingStateLabel, recordTypeLabel, releaseLabel, sightingLabel, sourceRolePhrase } from "@/lib/labels";
import { BackLink } from "@/components/BackLink";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const source = getSource(id);
  if (!source) return { title: "Source" };
  return {
    title: source.title,
    description: source.description?.slice(0, 180) || `Official source record ${source.externalId}.`,
    alternates: { canonical: `/source/${source.externalId}` },
    openGraph: { title: source.title, description: source.description?.slice(0, 180) ?? source.title },
  };
}

export default async function SourcePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const source = getSource(id);
  if (!source) notFound();
  const fragments = fragmentsForSource(source.externalId);
  const events = eventsForSource(source.externalId);
  const jsonLdType = source.type === "video" ? "VideoObject" : source.type === "audio" ? "AudioObject" : source.type === "image" ? "ImageObject" : "Article";
  const back = source.type === "audio"
    ? { href: "/audio", label: "Audio", nav: "audio" }
    : { href: "/sources", label: "Sources", nav: "sources" };

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": jsonLdType,
        name: source.title,
        description: source.description ?? undefined,
        url: `https://www.ufodossier.com/source/${source.externalId}`,
        ...(source.originalUrl ? { contentUrl: source.originalUrl } : {}),
      }} />

      <article className="document-shell py-10 md:py-14">
        <BackLink href={back.href} />
        <h1 className="lg:text-4xl font-serif text-2xl md:text-4xl font-medium mt-4 mb-4">{source.title}</h1>
        {source.dvidsId && (
          <div className="mb-6 border border-rule bg-bg-quiet">
            <div className="aspect-video">
              <iframe
                src={`https://www.dvidshub.net/video/embed/${source.dvidsId}`}
                title={source.title}
                allow="autoplay; fullscreen"
                allowFullScreen
                className="w-full h-full border-0"
              />
            </div>
            <p className="px-3 py-2 text-xs text-ink-faint">
              Same recording as the official release.{" "}
              <a
                href={`https://www.dvidshub.net/video/${source.dvidsId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                Open on DVIDS
              </a>
            </p>
          </div>
        )}
        {source.description && <p className="reading-column text-ink-dim leading-relaxed mb-6">{source.description}</p>}
        <dl className="source-metadata grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3 text-sm border-y border-rule py-5">
          <Field label="Agency" value={source.agency} />
          <Field label="Release" value={releaseLabel(source.release)} />
          <Field label="File type" value={recordTypeLabel(source.type)} />
          <Field label="Document type" value={documentClassLabel(source.classification)} />
          <Field label="Case written up" value={source.containsIncidents ? "Yes" : "No"} />
          <Field label="Status" value={processingStateLabel(source.processingState)} />
          {source.pageCount != null && <Field label="Pages" value={String(source.pageCount)} />}
        </dl>
        {source.originalUrl && (
          <a href={source.originalUrl} target="_blank" rel="noopener noreferrer" className="inline-block mt-4 text-accent hover:underline">
            View the file on war.gov
          </a>
        )}

        <section className="mt-10">
          <h2 className="font-serif text-xl mb-3">Case files from this document</h2>
          {fragments.length === 0 ? (
            <p className="text-ink-dim">No case is written up from this file.</p>
          ) : (
            <ul className="related-records space-y-3">
              {fragments.map((fragment) => (
                <li key={fragment.caseId}>
                  <Link href={`/incident/${fragment.slug}`} className="hover:text-accent">
                    <span className="font-mono text-xs">{fragment.caseId}</span>
                    <span className="block font-serif">{fragment.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mt-10">
          <h2 className="font-serif text-xl mb-3">Sightings tied to this file</h2>
          {events.length === 0 ? (
            <p className="text-ink-dim">This file is not tied to a sighting.</p>
          ) : (
            <ul className="related-records space-y-4">
              {events.map((event) => (
                <li key={event.eventId} className="border-l-2 border-accent pl-4">
                  <p className="font-serif">{sightingLabel(event.label)}</p>
                  <p className="text-sm text-ink-dim mt-1">
                    {event.roles.map((role) => sourceRolePhrase(role.role)).join(", ") || "Related file"}
                  </p>
                  {event.series && (
                    <p className="text-sm text-ink-dim mt-1">
                      Part of {sightingLabel(event.series.label)}, a group of {event.series.event_ids.length} separate sightings.
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </article>

    </>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="break-all">{value || "Not recorded"}</dd>
    </div>
  );
}
