import { TopBar } from "@/components/TopBar";
import { Footer } from "@/components/Footer";
import { JsonLd } from "@/components/JsonLd";
import { IncidentList } from "@/components/IncidentList";
import { getSupabaseServer } from "@/lib/supabase";
import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";

export const revalidate = 600;

async function getCollection(slug: string) {
  const sb = getSupabaseServer();
  const { data } = await sb
    .from("collections")
    .select("*")
    .eq("slug", slug)
    .single();
  return data;
}

async function getCollectionIncidents(collectionId: string) {
  const sb = getSupabaseServer();

  // Get incident IDs ordered by collection sort_order
  const { data: junctions } = await sb
    .from("collection_incidents")
    .select("incident_id")
    .eq("collection_id", collectionId)
    .order("sort_order");

  if (!junctions || junctions.length === 0) return [];

  const ids = junctions.map((j) => j.incident_id);

  const { data: incidents } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, source_agency, location_text, country, region, resolution_status, sensor_types, image_url, video_url, summary, raw_excerpt, case_id")
    .in("id", ids);

  if (!incidents) return [];

  // Preserve collection sort order
  const orderMap = new Map(ids.map((id, i) => [id, i]));
  return incidents.sort((a, b) => (orderMap.get(a.id) ?? 0) - (orderMap.get(b.id) ?? 0));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const collection = await getCollection(slug);
  if (!collection) return {};

  return {
    title: `${collection.title} — UFO Dossier`,
    description: collection.standfirst,
    alternates: { canonical: `/collections/${slug}` },
    openGraph: {
      title: collection.title,
      description: collection.standfirst,
      type: "website",
      url: `/collections/${slug}`,
    },
  };
}

export default async function CollectionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const collection = await getCollection(slug);
  if (!collection) notFound();

  const incidents = await getCollectionIncidents(collection.id);

  const introParas = collection.intro_md
    ? collection.intro_md.split("\n\n").filter(Boolean)
    : [];

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: collection.title,
        description: collection.standfirst,
        url: `https://www.ufodossier.com/collections/${slug}`,
        isPartOf: {
          "@type": "Dataset",
          name: "UFO Dossier — Declassified UAP Archive",
          description: "Searchable archive of every UAP incident in the U.S. government's declassified PURSUE files, with substring-validated verbatim excerpts from original source documents.",
          url: "https://www.ufodossier.com",
        },
      }} />
      <TopBar active="collections" />

      <main className="max-w-content mx-auto px-4 md:px-6">
        {/* Breadcrumb */}
        <nav className="pt-8 text-xs text-ink-faint font-sans">
          <Link href="/" className="hover:text-ink transition-colors">Archive</Link>
          <span className="mx-1.5">/</span>
          <Link href="/collections" className="hover:text-ink transition-colors">Collections</Link>
          <span className="mx-1.5">/</span>
          <span className="text-ink-dim">{collection.title}</span>
        </nav>

        <section className="pt-8 md:pt-12 pb-8">
          <h1 className="font-serif text-3xl md:text-[52px] font-medium leading-tight mb-4">
            {collection.title}
          </h1>
          <p className="font-serif italic text-lg md:text-xl text-ink-dim max-w-[600px]">
            {collection.standfirst}
          </p>

          {introParas.length > 0 && (
            <div className="mt-6 max-w-prose space-y-4">
              {introParas.map((para: string, i: number) => (
                <p key={i} className="text-ink-dim leading-relaxed">
                  {para}
                </p>
              ))}
            </div>
          )}
        </section>

        <section className="pb-14">
          <IncidentList incidents={incidents} />
        </section>
      </main>

      <Footer />
    </>
  );
}
