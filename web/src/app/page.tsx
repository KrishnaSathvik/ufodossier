import { HeaderShell } from "@/components/HeaderShell";
import { Footer } from "@/components/Footer";
import { IncidentList } from "@/components/IncidentList";
import { JsonLd } from "@/components/JsonLd";
import { RedactedExcerpt } from "@/components/RedactedExcerpt";
import { getSupabaseServer } from "@/lib/supabase";
import { getCorpusStats } from "@/lib/corpus/catalog";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";

export const revalidate = 300; // 5 min

export const metadata: Metadata = {
  alternates: { canonical: "/" },
  description: "A searchable, source-grounded archive of publicly released U.S. government UAP records.",
};

async function getStats() {
  const sb = getSupabaseServer();
  const { data } = await sb.from("v_stats").select("*").single();
  const base = data ?? {
    incident_count: 0,
    source_file_count: 0,
    unresolved_count: 0,
    country_count: 0,
    earliest: null,
    latest: null,
  };

  // Public case-file count is unflagged incidents. Flagged duplicate excerpts stay out.
  const { count: curated } = await sb
    .from("incidents")
    .select("id", { count: "exact", head: true })
    .eq("flagged", false);
  const { count: unresolvedCurated } = await sb
    .from("incidents")
    .select("id", { count: "exact", head: true })
    .eq("flagged", false)
    .eq("resolution_status", "unresolved");

  return {
    ...base,
    incident_count: curated ?? base.incident_count,
    unresolved_count: unresolvedCurated ?? base.unresolved_count,
  };
}

async function getAllIncidents(limit = 30) {
  const sb = getSupabaseServer();
  const { data } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, source_agency, location_text, country, region, resolution_status, sensor_types, image_url, video_url, summary, raw_excerpt, case_id, tranche_number")
    .eq("flagged", false)
    .order("tranche_number", { ascending: false, nullsFirst: false })
    .order("occurred_at", { ascending: false, nullsFirst: false })
    .limit(limit);
  return data ?? [];
}

async function getFeatured() {
  const sb = getSupabaseServer();
  const { data } = await sb
    .from("v_incident_full")
    .select("*")
    .eq("flagged", false)
    .eq("resolution_status", "unresolved")
    .not("tranche_number", "is", null)
    .order("tranche_number", { ascending: false, nullsFirst: false })
    .order("occurred_at", { ascending: false, nullsFirst: false })
    .limit(1);
  return data?.[0] ?? null;
}

export default async function HomePage() {
  const [stats, incidents, featured, corpus] = await Promise.all([
    getStats(),
    getAllIncidents(),
    getFeatured(),
    Promise.resolve(getCorpusStats()),
  ]);

  const earliestYear = stats.earliest ? parseInt(stats.earliest.split("-")[0]) : 1947;
  const latestYear = stats.latest ? parseInt(stats.latest.split("-")[0]) : 2025;

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "Dataset",
        name: "UFO Dossier — Declassified UAP Archive",
        description: `A searchable archive of publicly released U.S. government UAP records. ${corpus.fragments.toLocaleString()} checked passages and ${corpus.canonicalEvents.toLocaleString()} sightings, drawn from ${corpus.officialRecords.toLocaleString()} official files across ${corpus.releases} PURSUE releases.`,
        url: "https://www.ufodossier.com",
        license: "https://creativecommons.org/publicdomain/zero/1.0/",
        creator: { "@type": "Organization", name: "UFO Dossier" },
        temporalCoverage: `${earliestYear}/${latestYear}`,
        distribution: {
          "@type": "DataDownload",
          contentUrl: "https://www.ufodossier.com/sitemap.xml",
          encodingFormat: "application/xml",
        },
      }} />
      <HeaderShell active="archive" showBanner />

      <main className="max-w-content mx-auto px-4 md:px-6">
        {/* Hero */}
        <section className="pt-16 md:pt-24 pb-10 md:pb-14 border-b border-rule">
          <h1 className="font-serif text-[clamp(32px,5vw,56px)] font-medium leading-[1.1] tracking-tight mb-5 max-w-[720px]">
            A searchable, source-grounded archive of publicly released U.S. government UAP&nbsp;records.
          </h1>
          <p className="text-lg md:text-xl text-ink-dim max-w-prose leading-relaxed">
            {corpus.fragments.toLocaleString()} checked passages and {corpus.canonicalEvents.toLocaleString()} sightings,
            drawn from {corpus.officialRecords.toLocaleString()} official files across {corpus.releases} releases from PURSUE,
            the Pentagon program that published these unidentified anomalous phenomena (UAP) records.
            One sighting can be described in more than one passage.
            The case files below are the ones published on this site.
          </p>
        </section>

        {/* Featured case */}
        {featured && (
          <section className="py-10 md:py-14 border-b border-rule">
            <div className={
              featured.image_url || featured.video_url || featured.cover_image_url || featured.source_cover_image_url
                ? "grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12"
                : ""
            }>
              <div>
                <p className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">
                  Featured case
                  {featured.tranche_number ? ` · Release ${String(featured.tranche_number).padStart(2, "0")}` : ""}
                </p>
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
            Latest releases
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
