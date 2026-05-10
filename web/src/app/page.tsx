import { TopBar } from "@/components/TopBar";
import { Footer } from "@/components/Footer";
import { IncidentList } from "@/components/IncidentList";
import { JsonLd } from "@/components/JsonLd";
import { RedactedExcerpt } from "@/components/RedactedExcerpt";
import { getSupabase } from "@/lib/supabase";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";

export const revalidate = 300; // 5 min

export const metadata: Metadata = {
  alternates: { canonical: "/" },
  description: "A searchable archive of UAP incidents extracted from declassified U.S. government documents. Every claim sourced. Every document linked.",
};

async function getStats() {
  const sb = getSupabase();
  const { data } = await sb.from("v_stats").select("*").single();
  return data ?? {
    incident_count: 0,
    source_file_count: 0,
    unresolved_count: 0,
    country_count: 0,
    earliest: null,
    latest: null,
  };
}

async function getAllIncidents(limit = 30) {
  const sb = getSupabase();
  const { data } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, source_agency, location_text, country, region, resolution_status, sensor_types, image_url, video_url, summary, raw_excerpt, case_id")
    .order("occurred_at", { ascending: false, nullsFirst: false })
    .limit(limit);
  return data ?? [];
}

async function getFeatured() {
  const sb = getSupabase();
  // Priority 1: unresolved with real image
  const { data } = await sb
    .from("v_incident_full")
    .select("*")
    .eq("resolution_status", "unresolved")
    .not("image_url", "is", null)
    .order("occurred_at", { ascending: false, nullsFirst: false })
    .limit(1);
  if (data?.[0]) return data[0];

  // Priority 2: unresolved with cover image
  const { data: withCover } = await sb
    .from("v_incident_full")
    .select("*")
    .eq("resolution_status", "unresolved")
    .not("cover_image_url", "is", null)
    .order("occurred_at", { ascending: false, nullsFirst: false })
    .limit(1);
  if (withCover?.[0]) return withCover[0];

  // Priority 3: any unresolved
  const { data: fallback } = await sb
    .from("v_incident_full")
    .select("*")
    .eq("resolution_status", "unresolved")
    .order("occurred_at", { ascending: false, nullsFirst: false })
    .limit(1);
  return fallback?.[0] ?? null;
}

export default async function HomePage() {
  const [stats, incidents, featured] = await Promise.all([
    getStats(),
    getAllIncidents(),
    getFeatured(),
  ]);

  const earliestYear = stats.earliest ? parseInt(stats.earliest.split("-")[0]) : 1947;
  const latestYear = stats.latest ? parseInt(stats.latest.split("-")[0]) : 2025;
  const unresolvedPct =
    stats.incident_count > 0
      ? Math.round((stats.unresolved_count / stats.incident_count) * 100)
      : 0;

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "Dataset",
        name: "UFO Dossier — Declassified UAP Archive",
        description: `A searchable archive of ${stats.incident_count} UAP incidents extracted from ${stats.source_file_count} declassified U.S. government source documents.`,
        url: "https://ufodossier.com",
        license: "https://creativecommons.org/publicdomain/zero/1.0/",
        creator: { "@type": "Organization", name: "UFO Dossier" },
        temporalCoverage: `${earliestYear}/${latestYear}`,
        distribution: {
          "@type": "DataDownload",
          contentUrl: "https://ufodossier.com/sitemap.xml",
          encodingFormat: "application/xml",
        },
      }} />
      <TopBar active="archive" />

      <main className="max-w-content mx-auto px-4 md:px-6">
        {/* Hero */}
        <section className="pt-16 md:pt-24 pb-10 md:pb-14">
          <h1 className="font-serif text-[clamp(32px,5vw,56px)] font-medium leading-[1.1] tracking-tight mb-5 max-w-[720px]">
            Every UAP incident in the U.S. government&apos;s declassified&nbsp;files.
          </h1>
          <p className="text-lg md:text-xl text-ink-dim max-w-prose leading-relaxed">
            A searchable archive of {stats.incident_count.toLocaleString()} incidents
            extracted from {stats.source_file_count} source documents spanning {earliestYear}&ndash;{latestYear}.
            Every claim sourced. Every document linked.
          </p>
        </section>

        {/* Stats strip */}
        <section className="flex flex-wrap gap-x-8 gap-y-3 py-5 border-y border-rule text-sm">
          <StatPill label="Incidents" value={stats.incident_count.toLocaleString()} />
          <StatPill label="Countries" value={String(stats.country_count)} />
          <StatPill label="Unresolved" value={`${stats.unresolved_count.toLocaleString()} (${unresolvedPct}%)`} />
          <StatPill label="Years" value={`${earliestYear}\u2013${latestYear}`} />
          <StatPill label="Sources" value={String(stats.source_file_count)} />
        </section>

        {/* Featured case */}
        {featured && (
          <section className="py-10 md:py-14 border-b border-rule">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12">
              <div>
                <p className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">Featured case</p>
                <h2 className="font-serif text-2xl md:text-3xl font-medium leading-snug mb-4">
                  {featured.title}
                </h2>
                <p className="text-ink-dim leading-relaxed mb-4">
                  {featured.summary}
                </p>
                {featured.raw_excerpt && (
                  <blockquote className="border-l-2 border-accent pl-4 py-1 my-5 text-sm text-ink-dim italic">
                    &ldquo;<RedactedExcerpt text={featured.raw_excerpt} />&rdquo;
                  </blockquote>
                )}
                <div className="flex items-center gap-4 text-sm text-ink-faint">
                  <span className="font-mono text-xs">{featured.occurred_at ?? "Undated"}</span>
                  {featured.branch && <span className="font-mono text-xs uppercase">{featured.branch}</span>}
                  <Link
                    href={`/incident/${featured.slug || featured.id}`}
                    className="text-accent hover:text-accent-dim transition-colors ml-auto"
                  >
                    Read case file &rarr;
                  </Link>
                </div>
              </div>
              {featured.image_url ? (
                <div className="bg-bg-quiet overflow-hidden relative min-h-[240px]">
                  <Image
                    src={featured.image_url}
                    alt={`Source image: ${featured.title}`}
                    fill
                    sizes="(max-width: 768px) 100vw, 50vw"
                    className="object-contain"
                  />
                </div>
              ) : featured.video_url ? (
                <div className="bg-bg-quiet overflow-hidden">
                  <video controls preload="metadata" className="w-full h-full min-h-[240px]">
                    <source src={featured.video_url} type="video/mp4" />
                  </video>
                </div>
              ) : (featured.cover_image_url || featured.source_cover_image_url) ? (
                <div className="bg-bg-quiet overflow-hidden border border-rule relative min-h-[240px]">
                  <Image
                    src={featured.cover_image_url || featured.source_cover_image_url}
                    alt={`Document cover: ${featured.title}`}
                    fill
                    sizes="(max-width: 768px) 100vw, 50vw"
                    className="object-contain opacity-90"
                  />
                  <span className="absolute top-2 left-2 bg-bg/90 border border-rule px-2 py-0.5 text-[10px] font-mono uppercase tracking-tracked text-ink-faint">
                    Document cover
                  </span>
                </div>
              ) : null}
            </div>
          </section>
        )}

        {/* Incident list */}
        <section className="py-10 md:py-14">
          <h2 className="font-serif text-xl font-medium mb-6">
            Recent incidents
          </h2>

          <div>
            <IncidentList incidents={incidents} />
          </div>

          <div className="pt-6 text-center">
            <Link
              href="/incidents"
              className="inline-block px-5 py-2 border border-rule text-sm font-medium hover:border-ink-faint transition-colors"
            >
              View all incidents &rarr;
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-ink-faint">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}
