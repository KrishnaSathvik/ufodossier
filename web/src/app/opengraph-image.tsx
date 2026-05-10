import { ImageResponse } from "next/og";

export const runtime = "edge";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };

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

export default async function OGImage() {
  await loadFonts();

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
          justifyContent: "center",
          alignItems: "center",
          backgroundColor: "#0a0a0a",
          color: "#e8e6e0",
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

        <span
          style={{
            fontFamily: monoFont,
            fontSize: "16px",
            color: "#c8302a",
            letterSpacing: "4px",
            textTransform: "uppercase",
            border: "2px solid #c8302a",
            padding: "8px 20px",
            marginBottom: "40px",
            transform: "rotate(-8deg)",
          }}
        >
          Declassified
        </span>

        <div
          style={{
            fontFamily: titleFont,
            fontSize: "56px",
            lineHeight: 1.1,
            textAlign: "center",
            marginBottom: "24px",
          }}
        >
          UFO Dossier
        </div>

        <div
          style={{
            fontSize: "20px",
            color: "#999",
            textAlign: "center",
            maxWidth: "700px",
            lineHeight: 1.5,
          }}
        >
          Every UAP incident in the U.S. government's declassified files. Every claim sourced. Every document linked.
        </div>

        <span
          style={{
            fontFamily: monoFont,
            fontSize: "14px",
            color: "#ff9933",
            marginTop: "50px",
            letterSpacing: "2px",
          }}
        >
          ufodossier.com
        </span>
      </div>
    ),
    {
      ...size,
      fonts: fonts.length > 0 ? fonts : undefined,
    }
  );
}
