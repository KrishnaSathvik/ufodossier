import { TopBar } from "@/components/TopBar";
import { Footer } from "@/components/Footer";
import { JsonLd } from "@/components/JsonLd";
import { getSupabase } from "@/lib/supabase";
import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";

export const revalidate = 600;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function getIncident(idOrSlug: string) {
  const sb = getSupabase();

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
  if (!slugRow) return null;

  const { data } = await sb.from("v_incident_full").select("*").eq("id", slugRow.id).single();
  if (data) data.slug = slugRow.slug;
  return data;
}

async function getSimilar(id: string) {
  const sb = getSupabase();
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

  // If accessed by UUID and slug exists, redirect to slug URL
  if (UUID_RE.test(idOrSlug) && incident.slug) {
    redirect(`/incident/${incident.slug}`);
  }

  const similar = await getSimilar(incident.id);

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "Report",
        name: incident.title,
        description: incident.summary,
        datePublished: incident.occurred_at ?? undefined,
        url: `https://ufodossier.com/incident/${incident.slug ?? incident.id}`,
        author: { "@type": "Organization", name: incident.source_agency ?? "U.S. Government" },
        isPartOf: {
          "@type": "Dataset",
          name: "UFO Dossier — Declassified UAP Archive",
          url: "https://ufodossier.com",
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
      <TopBar />

      <article className="max-w-prose mx-auto px-4 md:px-6 pt-10 md:pt-16 pb-12">
        <Link href="/" className="text-sm text-ink-faint hover:text-ink transition-colors">
          &larr; Archive
        </Link>

        {/* Header */}
        <header className="mt-6 mb-8">
          <h1 className="font-serif text-2xl md:text-4xl font-medium leading-snug mb-4">
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
            <p className="text-xs text-ink-faint px-3 py-2 font-mono">
              Page 1 of {incident.source_filename}
              {incident.source_url && (
                <> &middot; <a href={incident.source_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">View original on war.gov</a></>
              )}
            </p>
          </div>
        )}

        {/* Summary */}
        <p className="text-ink-dim leading-relaxed mb-8 text-[17px]">
          {incident.summary}
        </p>

        {/* Verbatim excerpt */}
        <blockquote className="border-l-2 border-accent pl-5 py-3 my-8">
          <p className="font-serif italic text-[17px] leading-relaxed text-ink">
            &ldquo;{incident.raw_excerpt}&rdquo;
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
            <DetailField label="Precision" value={incident.occurred_at_precision} />
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

        {/* Methodology note */}
        <section className="border-t border-rule pt-6 mb-10">
          <p className="text-sm text-ink-faint leading-relaxed">
            Fields above were extracted by an LLM from the source document.
            The verbatim excerpt is substring-validated against the original text.
            Dashes indicate the source did not specify a value.
          </p>
        </section>

        {/* Source */}
        <section className="mb-10">
          <h2 className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">Source document</h2>
          <div className="text-sm text-ink-dim space-y-1">
            <p>Agency: {incident.source_agency ?? "Unknown"}</p>
            <p>File: {incident.source_filename ?? "Unknown"}</p>
            <p>Case ID: <span className="font-mono text-xs">{incident.case_id}</span></p>
            {incident.source_url && (
              <a href={incident.source_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline inline-block mt-1">
                View original on war.gov &rarr;
              </a>
            )}
          </div>
        </section>

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
                  <div className="font-serif text-[15px] text-ink mb-1">{s.title}</div>
                  <div className="text-xs text-ink-faint font-mono">
                    {s.occurred_at ?? "Undated"}{s.branch ? ` / ${s.branch}` : ""}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </article>

      <Footer />
    </>
  );
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
