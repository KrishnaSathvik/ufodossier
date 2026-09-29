import Link from "next/link";

export default function NotFound() {
  return (
    <>

      <main className="site-shell py-24 md:py-32 text-center">
        <p className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-4">
          File not found
        </p>
        <h1 className="font-serif text-3xl md:text-4xl font-medium mb-6">
          Page not found
        </h1>
        <p className="text-ink-dim max-w-md mx-auto mb-8 leading-relaxed">
          The requested document does not exist in this archive. It may have
          been moved, or this address is not a page in the archive.
        </p>
        <Link
          href="/"
          className="inline-block px-6 py-2.5 border border-rule text-sm font-medium hover:border-ink-faint transition-colors"
        >
          Return to archive &rarr;
        </Link>
      </main>

    </>
  );
}
