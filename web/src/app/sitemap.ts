import type { MetadataRoute } from "next";
import { getSupabaseServer } from "@/lib/supabase";
import { listFragments, listReleases, listSources } from "@/lib/corpus/catalog";

export const revalidate = 3600; // regenerate hourly

const BASE = "https://www.ufodossier.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const sb = getSupabaseServer();

  // Fetch all incidents in batches to handle Supabase row limits
  const allIncidents: { slug: string; extracted_at: string | null }[] = [];
  let from = 0;
  const batchSize = 200;
  while (true) {
    const { data, error } = await sb
      .from("incidents")
      .select("slug, extracted_at")
      .not("slug", "is", null)
      .order("id")
      .range(from, from + batchSize - 1);
    if (error) throw new Error(`Sitemap incidents query failed: ${error.message}`);
    if (!data || data.length === 0) break;
    allIncidents.push(...data);
    if (data.length < batchSize) break;
    from += batchSize;
  }

  const incidentEntries: MetadataRoute.Sitemap = allIncidents.map((i) => ({
    url: `${BASE}/incident/${i.slug}`,
    lastModified: i.extracted_at && !isNaN(new Date(i.extracted_at).getTime())
      ? new Date(i.extracted_at)
      : new Date(),
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }));

  // Fetch collections
  const { data: collections, error: collectionsError } = await sb
    .from("collections")
    .select("slug, created_at")
    .order("sort_order");

  if (collectionsError) throw new Error(`Sitemap collections query failed: ${collectionsError.message}`);

  const collectionEntries: MetadataRoute.Sitemap = (collections ?? []).map((c) => ({
    url: `${BASE}/collections/${c.slug}`,
    lastModified: c.created_at && !isNaN(new Date(c.created_at).getTime())
      ? new Date(c.created_at)
      : new Date(),
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE, changeFrequency: "daily", priority: 1.0, lastModified: new Date() },
    { url: `${BASE}/incidents`, changeFrequency: "daily", priority: 0.8, lastModified: new Date() },
    { url: `${BASE}/collections`, changeFrequency: "weekly", priority: 0.8, lastModified: new Date() },
    { url: `${BASE}/releases`, changeFrequency: "weekly", priority: 0.8, lastModified: new Date() },
    { url: `${BASE}/sources`, changeFrequency: "weekly", priority: 0.8, lastModified: new Date() },
    { url: `${BASE}/map`, changeFrequency: "weekly", priority: 0.8, lastModified: new Date() },
    { url: `${BASE}/media`, changeFrequency: "weekly", priority: 0.6, lastModified: new Date() },
    { url: `${BASE}/audio`, changeFrequency: "weekly", priority: 0.5, lastModified: new Date() },
    { url: `${BASE}/ask`, changeFrequency: "monthly", priority: 0.5, lastModified: new Date() },
    { url: `${BASE}/about`, changeFrequency: "monthly", priority: 0.4, lastModified: new Date() },
  ];

  const catalogEntries: MetadataRoute.Sitemap = [
    ...listReleases().map((release) => ({
      url: `${BASE}/releases/${String(release.release).padStart(2, "0")}`,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    })),
    ...listSources().map((source) => ({
      url: `${BASE}/source/${encodeURIComponent(source.slug)}`,
      changeFrequency: "monthly" as const,
      priority: 0.4,
    })),
  ];

  const localIncidentEntries: MetadataRoute.Sitemap = listFragments().map((fragment) => ({
    url: `${BASE}/incident/${encodeURIComponent(fragment.slug)}`,
    changeFrequency: "monthly",
    priority: 0.7,
  }));
  const entries = [...staticPages, ...collectionEntries, ...catalogEntries, ...localIncidentEntries, ...incidentEntries];
  return [...new Map(entries.map((entry) => [entry.url, entry])).values()];
}
