import type { MetadataRoute } from "next";
import { getSupabaseServer } from "@/lib/supabase";

export const revalidate = 3600; // regenerate hourly

const BASE = "https://www.ufodossier.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const sb = getSupabaseServer();

  // Fetch all incidents in batches to handle Supabase row limits
  const allIncidents: { slug: string; extracted_at: string | null }[] = [];
  let from = 0;
  const batchSize = 200;
  while (true) {
    const { data } = await sb
      .from("incidents")
      .select("slug, extracted_at")
      .not("slug", "is", null)
      .order("id")
      .range(from, from + batchSize - 1);
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
  const { data: collections } = await sb
    .from("collections")
    .select("slug, created_at")
    .order("sort_order");

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
    { url: `${BASE}/collections`, changeFrequency: "weekly", priority: 0.8, lastModified: new Date() },
    { url: `${BASE}/map`, changeFrequency: "weekly", priority: 0.8, lastModified: new Date() },
    { url: `${BASE}/media`, changeFrequency: "weekly", priority: 0.6, lastModified: new Date() },
    { url: `${BASE}/about`, changeFrequency: "monthly", priority: 0.4, lastModified: new Date() },
  ];

  return [...staticPages, ...collectionEntries, ...incidentEntries];
}
