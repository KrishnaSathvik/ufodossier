import { IncidentRow } from "@/components/IncidentRow";
import { JsonLd } from "@/components/JsonLd";
import { RedactedExcerpt } from "@/components/RedactedExcerpt";
import { getSupabaseServer } from "@/lib/supabase";
import { getCorpusStats, listReleases } from "@/lib/corpus/catalog";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";

export const revalidate = 300; // 5 min

export const metadata: Metadata = {
  alternates: { canonical: "/" },
  description: "A searchable, source-grounded archive of publicly released U.S. government UAP records.",
  openGraph: {
    title: "Archive — UFO Dossier",
    description: "Verified passages from publicly released U.S. government UAP records.",
    images: [{ url: "/og/archive.png", width: 1200, height: 630, alt: "Archive — UFO Dossier" }],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og/archive.png"],
  },
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

  const latestIncidents = incidents.filter((incident) => incident.id !== featured?.id).slice(0, 10);

  const releases = listReleases();
  const latestRelease = releases.at(-1);
  const latestReleaseHref = latestRelease ? `/releases/${String(latestRelease.release).padStart(2, "0")}` : "/releases";

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


      <main className="site-shell homepage">
        {/* Keep editorial copy stacked; the desktop index supplies context. */}
        <section className="archive-intro pt-14 md:pt-20 pb-10 md:pb-12 border-b border-rule">
          <div className="archive-intro-copy">
            <h1 className="font-serif text-[clamp(28px,3.6vw,48px)] font-medium leading-[1.15] tracking-tight mb-5 max-w-[38rem]">
              A searchable, source-grounded archive of publicly released U.S. government UAP&nbsp;records.
            </h1>
            <p className="text-base md:text-lg text-ink-dim max-w-prose leading-relaxed">
              {corpus.fragments.toLocaleString()} checked passages and {corpus.canonicalEvents.toLocaleString()} sightings,
              drawn from {corpus.officialRecords.toLocaleString()} official files across {corpus.releases} releases from PURSUE,
              the Pentagon program that published these unidentified anomalous phenomena (UAP) records.
              One sighting can be described in more than one passage.
              The case files below are the ones published on this site.
            </p>
          </div>
          <aside aria-label="Archive index" className="archive-index hidden lg:block">
            <p className="font-mono text-xs uppercase tracking-tracked text-ink-dim mb-4">Archive index</p>
            <dl>
              {[
                ["Official files", corpus.officialRecords],
                ["Checked passages", corpus.fragments],
                ["Sightings", corpus.canonicalEvents],
                ["Releases", corpus.releases],
              ].map(([label, count]) => (
                <div key={label} className="flex items-baseline justify-between gap-6 border-t border-rule py-3">
                  <dt className="font-mono text-xs text-ink-dim">{label}</dt>
                  <dd className="font-serif text-3xl tabular-nums">{count.toLocaleString()}</dd>
                </div>
              ))}
            </dl>
            <Link href={latestReleaseHref} className="block border-t border-rule pt-4 font-mono text-xs text-accent hover:text-accent-dim transition-colors">
              {latestRelease ? `Latest: ${latestRelease.label}` : "Browse releases"} &rarr;
            </Link>
          </aside>
        </section>

        {/* Featured case */}
        {featured && (
          <section className="home-feature py-10 md:py-12 border-b border-rule">
            <div className="featured-file">
              <div className="featured-rail flex items-baseline justify-between gap-4">
                <p className="featured-label text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">
                  Featured case
                  {featured.tranche_number ? ` · Release ${String(featured.tranche_number).padStart(2, "0")}` : ""}
                </p>
                {featured.resolution_status && (
                  <span className={`hidden lg:inline font-mono text-xs uppercase ${featured.resolution_status === "unresolved" ? "text-critical" : "text-ink-dim"}`}>
                    {featured.resolution_status.replaceAll("_", " ")}
                  </span>
                )}
              </div>
              <div className={
                featured.image_url || featured.video_url || featured.cover_image_url || featured.source_cover_image_url
                  ? "content-region grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-10"
                  : "featured-text-layout"
              }>
                <div className="featured-copy">
                  <h2 className="featured-title font-serif text-2xl md:text-[1.75rem] font-medium leading-snug mb-3">
                    {featured.title}
                  </h2>
                  <p className="featured-summary text-ink-dim leading-relaxed mb-4 text-[15px] lg:text-base">
                    {featured.summary}
                  </p>
                  {featured.raw_excerpt && (
                    <blockquote className="featured-excerpt border-l-2 border-accent pl-4 py-1 my-5 text-sm lg:text-base lg:leading-relaxed text-ink-dim italic">
                      &ldquo;<RedactedExcerpt text={featured.raw_excerpt} />&rdquo;
                    </blockquote>
                  )}
                  <div className="featured-meta flex items-center gap-4 text-sm text-ink-faint">
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
            </div>
          </section>
        )}

        {/* Incident list */}
        <section className="py-10 md:py-14">
          <h2 className="font-serif text-xl font-medium mb-6">
            Latest releases
          </h2>

          <div className="incident-row hidden lg:grid border-y border-rule py-3 text-[10px] lg:text-xs lg:text-ink-dim font-mono uppercase tracking-tracked text-ink-faint" aria-hidden="true">
            <span>Date</span>
            <span>Case</span>
            <span className="incident-metadata grid">
              <span>Release</span><span>Agency</span><span>Status</span>
            </span>
          </div>
          <div className="home-latest">
            {latestIncidents.length === 0 ? (
              <p className="py-12 text-center text-ink-faint">No incidents are listed yet.</p>
            ) : latestIncidents.map((incident) => (
              <IncidentRow key={incident.id} incident={incident} />
            ))}
          </div>

          <div className="pt-6 flex flex-wrap items-center justify-between gap-4">
            <Link href="/incidents" className="inline-block px-5 py-2 border border-rule text-sm font-medium hover:border-ink-faint transition-colors">
              View all {stats.incident_count.toLocaleString()} case files &rarr;
            </Link>
            <Link href={latestReleaseHref} className="text-sm text-accent hover:text-accent-dim transition-colors">
              {latestRelease ? `Browse ${latestRelease.label}` : "Browse releases"} &rarr;
            </Link>
          </div>
        </section>
      </main>

    </>
  );
}
