import { JsonLd } from "@/components/JsonLd";
import { listAudio } from "@/lib/corpus/catalog";
import { VideoCard } from "@/components/VideoCard";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Audio Records",
  description: "Official audio from the PURSUE releases, played from the same DVIDS recordings.",
  alternates: { canonical: "/audio" },
  openGraph: {
    title: "Audio — UFO Dossier",
    description: "Official recordings and audio excerpts from the released files.",
    images: [{ url: "/og/audio.png", width: 1200, height: 630, alt: "Audio — UFO Dossier" }],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og/audio.png"],
  },
};

export default function AudioPage() {
  const records = listAudio();

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: "Audio Records — UFO Dossier",
        description: "Official audio source records from the PURSUE releases.",
        url: "https://www.ufodossier.com/audio",
      }} />

      <main className="site-shell py-10 md:py-14">
        <h1 className="lg:text-4xl font-serif text-2xl md:text-4xl font-medium mb-3">Audio</h1>
        <p className="text-ink-dim max-w-prose mb-8">
          {records.length.toLocaleString()} official audio recordings from the government releases.
          Press play to hear the same recording published on DVIDS. The text under the title is the government description, not a transcript.
        </p>
        {records.length === 0 ? (
          <p className="text-ink-faint">No audio recordings are listed yet.</p>
        ) : (
          <div className="media-grid">
            {records.map((record) => (
              <VideoCard
                key={record.slug}
                video={{
                  id: record.slug,
                  filename: record.title,
                  url: record.dvidsId ? `https://www.dvidshub.net/video/${record.dvidsId}` : `/source/${record.slug}`,
                  embed_url: record.dvidsId ? `https://www.dvidshub.net/video/embed/${record.dvidsId}` : "",
                  thumbnail_url: null,
                  agency: record.agency,
                  blurb: record.dvidsId ? null : "No playable file is published for this recording.",
                  release: record.release,
                  href: `/source/${record.slug}`,
                }}
              />
            ))}
          </div>
        )}
      </main>

    </>
  );
}
