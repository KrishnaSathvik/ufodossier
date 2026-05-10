import { TopBar } from "@/components/TopBar";
import { Footer } from "@/components/Footer";
import { IncidentList } from "@/components/IncidentList";
import { getSupabaseServer } from "@/lib/supabase";
import type { Metadata } from "next";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "All Incidents",
  description: "Complete list of UAP incidents extracted from declassified U.S. government documents.",
  alternates: { canonical: "/incidents" },
};

async function getAllIncidents() {
  const sb = getSupabaseServer();
  const all: any[] = [];
  let from = 0;
  const batchSize = 200;
  while (true) {
    const { data } = await sb
      .from("v_incident_full")
      .select("id, slug, title, occurred_at, occurred_at_text, branch, source_agency, location_text, country, region, resolution_status, sensor_types, image_url, video_url, summary, raw_excerpt, case_id")
      .order("occurred_at", { ascending: false, nullsFirst: false })
      .range(from, from + batchSize - 1);
    if (!data || data.length === 0) break;
    all.push(...data);
    if (data.length < batchSize) break;
    from += batchSize;
  }
  return all;
}

export default async function IncidentsPage() {
  const incidents = await getAllIncidents();

  return (
    <>
      <TopBar active="archive" />
      <main className="max-w-content mx-auto px-4 md:px-6 py-10 md:py-14">
        <h1 className="font-serif text-2xl md:text-3xl font-medium mb-2">
          All incidents
        </h1>
        <p className="text-sm text-ink-faint mb-8">
          {incidents.length.toLocaleString()} cases from declassified U.S. government files
        </p>
        <IncidentList incidents={incidents} showSearch paginated />
      </main>
      <Footer />
    </>
  );
}
