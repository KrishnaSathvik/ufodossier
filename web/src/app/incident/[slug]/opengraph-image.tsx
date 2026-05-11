import { ImageResponse } from "next/og";
import { getSupabaseServer } from "@/lib/supabase";

export const runtime = "edge";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };
export const revalidate = 604800; // 1 week

export default async function OGImage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const sb = getSupabaseServer();
  const { data: slugRow } = await sb
    .from("incidents")
    .select("id")
    .eq("slug", slug)
    .single();

  if (!slugRow) {
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#0a0a0a",
            color: "#e8e6e0",
            fontSize: "32px",
            fontFamily: "Georgia, serif",
          }}
        >
          UFO Dossier
        </div>
      ),
      { ...size },
    );
  }

  const { data: incident } = await sb
    .from("v_incident_full")
    .select("image_url, cover_image_url, source_cover_image_url")
    .eq("id", slugRow.id)
    .single();

  const visualUrl =
    incident?.image_url ||
    incident?.cover_image_url ||
    incident?.source_cover_image_url ||
    null;

  if (visualUrl) {
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            backgroundColor: "#0a0a0a",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt=""
            src={visualUrl}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </div>
      ),
      { ...size },
    );
  }

  // No image — dark fallback
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0a0a0a",
          color: "#e8e6e0",
          fontSize: "32px",
          fontFamily: "Georgia, serif",
        }}
      >
        UFO Dossier
      </div>
    ),
    { ...size },
  );
}
