import { HeaderShell } from "@/components/HeaderShell";
import { Footer } from "@/components/Footer";
import { JsonLd } from "@/components/JsonLd";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About This Archive",
  description: "Methodology, sources, and known limitations of the UFO Dossier declassified UAP archive.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@type": "WebPage",
        name: "About This Archive — UFO Dossier",
        description: "Methodology, sources, and known limitations of the UFO Dossier declassified UAP archive.",
        url: "https://www.ufodossier.com/about",
        isPartOf: { "@type": "WebSite", name: "UFO Dossier", url: "https://www.ufodossier.com" },
      }} />
      <HeaderShell active="about" />

      <article className="max-w-prose mx-auto px-4 md:px-6 pt-10 md:pt-16 pb-14 md:pb-20">
        <h1 className="font-serif text-2xl md:text-4xl font-medium mb-3">
          About this archive
        </h1>
        <p className="text-ink-dim mb-10 max-w-md leading-relaxed">
          A plain account of what we did, what we didn&apos;t do, and where to verify
          anything you read here against the original record.
        </p>

        <div className="space-y-10 text-[16px] leading-[1.75] text-ink">
          <section>
            <h2 className="font-serif text-xl font-medium mb-3">What this archive is</h2>
            <p className="mb-4">
              UFO Dossier is a searchable archive of publicly released
              U.S. government records of unidentified anomalous phenomena (UAP), from the PURSUE releases at{" "}
              <a href="https://war.gov/UFO" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                war.gov/UFO
              </a>
              . PURSUE is the Pentagon program that published these files.
              We are not affiliated with the U.S. government. The original files are theirs.
            </p>
            <p>
              The counts on the homepage are three different things: official files, passages checked
              against those files, and the sightings those passages describe. One sighting can show up
              in more than one passage.
            </p>
          </section>

          <section>
            <h2 className="font-serif text-xl font-medium mb-3">How a record gets here</h2>
            <ol className="list-decimal pl-5 space-y-2">
              <li>We start from the public list of PURSUE files.</li>
              <li>The original file is kept.</li>
              <li>We use the text in the file. If that text cannot be read, the pages are read with optical character recognition.</li>
              <li>Each file is noted as a sighting report, program paperwork, or a photo, video, or audio file.</li>
              <li>A short reading is written from the file, always tied to a quote copied from it.</li>
              <li>The quote is checked against the file. A paraphrase or an invented sentence is dropped.</li>
              <li>A passage that is too thin to stand as a case is dropped.</li>
              <li>Passages that describe the same sighting are grouped. A photo, a video, or a later analysis can belong to that sighting without becoming a second case. A set of related sightings, such as the Western U.S. reports from 2023, stays a set.</li>
              <li>Search and the public pages keep a file, a passage, and a sighting distinct.</li>
            </ol>
          </section>

          <section>
            <h2 className="font-serif text-xl font-medium mb-3">Passages, sightings, and files</h2>
            <p className="mb-4">
              A passage is one checked quote and the details taken from it. A sighting is the
              episode those passages describe. A series, such as the Western U.S. reports from
              2023, is a set of sightings, not one giant sighting. The source is the government
              file itself. A photo or a later write-up can belong to a sighting without becoming
              a second case.
            </p>
            <p>
              Colorado Springs in 2022 is the worked example: one sighting, the main account,
              a photo or video, and a later analysis. The photo or video is not a separate case.
            </p>
          </section>

          <section>
            <h2 className="font-serif text-xl font-medium mb-3">What we do not claim</h2>
            <p>
              This site does not claim that UAPs are extraterrestrial, that the U.S.
              government has recovered alien technology, or that any single incident has
              a paranormal explanation. The Pentagon&apos;s All-domain Anomaly
              Resolution Office (AARO), which reviewed many of these incidents officially,
              has reached no such conclusion either. The dataset is observational &mdash;
              what was seen, by whom, with what sensors, and what remained unresolved.
            </p>
          </section>

          <section>
            <h2 className="font-serif text-xl font-medium mb-3">Limits and known gaps</h2>
            <p className="mb-4">
              When a document is ambiguous, the reading can mislabel the sensor or the
              service branch. Those fields are marked unknown rather than guessed.
            </p>
            <p className="mb-4">
              Heavily redacted documents may produce cases with very few details.
              They are still listed, because the file exists even when most of it is blacked out.
            </p>
            <p className="mb-4" id="geocoding">
              Roughly 60% of incidents could be placed on the map; the rest
              lack precise coordinates in the source text and appear in lists
              but not on the map. Older FBI case files often describe sightings
              without specific geographic detail.
            </p>
            <p>
              Videos and audio in this version are linked as official sources. This site does not
              invent a transcript when the release did not include one.
            </p>
          </section>
        </div>
      </article>

      <Footer />
    </>
  );
}
