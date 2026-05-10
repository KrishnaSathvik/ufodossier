import { TopBar } from "@/components/TopBar";
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
      <TopBar active="about" />

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
            <h2 className="font-serif text-xl font-medium mb-3">Source</h2>
            <p className="mb-4">
              Every file in this archive originated from the U.S. Department of
              War&apos;s public release portal at{" "}
              <a href="https://war.gov/UFO" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                war.gov/UFO
              </a>
              , an interagency effort officially titled the Presidential Unsealing and
              Reporting System for UAP Encounters (PURSUE). We are not affiliated with the
              U.S. government. The original files are their work; we have only
              restructured them.
            </p>
            <p>
              Every incident page links to the original document on war.gov so
              you can verify any claim against the source.
            </p>
          </section>

          <section>
            <h2 className="font-serif text-xl font-medium mb-3">Preventing hallucination</h2>
            <p className="mb-4">
              The structured fields you see in case files &mdash; date, location,
              branch, sensor type, summary &mdash; are produced by a language model
              reading the source text. To prevent fabricated incidents from
              appearing here, every extracted incident must include a verbatim
              excerpt that we substring-validate against the original document.
              If the quote isn&apos;t actually in the source, the incident is
              dropped. The validator was tested against real source text plus
              deliberately fabricated rows; it preserved every real quote and
              dropped every fabricated one.
            </p>
            <p>
              When in doubt, the verbatim excerpt is ground truth &mdash; not the
              structured fields. And when in further doubt, click through to
              the original PDF.
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
              The model occasionally misclassifies sensor types or branches
              when the source is ambiguous. We mark such fields as unknown
              rather than guess.
            </p>
            <p className="mb-4">
              Heavily redacted documents may produce incidents with very sparse
              fields. They are still listed, because their existence is itself
              signal.
            </p>
            <p className="mb-4" id="geocoding">
              Roughly 60% of incidents could be placed on the map; the rest
              lack precise coordinates in the source text and appear in lists
              but not on the map. Older FBI case files often describe sightings
              without specific geographic detail.
            </p>
            <p>
              Videos are linked, not transcribed. Their official war.gov
              captions appear in their place.
            </p>
          </section>
        </div>
      </article>

      <Footer />
    </>
  );
}
