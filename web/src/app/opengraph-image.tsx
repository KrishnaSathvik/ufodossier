import { ImageResponse } from "next/og";

export const runtime = "edge";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };
export const revalidate = 604800; // 1 week

const HERO_IMAGE_URL =
  "https://whyrlabwefasmmebtzja.supabase.co/storage/v1/object/public/source-files/media/e0900a2af183fc926c75be658b91084ae489bd7c077b3bdf3d756cc24a7ca98f/DOW-UAP-PR46-Unresolved-UAP-Report-INDOPACOM-2024.jpg";

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
// Image fetching — 5-second timeout, returns data-URL or null
// ---------------------------------------------------------------------------
async function fetchImageData(url: string): Promise<string | null> {
  try {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), 5000);
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
    console.error("Hero image fetch failed:", e);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Text overlay (shared between image and dark fallback variants)
// ---------------------------------------------------------------------------
function TextOverlay({
  serifFont,
  monoFont,
}: {
  serifFont: string;
  monoFont: string;
}) {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        display: "flex",
        flexDirection: "column",
        padding: "0 60px 60px 60px",
      }}
    >
      <span
        style={{
          fontFamily: monoFont,
          fontSize: "18px",
          fontWeight: 500,
          letterSpacing: "0.2em",
          color: "rgba(255,255,255,0.85)",
          marginBottom: "16px",
        }}
      >
        UFO DOSSIER
      </span>
      <span
        style={{
          fontFamily: serifFont,
          fontSize: "56px",
          fontWeight: 500,
          color: "#ffffff",
          lineHeight: 1.1,
          maxWidth: "1000px",
          marginBottom: "20px",
        }}
      >
        Every declassified UAP incident, in one searchable archive.
      </span>
      <span
        style={{
          fontFamily: monoFont,
          fontSize: "14px",
          fontWeight: 400,
          letterSpacing: "0.05em",
          color: "rgba(255,255,255,0.75)",
        }}
      >
        480 cases · 1890–2025 · www.ufodossier.com
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// OG image handler
// ---------------------------------------------------------------------------
export default async function OGImage() {
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

  const imageData = await fetchImageData(HERO_IMAGE_URL);

  // =========================================================================
  // Image variant — football-shaped object with text overlay
  // =========================================================================
  if (imageData) {
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
          {/* Full-bleed hero image */}
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

          {/* Darkening gradient overlay */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background:
                "linear-gradient(to bottom, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.55) 100%)",
              display: "flex",
            }}
          />

          <TextOverlay serifFont={serifFont} monoFont={monoFont} />
        </div>
      ),
      { ...size, fonts: fontOpts },
    );
  }

  // =========================================================================
  // Dark fallback — if hero image fetch fails
  // =========================================================================
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          position: "relative",
          backgroundColor: "#1a1a1a",
        }}
      >
        <TextOverlay serifFont={serifFont} monoFont={monoFont} />
      </div>
    ),
    { ...size, fonts: fontOpts },
  );
}
