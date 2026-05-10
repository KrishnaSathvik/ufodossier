import { TopBar } from "@/components/TopBar";
import { Footer } from "@/components/Footer";
import { JsonLd } from "@/components/JsonLd";
import { getMediaIncidents } from "@/lib/incidents";
import { MediaGrid } from "./MediaGrid";
import type { Metadata } from "next";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Source Media",
  description: "Source images, videos, and document covers from the U.S. government's declassified UAP files.",
  alternates: { canonical: "/media" },
};

export default async function MediaPage() {
  const { images, videos, documents } = await getMediaIncidents();

  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: "Source Media — UFO Dossier",
        description: "Source images, videos, and document covers from declassified UAP files.",
        url: "https://ufodossier.com/media",
        isPartOf: { "@type": "WebSite", name: "UFO Dossier", url: "https://ufodossier.com" },
      }} />
      <TopBar active="media" />
      <main className="max-w-content mx-auto px-4 md:px-6 py-10 md:py-14">
        <h1 className="font-serif text-2xl md:text-3xl font-medium mb-2">Source media</h1>
        <p className="text-ink-dim mb-8 max-w-prose">
          Images, videos, and document covers from the declassified source documents. Each links to its corresponding incident case file.
        </p>

        <MediaGrid images={images} videos={videos} documents={documents} />
      </main>
      <Footer />
    </>
  );
}
