import type { MetadataRoute } from "next";
import { getSupabase } from "@/lib/supabase";

export const revalidate = 3600; // regenerate hourly

const BASE = "https://ufodossier.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const sb = getSupabase();

  // Fetch all incidents in batches to handle Supabase row limits
  // Paginate in batches of 200 to work around Supabase max_rows limits
  const allIncidents: { slug: string; occurred_at: string | null }[] = [];
  let from = 0;
  const batchSize = 200;
  while (true) {
    const { data } = await sb
      .from("incidents")
      .select("slug, occurred_at")
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
    lastModified: i.occurred_at ?? undefined,
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }));

  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE, changeFrequency: "daily", priority: 1.0 },
    { url: `${BASE}/map`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE}/media`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${BASE}/about`, changeFrequency: "monthly", priority: 0.4 },
  ];

  return [...staticPages, ...incidentEntries];
}
