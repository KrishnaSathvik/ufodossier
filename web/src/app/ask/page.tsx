import { AskForm } from "./AskForm";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ask the Archive",
  description: "Ask questions about the declassified UAP archive. Answers use only the records in this archive.",
  robots: { index: true, follow: true },
  openGraph: {
    title: "Ask the Archive — UFO Dossier",
    description: "Search the records by case, place, year, or file.",
    images: [{ url: "/og/ask.png", width: 1200, height: 630, alt: "Ask the Archive — UFO Dossier" }],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og/ask.png"],
  },
};

export default function AskPage() {
  return (
    <>


      <main className="site-shell py-10 md:py-14">
        <AskForm />
      </main>
    </>
  );
}
