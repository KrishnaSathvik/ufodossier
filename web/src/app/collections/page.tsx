import { TopBar } from "@/components/TopBar";
import { Footer } from "@/components/Footer";
import { getSupabaseServer } from "@/lib/supabase";
import Link from "next/link";
import type { Metadata } from "next";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Collections — UFO Dossier",
  description: "Curated collections of declassified UAP incidents, organized by agency, era, and theme.",
  alternates: { canonical: "/collections" },
};

async function getCollections() {
  const sb = getSupabaseServer();
  const { data: collections } = await sb
    .from("collections")
    .select("id, slug, title, standfirst, sort_order")
    .order("sort_order");

  if (!collections || collections.length === 0) return [];

  // Get incident counts per collection
  const { data: counts } = await sb
    .from("collection_incidents")
    .select("collection_id");

  const countMap = new Map<string, number>();
  for (const row of counts ?? []) {
    countMap.set(row.collection_id, (countMap.get(row.collection_id) ?? 0) + 1);
  }

  return collections.map((c) => ({
    ...c,
    incident_count: countMap.get(c.id) ?? 0,
  }));
}

export default async function CollectionsPage() {
  const collections = await getCollections();

  return (
    <>
      <TopBar active="collections" />

      <main className="max-w-content mx-auto px-4 md:px-6">
        <section className="pt-16 md:pt-24 pb-10 md:pb-14">
          <h1 className="font-serif text-3xl md:text-5xl font-medium leading-tight mb-4">
            Collections
          </h1>
          <p className="font-serif italic text-lg text-ink-dim max-w-prose">
            Curated groupings of declassified incidents, organized by agency, era, and sensor type.
          </p>
        </section>

        {collections.length === 0 ? (
          <p className="py-12 text-center text-ink-faint">
            No collections yet. Pipeline pending.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-14">
            {collections.map((c) => (
              <Link
                key={c.slug}
                href={`/collections/${c.slug}`}
                className="block border border-rule p-6 hover:border-ink-faint transition-colors group"
              >
                <h2 className="font-serif text-[22px] font-medium leading-snug mb-2 group-hover:text-accent transition-colors">
                  {c.title}
                </h2>
                <p className="font-serif italic text-sm text-ink-dim line-clamp-2 mb-3">
                  {c.standfirst}
                </p>
                <span className="text-xs text-ink-faint font-sans">
                  {c.incident_count} incidents &rarr;
                </span>
              </Link>
            ))}
          </div>
        )}
      </main>

      <Footer />
    </>
  );
}
