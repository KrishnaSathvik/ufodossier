import { JsonLd } from "@/components/JsonLd";
import { RedactedExcerpt } from "@/components/RedactedExcerpt";
import { ShareRow } from "@/components/ShareRow";
import { getSupabaseServer } from "@/lib/supabase";
import { getFragmentBySlug, getSource, identityForCase } from "@/lib/corpus/catalog";
import { datePrecisionLabel, sightingLabel, sourceRolePhrase } from "@/lib/labels";
import { notFound, redirect } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";

export const revalidate = 600;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function getIncident(idOrSlug: string) {
  const sb = getSupabaseServer();

  if (UUID_RE.test(idOrSlug)) {
    const { data } = await sb.from("v_incident_full").select("*").eq("id", idOrSlug).single();
    if (data) {
      const { data: slugRow } = await sb.from("incidents").select("slug").eq("id", idOrSlug).single();
      data.slug = slugRow?.slug ?? null;
    }
    return data;
  }

  // Resolve slug to UUID
  const { data: slugRow } = await sb.from("incidents").select("id, slug").eq("slug", idOrSlug).single();
  if (!slugRow) return localIncident(idOrSlug);

  const { data } = await sb.from("v_incident_full").select("*").eq("id", slugRow.id).single();
  if (data) data.slug = slugRow.slug;
  if (data) return data;
  return localIncident(idOrSlug);
}

function localIncident(idOrSlug: string) {
  const fragment = getFragmentBySlug(idOrSlug);
  if (!fragment) return null;
  const source = fragment.sourceExternalId ? getSource(fragment.sourceExternalId) : null;
  return {
    id: fragment.caseId,
    slug: fragment.slug,
    case_id: fragment.caseId,
    title: fragment.title,
    summary: fragment.summary,
    raw_excerpt: fragment.rawExcerpt,
    occurred_at: fragment.occurredAt,
    occurred_at_text: fragment.occurredAtText,
    occurred_at_precision: fragment.occurredAtPrecision,
    location_text: fragment.locationText,
    country: fragment.country,
    region: fragment.region,
    branch: fragment.branch,
    reporting_unit: fragment.reportingUnit,
    resolution_status: fragment.resolutionStatus,
    resolution_notes: fragment.resolutionNotes,
    sensor_types: fragment.sensorTypes,
    shape_description: fragment.shapeDescription,
    size_description: fragment.sizeDescription,
    altitude_feet: fragment.altitudeFeet,
    duration_seconds: fragment.durationSeconds,
    source_filename: fragment.sourceFilename,
    source_agency: source?.agency ?? fragment.branch,
    source_url: source?.originalUrl ?? null,
    source_page_count: source?.pageCount ?? null,
    image_url: null,
    video_url: null,
    cover_image_url: null,
    source_cover_image_url: null,
    lat: null,
    lon: null,
    local_only: true,
  };
}

async function getSimilar(id: string) {
  if (!UUID_RE.test(id)) return [];
  const sb = getSupabaseServer();
  const { data: inc } = await sb
    .from("incidents")
    .select("embedding")
    .eq("id", id)
    .single();

  if (!inc?.embedding) {
    const { data } = await sb.from("incidents").select("id, slug, case_id, occurred_at, title, branch").neq("id", id).limit(4);
    return data ?? [];
  }

  const { data: matches } = await sb.rpc("match_incidents", {
    query_embedding: inc.embedding,
    match_threshold: 0.3,
    match_count: 5,
  });

  if (!matches) return [];

  // Fetch slugs for matched incidents
  const ids = matches.filter((m: any) => m.id !== id).slice(0, 4).map((m: any) => m.id);
  if (ids.length === 0) return [];

  const { data: slugRows } = await sb.from("incidents").select("id, slug").in("id", ids);
  const slugMap = new Map((slugRows ?? []).map((r: any) => [r.id, r.slug]));

  return matches
    .filter((m: any) => m.id !== id)
    .slice(0, 4)
    .map((m: any) => ({ ...m, slug: slugMap.get(m.id) ?? null }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const incident = await getIncident(slug);
  if (!incident) return {};

  const canonical = `/incident/${incident.slug ?? slug}`;

  return {
    title: incident.title,
    description: incident.summary,
    alternates: { canonical },
    openGraph: {
      title: incident.title,
      description: incident.summary,
      type: "article",
      url: canonical,
    },
    twitter: {
      card: "summary_large_image",
      title: incident.title,
      description: incident.summary,
    },
  };
}

export default async function IncidentPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug: idOrSlug } = await params;
  const incident = await getIncident(idOrSlug);
  if (!incident) notFound();
  const identity = incident.case_id ? identityForCase(String(incident.case_id)) : null;

  // If accessed by UUID and slug exists, redirect to slug URL
  if (UUID_RE.test(idOrSlug) && incident.slug) {
    redirect(`/incident/${incident.slug}`);
  }

  const similar = await getSimilar(incident.id);
  const relatedCases = (identity?.memberCaseIds ?? [])
    .filter((caseId) => caseId.toUpperCase() !== String(incident.case_id ?? "").toUpperCase())
    .map((caseId) => getFragmentBySlug(caseId))
    .filter((row) => row != null);

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "Report",
        name: incident.title,
        description: incident.summary,
        datePublished: incident.occurred_at ?? undefined,
        url: `https://www.ufodossier.com/incident/${incident.slug ?? incident.id}`,
        author: { "@type": "Organization", name: incident.source_agency ?? "U.S. Government" },
        isPartOf: {
          "@type": "Dataset",
          name: "UFO Dossier — Declassified UAP Archive",
          description: "A searchable archive of publicly released U.S. government UAP records. Quotes are checked against the original files.",
          url: "https://www.ufodossier.com",
        },
        ...(incident.location_text ? {
          spatialCoverage: {
            "@type": "Place",
            name: incident.location_text,
            ...(incident.lat && incident.lon ? {
              geo: { "@type": "GeoCoordinates", latitude: incident.lat, longitude: incident.lon },
            } : {}),
          },
        } : {}),
      }} />


      <article className="reading-shell pt-10 md:pt-16 lg:pt-14 pb-12">
        <BackLink href="/" />

        {/* Header */}
        <header className="mt-6 mb-8">
          <h1 className="lg:text-4xl font-serif text-2xl md:text-4xl font-medium leading-snug mb-4">
            {incident.title}
          </h1>

          {/* Metadata line */}
          <div className="flex flex-wrap items-center gap-y-1 text-sm text-ink-dim">
            <span>{incident.occurred_at ?? incident.occurred_at_text ?? "Undated"}</span>
            {incident.location_text && (
              <>
                <span className="mx-2 text-ink-faint">&middot;</span>
                <span>{incident.location_text}</span>
              </>
            )}
            {incident.branch && (
              <>
                <span className="mx-2 text-ink-faint">&middot;</span>
                <span className="font-mono text-xs uppercase">{incident.branch}</span>
              </>
            )}
            <span className="mx-2 text-ink-faint">&middot;</span>
            <span className={`font-mono text-xs uppercase ${
              incident.resolution_status === "unresolved" ? "text-critical" :
              incident.resolution_status === "identified" ? "text-ink-dim" :
              "text-ink-faint"
            }`}>
              {incident.resolution_status?.replace("_", " ")}
            </span>
          </div>
        </header>

        {/* Media */}
        {incident.video_url && (
          <div className="mb-8 bg-bg-quiet overflow-hidden">
            {incident.video_url.includes("dvidshub.net") ? (
              <div className="aspect-video">
                <iframe
                  src={incident.video_url}
                  title={`Source video for ${incident.title}`}
                  allow="autoplay; fullscreen"
                  allowFullScreen
                  className="w-full h-full border-0"
                />
              </div>
            ) : (
              <video controls preload="metadata" className="w-full max-h-[480px]">
                <source src={incident.video_url} type="video/mp4" />
              </video>
            )}
            <p className="text-xs text-ink-faint px-3 py-2 font-mono">
              Source: {incident.source_filename}
              {incident.source_duration_seconds && ` / ${Math.floor(incident.source_duration_seconds / 60)}:${String(incident.source_duration_seconds % 60).padStart(2, "0")}`}
            </p>
          </div>
        )}
        {!incident.video_url && incident.image_url && (
          <div className="mb-8 bg-bg-quiet overflow-hidden">
            <div className="relative w-full" style={{ minHeight: "300px", maxHeight: "600px", height: "50vw" }}>
              <Image
                src={incident.image_url}
                alt={`Source image for ${incident.title}`}
                fill
                sizes="(max-width: 768px) 100vw, 680px"
                className="object-contain"
              />
            </div>
            <p className="text-xs text-ink-faint px-3 py-2 font-mono">
              Source: {incident.source_filename}
            </p>
          </div>
        )}
        {!incident.video_url && !incident.image_url && (incident.cover_image_url || incident.source_cover_image_url) && (
          <div className="mb-8 bg-bg-quiet overflow-hidden border border-rule">
            {incident.source_url ? (
              <a href={incident.source_url} target="_blank" rel="noopener noreferrer" className="block relative cursor-pointer" style={{ minHeight: "240px", maxHeight: "400px", height: "40vw" }}>
                <Image
                  src={incident.cover_image_url || incident.source_cover_image_url}
                  alt={`Document cover: ${incident.source_filename}`}
                  fill
                  sizes="(max-width: 768px) 100vw, 680px"
                  className="object-contain opacity-90"
                />
                <span className="absolute top-2 left-2 bg-bg/90 border border-rule px-2 py-0.5 text-[10px] font-mono uppercase tracking-tracked text-ink-faint">
                  Document cover
                </span>
              </a>
            ) : (
              <div className="relative" style={{ minHeight: "240px", maxHeight: "400px", height: "40vw" }}>
                <Image
                  src={incident.cover_image_url || incident.source_cover_image_url}
                  alt={`Document cover: ${incident.source_filename}`}
                  fill
                  sizes="(max-width: 768px) 100vw, 680px"
                  className="object-contain opacity-90"
                />
                <span className="absolute top-2 left-2 bg-bg/90 border border-rule px-2 py-0.5 text-[10px] font-mono uppercase tracking-tracked text-ink-faint">
                  Document cover
                </span>
              </div>
            )}
            <p className="text-xs text-ink-faint px-3 py-2 font-mono">
              Page 1 of {incident.source_filename}
              {incident.source_page_count && ` (${incident.source_page_count} pages total)`}
              {incident.source_url && (
                <> &middot; <a href={incident.source_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">View original on war.gov</a></>
              )}
            </p>
          </div>
        )}

        {/* Summary */}
        <p className="text-ink-dim leading-relaxed mb-8 text-[17px] lg:text-base">
          {incident.summary}
        </p>

        {/* Verbatim excerpt */}
        <blockquote className="border-l-2 border-accent pl-5 py-3 my-8">
          <p className="font-serif italic text-[17px] lg:text-base leading-relaxed text-ink">
            &ldquo;<RedactedExcerpt text={incident.raw_excerpt} />&rdquo;
          </p>
          <cite className="block mt-3 text-xs text-ink-faint font-mono not-italic">
            Verbatim from {incident.source_filename}
            {incident.source_url && (
              <>
                {" "}&middot;{" "}
                <a href={incident.source_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                  View original on war.gov
                </a>
              </>
            )}
          </cite>
        </blockquote>

        {/* Detail fields */}
        <section className="border-t border-rule pt-6 mb-8">
          <h2 className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-4">Case details</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <DetailField label="Date" value={incident.occurred_at ?? incident.occurred_at_text} />
            <DetailField label="Date exactness" value={datePrecisionLabel(incident.occurred_at_precision)} />
            <DetailField label="Location" value={incident.location_text} />
            <DetailField label="Country" value={incident.country} />
            <DetailField label="Region" value={incident.region} />
            <DetailField label="Branch" value={incident.branch} />
            <DetailField label="Unit" value={incident.reporting_unit} />
            <DetailField label="Sensors" value={incident.sensor_types?.join(", ")} />
            <DetailField label="Shape" value={incident.shape_description} />
            <DetailField label="Size" value={incident.size_description} />
            {incident.altitude_feet && <DetailField label="Altitude" value={`${incident.altitude_feet} ft`} />}
            {incident.duration_seconds && <DetailField label="Duration" value={`${incident.duration_seconds}s`} />}
          </dl>
        </section>

        {/* Resolution notes */}
        {incident.resolution_notes && (
          <section className="mb-8">
            <h2 className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">Resolution</h2>
            <p className="text-ink-dim leading-relaxed">{incident.resolution_notes}</p>
          </section>
        )}

        {/* Source */}
        <section className="mb-10">
          <h2 className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">Source document</h2>
          <div className="text-sm text-ink-dim space-y-1">
            <p>Agency: {incident.source_agency ?? "Unknown"}</p>
            <p>File: <SourceFileName filename={incident.source_filename} /></p>
            <p>Case ID: <span className="font-mono text-xs">{incident.case_id}</span></p>
            {incident.source_url && (
              <a href={incident.source_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline inline-block mt-1">
                View original on war.gov &rarr;
              </a>
            )}
          </div>
          <p className="text-xs text-ink-faint mt-4">
            Quote checked against the original file.
          </p>
        </section>

        {identity && (
          <section className="mb-10 border-t border-rule pt-6">
            <h2 className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">This sighting</h2>
            <p className="font-serif text-lg">{sightingLabel(identity.eventLabel)}</p>
            {relatedCases.length > 0 && (
              <div className="text-sm text-ink-dim mt-3">
                <p>Also described in</p>
                <ul className="mt-1 space-y-1">
                  {relatedCases.map((related) => (
                    <li key={related.caseId}>
                      <Link href={`/incident/${related.slug}`} className="text-accent hover:underline">
                        {related.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {identity.sourceRoles.length > 0 && (
              <ul className="mt-3 text-sm text-ink-dim space-y-1">
                {identity.sourceRoles.map((role) => (
                  <li key={`${role.filename}-${role.role}`}>
                    <SourceFileName filename={role.filename} />
                    <span> — {sourceRolePhrase(role.role)}</span>
                  </li>
                ))}
              </ul>
            )}
            {identity.seriesLabel && (
              <p className="text-sm text-ink-dim mt-3">
                Part of {sightingLabel(identity.seriesLabel)}, a group of {identity.seriesEventCount} separate sightings.
              </p>
            )}
          </section>
        )}

        {/* Share */}
        <ShareRow
          url={`/incident/${incident.slug ?? incident.id}`}
          title={incident.title}
        />

        {/* Similar incidents */}
        {similar.length > 0 && (
          <section className="border-t border-rule pt-8">
            <h2 className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-5">Related incidents</h2>
            <div className="space-y-3">
              {similar.map((s: any) => (
                <Link
                  key={s.id}
                  href={`/incident/${s.slug || s.id}`}
                  className="block py-3 border-b border-rule hover:bg-bg-elev transition-colors -mx-2 px-2"
                >
                  <div className="font-serif text-[15px] lg:text-base text-ink mb-1">{s.title}</div>
                  <div className="text-xs text-ink-faint font-mono">
                    {s.occurred_at ?? "Undated"}{s.branch ? ` / ${s.branch}` : ""}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </article>

    </>
  );
}

function SourceFileName({ filename }: { filename?: string | null }) {
  if (!filename) return <>Unknown</>;
  const id = filename.match(/^([A-Z0-9]+-UAP-[A-Z0-9]+)/i)?.[1]?.toUpperCase();
  const source = id ? getSource(id) : null;
  if (source?.originalUrl) {
    return (
      <a href={source.originalUrl} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
        {filename}
      </a>
    );
  }
  if (source) {
    return (
      <Link href={`/source/${source.externalId}`} className="text-accent hover:underline">
        {filename}
      </Link>
    );
  }
  return <>{filename}</>;
}

function DetailField({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-ink-faint text-xs">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
