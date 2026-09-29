import { getSupabaseServer } from "./supabase";

export async function getMapIncidents() {
  const sb = getSupabaseServer();
  const { data } = await sb
    .from("v_incident_full")
    .select("id, slug, title, occurred_at, occurred_at_text, branch, location_text, country, lat, lon, resolution_status, case_id, sensor_types, summary, raw_excerpt, image_url, video_url, cover_image_url, source_cover_image_url")
    .eq("flagged", false)
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
    .eq("flagged", false)
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

  const { data: imageRecords } = await sb
    .from("source_records")
    .select("id, external_id, title, agency, release_number, thumbnail_url, original_url")
    .eq("source_type", "image")
    .eq("status", "active")
    .not("thumbnail_url", "is", null)
    .order("release_number", { ascending: false });

  const registryImages = (imageRecords ?? []).map((record) => ({
    id: record.id,
    slug: null,
    href: record.external_id ? `/source/${record.external_id}` : record.original_url,
    title: record.title || record.external_id,
    occurred_at: null,
    branch: record.agency,
    image_url: record.thumbnail_url,
    release: record.release_number,
    case_id: record.external_id,
    source_filename: record.external_id,
  }));

  return {
    images: [...registryImages, ...slideshowImages],
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

  const fromFiles = (data ?? []).map((d) => {
    const dvidMatch = d.url.match(/dvidshub\.net\/video\/(\d+)/);
    const dvidsId = dvidMatch ? dvidMatch[1] : null;
    const embedUrl = dvidsId
      ? `https://www.dvidshub.net/video/embed/${dvidsId}`
      : d.url;

    let blurb: string | null = null;
    if (d.transcript) {
      const first = d.transcript.split("\n")[0].trim();
      blurb = first.length > 150 ? first.slice(0, 147) + "..." : first;
    }

    return {
      id: d.id,
      filename: d.filename,
      url: d.url,
      embed_url: embedUrl,
      thumbnail_url: d.cover_image_url ?? null,
      agency: d.agency,
      blurb,
      release: null as number | null,
      dvidsId,
    };
  });

  const seen = new Set(fromFiles.map((video) => video.dvidsId).filter((id): id is string => Boolean(id)));
  const { data: videoRecords } = await sb
    .from("source_records")
    .select("id, external_id, title, agency, release_number, description, metadata")
    .eq("source_type", "video")
    .eq("status", "active");

  const releaseByDvids = new Map<string, number>();
  const extras = [];
  for (const record of videoRecords ?? []) {
    const metadata = (record.metadata ?? {}) as { dvids_video_id?: string; video_title?: string };
    const dvidsId = metadata.dvids_video_id ? String(metadata.dvids_video_id) : null;
    if (!dvidsId) continue;
    if (record.release_number) releaseByDvids.set(dvidsId, record.release_number);
    if (seen.has(dvidsId)) continue;
    seen.add(dvidsId);
    const blurb = record.description
      ? record.description.length > 150
        ? record.description.slice(0, 147) + "..."
        : record.description
      : null;
    extras.push({
      id: record.id,
      filename: metadata.video_title || record.title || record.external_id || dvidsId,
      url: `https://www.dvidshub.net/video/${dvidsId}`,
      embed_url: `https://www.dvidshub.net/video/embed/${dvidsId}`,
      thumbnail_url: null,
      agency: record.agency,
      blurb,
      release: record.release_number as number | null,
      dvidsId,
    });
  }

  return [...fromFiles, ...extras]
    .map((video) => ({
      ...video,
      release: video.release ?? (video.dvidsId ? releaseByDvids.get(video.dvidsId) ?? null : null),
    }))
    .sort((a, b) => (b.release ?? 0) - (a.release ?? 0) || a.filename.localeCompare(b.filename))
    .map(({ dvidsId: _dvidsId, ...video }) => video);
}

export async function getDocumentsForMedia() {
  const sb = getSupabaseServer();

  const [{ data, error }, { data: pdfRecords }] = await Promise.all([
    sb
      .from("source_files")
      .select("id, filename, url, cover_image_url, page_count, file_type, agency, releases(tranche_number)")
      .eq("file_type", "pdf"),
    sb
      .from("source_records")
      .select("external_id, thumbnail_url, original_url, release_number")
      .eq("source_type", "pdf")
      .eq("status", "active")
      .not("thumbnail_url", "is", null),
  ]);

  if (error) throw error;

  const thumbByExternalId = new Map<string, { thumbnail_url: string | null; original_url: string | null; release_number: number | null }>();
  for (const record of pdfRecords ?? []) {
    if (!record.external_id || !record.thumbnail_url) continue;
    thumbByExternalId.set(record.external_id.toUpperCase(), record);
  }

  const withCovers = (data ?? []).flatMap((file) => {
    const matched = (file.filename ?? "").match(/^([A-Z0-9]+-UAP-[A-Z0-9]+)/i);
    const externalId = matched?.[1]?.toUpperCase() ?? null;
    const record = externalId ? thumbByExternalId.get(externalId) : undefined;
    const cover = file.cover_image_url || record?.thumbnail_url || null;
    if (!cover) return [];
    const releaseJoin = file.releases as { tranche_number: number } | { tranche_number: number }[] | null;
    const joinedRelease = Array.isArray(releaseJoin) ? releaseJoin[0]?.tranche_number : releaseJoin?.tranche_number;
    return [{
      ...file,
      url: file.url || record?.original_url || "",
      cover_image_url: cover,
      release: joinedRelease ?? record?.release_number ?? null,
    }];
  }).sort((a, b) => (b.release ?? 0) - (a.release ?? 0) || a.filename.localeCompare(b.filename));

  const ids = withCovers.map((d) => d.id);
  const { data: incidents } = ids.length
    ? await sb.from("incidents").select("source_file_id, slug").in("source_file_id", ids)
    : { data: [] };

  const slugBySourceFileId: Record<string, string> = {};
  for (const inc of incidents ?? []) {
    if (inc.source_file_id && inc.slug && !slugBySourceFileId[inc.source_file_id]) {
      slugBySourceFileId[inc.source_file_id] = inc.slug;
    }
  }

  return withCovers.map((d) => ({
    ...d,
    incident_slug: slugBySourceFileId[d.id] ?? null,
  }));
}
