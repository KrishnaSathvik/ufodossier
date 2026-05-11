import { ImageResponse } from "next/og";
import { getSupabaseServer } from "@/lib/supabase";

export const runtime = "edge";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };
export const revalidate = 604800; // 1 week

// ---------------------------------------------------------------------------
// Font loading — each fetch gets its own 5-second timeout
// ---------------------------------------------------------------------------
async function loadFont(
  family: string,
  weight: number,
): Promise<ArrayBuffer | null> {
  try {
    const ctrl1 = new AbortController();
    const t1 = setTimeout(() => ctrl1.abort(), 5000);
    const cssRes = await fetch(
      `https://fonts.googleapis.com/css2?family=${family.replace(/ /g, "+")}:wght@${weight}&display=swap`,
      { signal: ctrl1.signal, headers: { "User-Agent": "Mozilla/5.0" } },
    );
    const css = await cssRes.text();
    clearTimeout(t1);

    const url = css.match(/src:\s*url\(([^)]+\.woff2)\)/)?.[1];
    if (!url) return null;

    const ctrl2 = new AbortController();
    const t2 = setTimeout(() => ctrl2.abort(), 5000);
    const buf = await fetch(url, { signal: ctrl2.signal }).then((r) =>
      r.arrayBuffer(),
    );
    clearTimeout(t2);
    return buf;
  } catch (e) {
    console.error(`Font load failed (${family}):`, e);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Image fetching — 8-second timeout, returns data-URL or null
// ---------------------------------------------------------------------------
async function fetchImageData(url: string): Promise<string | null> {
  try {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(id);
    if (!res.ok) return null;
    const buf = await res.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const mime = res.headers.get("content-type") || "image/jpeg";
    return `data:${mime};base64,${btoa(binary)}`;
  } catch (e) {
    console.error("Image fetch failed:", e);
    return null;
  }
}

// ---------------------------------------------------------------------------
// OG image handler
// ---------------------------------------------------------------------------
export default async function OGImage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  // Load Newsreader + JetBrains Mono in parallel
  const [newsreaderBuf, jetBrainsBuf] = await Promise.all([
    loadFont("Newsreader", 500),
    loadFont("JetBrains Mono", 400),
  ]);

  const fonts: { name: string; data: ArrayBuffer; style: "normal" }[] = [];
  if (newsreaderBuf)
    fonts.push({ name: "Newsreader", data: newsreaderBuf, style: "normal" });
  if (jetBrainsBuf)
    fonts.push({
      name: "JetBrains Mono",
      data: jetBrainsBuf,
      style: "normal",
    });

  const serifFont = newsreaderBuf ? "Newsreader" : "Georgia, serif";
  const monoFont = jetBrainsBuf ? "JetBrains Mono" : "Courier, monospace";
  const fontOpts = fonts.length > 0 ? fonts : undefined;

  // ---- Query incident ----
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
            backgroundColor: "#faf8f3",
            fontFamily: serifFont,
            fontSize: "32px",
            color: "#1a1a1a",
          }}
        >
          UFO Dossier
        </div>
      ),
      { ...size, fonts: fontOpts },
    );
  }

  const { data: incident } = await sb
    .from("v_incident_full")
    .select(
      "title, case_id, occurred_at, occurred_at_text, location_text, branch, source_agency, image_url, video_url, cover_image_url, source_cover_image_url, raw_excerpt, summary",
    )
    .eq("id", slugRow.id)
    .single();

  if (!incident) {
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#faf8f3",
            fontFamily: serifFont,
            fontSize: "32px",
            color: "#1a1a1a",
          }}
        >
          UFO Dossier
        </div>
      ),
      { ...size, fonts: fontOpts },
    );
  }

  // ---- Prepare text ----
  const caseId = incident.case_id ?? "";
  const date = incident.occurred_at ?? incident.occurred_at_text ?? "Undated";
  const branch = incident.branch ?? incident.source_agency ?? "";
  const location = incident.location_text
    ? incident.location_text.length > 35
      ? incident.location_text.slice(0, 32) + "..."
      : incident.location_text
    : "";
  const metaLine = [String(date), location, branch]
    .filter(Boolean)
    .join("  \u00b7  ");

  // ---- Pick lead visual (priority chain) ----
  const visualUrl =
    incident.image_url ||
    incident.cover_image_url ||
    incident.source_cover_image_url ||
    null;

  let imageData: string | null = null;
  if (visualUrl) {
    imageData = await fetchImageData(visualUrl);
  }

  // ===========================================================================
  // VARIANT 1 — Media layout (real image / document cover)
  // ===========================================================================
  if (imageData) {
    const title =
      incident.title.length > 100
        ? incident.title.slice(0, 97) + "..."
        : incident.title;

    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            position: "relative",
          }}
        >
          {/* Full-bleed image */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageData}
            alt=""
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />

          {/* Bottom gradient overlay (~35% of 630 = 220px) */}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: "220px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "flex-end",
              padding: "0 60px 40px 60px",
              background:
                "linear-gradient(to top, rgba(0,0,0,0.85) 0%, transparent 100%)",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column" }}>
              {caseId && (
                <span
                  style={{
                    fontFamily: monoFont,
                    fontSize: "18px",
                    color: "rgba(255,255,255,0.7)",
                    letterSpacing: "0.1em",
                    marginBottom: "8px",
                  }}
                >
                  {caseId}
                </span>
              )}
              <span
                style={{
                  fontFamily: serifFont,
                  fontSize: "42px",
                  color: "#ffffff",
                  lineHeight: 1.15,
                  marginBottom: "10px",
                }}
              >
                {title}
              </span>
              <span
                style={{
                  fontFamily: monoFont,
                  fontSize: "16px",
                  color: "rgba(255,255,255,0.6)",
                }}
              >
                {metaLine}
              </span>
            </div>
          </div>

          {/* Top-right wordmark */}
          <div
            style={{
              position: "absolute",
              top: "30px",
              right: "30px",
              display: "flex",
            }}
          >
            <span
              style={{
                fontFamily: monoFont,
                fontSize: "14px",
                letterSpacing: "0.15em",
                color: "rgba(255,255,255,0.85)",
                textShadow: "0 1px 4px rgba(0,0,0,0.6)",
              }}
            >
              UFO DOSSIER
            </span>
          </div>
        </div>
      ),
      { ...size, fonts: fontOpts },
    );
  }

  // ===========================================================================
  // VARIANT 2 — Typographic fallback (no media available)
  // ===========================================================================
  const title =
    incident.title.length > 100
      ? incident.title.slice(0, 97) + "..."
      : incident.title;

  const excerptText = incident.raw_excerpt || incident.summary || "";
  const excerpt =
    excerptText.length > 280
      ? excerptText.slice(0, 277) + "..."
      : excerptText;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#faf8f3",
          padding: "30px",
          position: "relative",
        }}
      >
        {/* Hairline border inset 30px */}
        <div
          style={{
            position: "absolute",
            top: "30px",
            left: "30px",
            right: "30px",
            bottom: "30px",
            border: "1px solid #d8d4c8",
            display: "flex",
          }}
        />

        {/* Top-left wordmark */}
        <div style={{ display: "flex", padding: "20px 30px 0" }}>
          <span
            style={{
              fontFamily: monoFont,
              fontSize: "16px",
              letterSpacing: "0.15em",
              color: "#5a584f",
            }}
          >
            UFO DOSSIER
          </span>
        </div>

        {/* Center content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            flex: 1,
            padding: "0 80px",
          }}
        >
          {caseId && (
            <span
              style={{
                fontFamily: monoFont,
                fontSize: "18px",
                color: "#8a8780",
                letterSpacing: "0.1em",
                marginBottom: "12px",
              }}
            >
              {caseId}
            </span>
          )}
          <span
            style={{
              fontFamily: serifFont,
              fontSize: "42px",
              color: "#1a1a1a",
              lineHeight: 1.15,
              marginBottom: "16px",
            }}
          >
            {title}
          </span>
          <span
            style={{ fontFamily: monoFont, fontSize: "14px", color: "#5a584f", marginBottom: "20px" }}
          >
            {metaLine}
          </span>

          {/* Verbatim excerpt block */}
          {excerpt && (
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span
                style={{
                  fontFamily: monoFont,
                  fontSize: "10px",
                  letterSpacing: "0.15em",
                  color: "#8a8780",
                  marginBottom: "8px",
                }}
              >
                VERBATIM FROM SOURCE
              </span>
              <div
                style={{
                  display: "flex",
                  borderLeft: "3px solid #ff9933",
                  paddingLeft: "16px",
                }}
              >
                <span
                  style={{
                    fontFamily: serifFont,
                    fontSize: "18px",
                    fontStyle: "italic",
                    color: "#3a3935",
                    lineHeight: 1.45,
                  }}
                >
                  {excerpt}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Bottom label */}
        <div style={{ display: "flex", padding: "0 30px 20px" }}>
          <span
            style={{
              fontFamily: monoFont,
              fontSize: "13px",
              letterSpacing: "0.15em",
              color: "#8a8780",
            }}
          >
            FROM THE DECLASSIFIED PURSUE RELEASE
          </span>
        </div>
      </div>
    ),
    { ...size, fonts: fontOpts },
  );
}
