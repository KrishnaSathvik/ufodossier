import { getSupabaseServer } from "./supabase";

export async function getMapIncidents() {
  const sb = getSupabaseServer();
  const { data } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, location_text, country, lat, lon, resolution_status, case_id, sensor_types, summary, raw_excerpt, image_url, video_url, cover_image_url, source_cover_image_url")
    .not("lat", "is", null)
    .not("lon", "is", null);
  return data ?? [];
}

export async function getTotalIncidentCount() {
  const sb = getSupabaseServer();
  const { count } = await sb
    .from("v_incident_full")
    .select("id", { count: "exact", head: true });
  return count ?? 0;
}

export async function getGeocodePendingCount() {
  const sb = getSupabaseServer();
  const { count } = await sb
    .from("incidents")
    .select("id", { count: "exact", head: true })
    .not("location_text", "is", null)
    .is("lat", null);
  return count ?? 0;
}

export async function getMediaIncidents() {
  const sb = getSupabaseServer();

  // Slideshow images from source_files (deduplicated by design — one row per image)
  const { data: slideshowFiles } = await sb
    .from("source_files")
    .select("id, filename, storage_path, agency")
    .ilike("storage_path", "source-files/slideshow/%")
    .order("filename");

  // Build public URLs and find one linked incident per image
  const baseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const slideshowImages: any[] = [];

  if (slideshowFiles) {
    // Get all incidents with image_url set (for matching)
    const { data: imgIncidents } = await sb
      .from("v_incident_full")
      .select("id, slug, title, occurred_at, occurred_at_text, branch, location_text, image_url, case_id, resolution_status, source_filename")
      .not("image_url", "is", null)
      .is("video_url", null);

    const incidentsByUrl = new Map<string, any>();
    for (const inc of imgIncidents ?? []) {
      if (inc.image_url && !incidentsByUrl.has(inc.image_url)) {
        incidentsByUrl.set(inc.image_url, inc);
      }
    }

    for (const sf of slideshowFiles) {
      if (!sf.storage_path) continue;
      const publicUrl = `${baseUrl}/storage/v1/object/public/${sf.storage_path}`;
      const linked = incidentsByUrl.get(publicUrl) || incidentsByUrl.get(sf.filename);

      // Also check war.gov URL pattern for matching
      const warGovUrl = `https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/${sf.filename}`;
      const linkedViaWar = !linked ? incidentsByUrl.get(warGovUrl) : null;
      const incident = linked || linkedViaWar;

      slideshowImages.push({
        id: sf.id,
        slug: incident?.slug,
        title: incident?.title || sf.filename.replace(/\.jpg$/i, "").replace(/[-_]/g, " "),
        occurred_at: incident?.occurred_at,
        occurred_at_text: incident?.occurred_at_text,
        branch: incident?.branch || sf.agency,
        location_text: incident?.location_text,
        image_url: publicUrl,
        case_id: incident?.case_id,
        resolution_status: incident?.resolution_status,
        source_filename: sf.filename,
      });
    }
  }

  return {
    images: slideshowImages,
  };
}

export async function getVideosForMedia() {
  const sb = getSupabaseServer();

  const { data, error } = await sb
    .from("source_files")
    .select("id, filename, url, agency, transcript, file_type, cover_image_url")
    .eq("file_type", "mp4")
    .order("filename");

  if (error) throw error;

  return (data ?? []).map((d) => {
    // Extract DVIDS ID from canonical URL: https://www.dvidshub.net/video/{ID}
    const dvidMatch = d.url.match(/dvidshub\.net\/video\/(\d+)/);
    const dvidsId = dvidMatch ? dvidMatch[1] : null;
    const embedUrl = dvidsId
      ? `https://www.dvidshub.net/video/embed/${dvidsId}`
      : d.url;

    // Extract a short description from the transcript (first 150 chars)
    let blurb: string | null = null;
    if (d.transcript) {
      const first = d.transcript.split("\n")[0].trim();
      blurb =
        first.length > 150 ? first.slice(0, 147) + "..." : first;
    }

    return {
      id: d.id,
      filename: d.filename,
      url: d.url,
      embed_url: embedUrl,
      thumbnail_url: d.cover_image_url ?? null,
      agency: d.agency,
      blurb,
    };
  });
}

export async function getDocumentsForMedia() {
  const sb = getSupabaseServer();

  const { data, error } = await sb
    .from("source_files")
    .select("id, filename, url, cover_image_url, page_count, file_type, agency")
    .eq("file_type", "pdf")
    .not("cover_image_url", "is", null)
    .order("created_at", { ascending: false });

  if (error) throw error;

  // For each PDF, find an associated incident slug if one exists
  const ids = (data ?? []).map((d) => d.id);
  const { data: incidents } = await sb
    .from("incidents")
    .select("source_file_id, slug")
    .in("source_file_id", ids);

  const slugBySourceFileId: Record<string, string> = {};
  for (const inc of incidents ?? []) {
    if (inc.source_file_id && inc.slug && !slugBySourceFileId[inc.source_file_id]) {
      slugBySourceFileId[inc.source_file_id] = inc.slug;
    }
  }

  return (data ?? []).map((d) => ({
    ...d,
    incident_slug: slugBySourceFileId[d.id] ?? null,
  }));
}
