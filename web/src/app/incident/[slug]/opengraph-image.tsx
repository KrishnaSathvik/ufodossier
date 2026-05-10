import { ImageResponse } from "next/og";
import { getSupabaseServer } from "@/lib/supabase";

export const runtime = "edge";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };

// Font loading with defensive fallbacks
let specialEliteFont: ArrayBuffer | null = null;
let jetBrainsFont: ArrayBuffer | null = null;
let fontsLoaded = false;

async function loadFonts() {
  if (fontsLoaded) return;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    const seCssRes = await fetch(
      "https://fonts.googleapis.com/css2?family=Special+Elite&display=swap",
      { signal: controller.signal, headers: { "User-Agent": "Mozilla/5.0" } }
    );
    const seCss = await seCssRes.text();
    const seUrl = seCss.match(/src:\s*url\(([^)]+\.woff2)\)/)?.[1];
    if (seUrl) {
      const seRes = await fetch(seUrl, { signal: controller.signal });
      specialEliteFont = await seRes.arrayBuffer();
    }
  } catch (e) {
    console.error("Failed to load Special Elite font:", e);
  }

  try {
    const jbCssRes = await fetch(
      "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400&display=swap",
      { signal: controller.signal, headers: { "User-Agent": "Mozilla/5.0" } }
    );
    const jbCss = await jbCssRes.text();
    const jbUrl = jbCss.match(/src:\s*url\(([^)]+\.woff2)\)/)?.[1];
    if (jbUrl) {
      const jbRes = await fetch(jbUrl, { signal: controller.signal });
      jetBrainsFont = await jbRes.arrayBuffer();
    }
  } catch (e) {
    console.error("Failed to load JetBrains Mono font:", e);
  }

  clearTimeout(timeout);
  fontsLoaded = true;
}

export default async function OGImage({ params }: { params: { slug: string } }) {
  const { slug } = params;

  await loadFonts();

  const sb = getSupabaseServer();
  const { data: slugRow } = await sb
    .from("incidents")
    .select("id")
    .eq("slug", slug)
    .single();

  if (!slugRow) {
    // Return a generic fallback
    return new ImageResponse(
      (
        <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#0a0a0a", color: "#e8e6e0", fontSize: "32px" }}>
          UFO Dossier
        </div>
      ),
      size
    );
  }

  const { data: incident } = await sb
    .from("v_incident_full")
    .select("title, summary, occurred_at, occurred_at_text, branch, location_text, resolution_status, source_agency, case_id")
    .eq("id", slugRow.id)
    .single();

  if (!incident) {
    return new ImageResponse(
      (
        <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#0a0a0a", color: "#e8e6e0", fontSize: "32px" }}>
          UFO Dossier
        </div>
      ),
      size
    );
  }

  const date = incident.occurred_at ?? incident.occurred_at_text ?? "Undated";
  const branch = incident.branch ?? incident.source_agency ?? "";
  const status = incident.resolution_status?.replace("_", " ").toUpperCase() ?? "";
  const title = incident.title.length > 90 ? incident.title.slice(0, 87) + "..." : incident.title;
  const summary = incident.summary
    ? incident.summary.length > 180
      ? incident.summary.slice(0, 177) + "..."
      : incident.summary
    : "";

  const fonts: { name: string; data: ArrayBuffer; style: "normal" }[] = [];
  if (specialEliteFont) fonts.push({ name: "Special Elite", data: specialEliteFont, style: "normal" });
  if (jetBrainsFont) fonts.push({ name: "JetBrains Mono", data: jetBrainsFont, style: "normal" });

  const titleFont = specialEliteFont ? "Special Elite" : "serif";
  const monoFont = jetBrainsFont ? "JetBrains Mono" : "monospace";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#0a0a0a",
          color: "#e8e6e0",
          padding: "60px",
          position: "relative",
        }}
      >
        {/* Vignette border */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            border: "8px solid rgba(255,255,255,0.03)",
          }}
        />

        {/* Top bar */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "30px",
          }}
        >
          <span
            style={{
              fontFamily: monoFont,
              fontSize: "13px",
              color: "#c8302a",
              letterSpacing: "3px",
              textTransform: "uppercase",
              border: "1px solid #c8302a",
              padding: "4px 12px",
            }}
          >
            {status || "UNCLASSIFIED"}
          </span>
          <span
            style={{
              fontFamily: monoFont,
              fontSize: "12px",
              color: "#666",
              letterSpacing: "2px",
            }}
          >
            {incident.case_id}
          </span>
        </div>

        {/* Title */}
        <div
          style={{
            fontFamily: titleFont,
            fontSize: "42px",
            lineHeight: 1.15,
            marginBottom: "20px",
            maxWidth: "900px",
          }}
        >
          {title}
        </div>

        {/* Summary */}
        {summary && (
          <div
            style={{
              fontSize: "18px",
              lineHeight: 1.6,
              color: "#999",
              marginBottom: "auto",
              maxWidth: "850px",
            }}
          >
            {summary}
          </div>
        )}

        {/* Bottom bar */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            borderTop: "1px solid #2a2925",
            paddingTop: "20px",
            marginTop: "20px",
          }}
        >
          <div style={{ display: "flex", gap: "24px" }}>
            <span style={{ fontFamily: monoFont, fontSize: "13px", color: "#888" }}>
              {date}
            </span>
            {branch && (
              <span style={{ fontFamily: monoFont, fontSize: "13px", color: "#888", textTransform: "uppercase" }}>
                {branch}
              </span>
            )}
            {incident.location_text && (
              <span style={{ fontFamily: monoFont, fontSize: "13px", color: "#888" }}>
                {incident.location_text.length > 40
                  ? incident.location_text.slice(0, 37) + "..."
                  : incident.location_text}
              </span>
            )}
          </div>
          <span style={{ fontFamily: monoFont, fontSize: "13px", color: "#ff9933" }}>
            ufodossier.com
          </span>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: fonts.length > 0 ? fonts : undefined,
    }
  );
}
