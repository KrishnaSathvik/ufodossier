import { ImageResponse } from "next/og";

export const runtime = "edge";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };
export const revalidate = 604800; // 1 week

export default async function OGImage() {
  const logoUrl = new URL("/logo.png", "https://www.ufodossier.com").toString();

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
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          alt=""
          src={logoUrl}
          style={{ width: "400px", height: "400px" }}
        />
      </div>
    ),
    { ...size },
  );
}
