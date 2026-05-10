import { TopBar } from "@/components/TopBar";
import { Footer } from "@/components/Footer";
import { AskForm } from "./AskForm";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ask the Archive",
  description: "Ask questions about the declassified UAP archive. Every answer is grounded in the corpus.",
  robots: { index: false, follow: true },
};

export default function AskPage() {
  return (
    <>
      <TopBar active="ask" />

      <main className="max-w-prose mx-auto px-4 md:px-6 pt-12 md:pt-20 pb-14 md:pb-20">
        <h1 className="font-serif text-2xl md:text-4xl font-medium mb-3">
          Ask the archive
        </h1>
        <p className="text-ink-dim mb-8 max-w-md">
          Every answer is grounded in the corpus. If the evidence isn&apos;t there, the answer says so.
        </p>

        <AskForm />
      </main>

      <Footer />
    </>
  );
}
