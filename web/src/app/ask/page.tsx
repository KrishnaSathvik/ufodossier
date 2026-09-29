import { HeaderShell } from "@/components/HeaderShell";
import { AskForm } from "./AskForm";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ask the Archive",
  description: "Ask questions about the declassified UAP archive. Answers use only the records in this archive.",
  robots: { index: true, follow: true },
};

export default function AskPage() {
  return (
    <>
      <HeaderShell active="ask" />

      <main className="flex flex-col h-[calc(100dvh-5.5rem)] sm:h-[calc(100dvh-3.5rem)] overflow-hidden">
        <AskForm />
      </main>
    </>
  );
}
