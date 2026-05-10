import { getSupabase } from "./supabase";

export async function getMapIncidents() {
  const sb = getSupabase();
  const { data } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, location_text, country, lat, lon, resolution_status, case_id, sensor_types, summary, raw_excerpt, image_url, video_url, cover_image_url, source_cover_image_url")
    .not("lat", "is", null)
    .not("lon", "is", null);
  return data ?? [];
}

export async function getTotalIncidentCount() {
  const sb = getSupabase();
  const { count } = await sb
    .from("v_incident_full")
    .select("id", { count: "exact", head: true });
  return count ?? 0;
}

export async function getGeocodePendingCount() {
  const sb = getSupabase();
  const { count } = await sb
    .from("incidents")
    .select("id", { count: "exact", head: true })
    .not("location_text", "is", null)
    .is("lat", null);
  return count ?? 0;
}

export async function getMediaIncidents() {
  const sb = getSupabase();

  // images (exclude videos that have image_url set as thumbnail)
  const { data: images } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, location_text, image_url, case_id, resolution_status, source_filename")
    .not("image_url", "is", null)
    .is("video_url", null);

  // videos (include image_url for thumbnails)
  const { data: videos } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, location_text, video_url, image_url, case_id, resolution_status, source_filename, source_duration_seconds")
    .not("video_url", "is", null);

  // documents (PDF cover only, no real media)
  const { data: documents } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, location_text, cover_image_url, case_id, resolution_status, source_filename")
    .not("cover_image_url", "is", null)
    .is("image_url", null)
    .is("video_url", null);

  return {
    images: images ?? [],
    videos: videos ?? [],
    documents: documents ?? [],
  };
}
