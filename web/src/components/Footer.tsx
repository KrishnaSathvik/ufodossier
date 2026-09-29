import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-rule mt-16 shrink-0">
      <div className="site-shell flex flex-wrap items-center justify-center gap-y-2 py-6 lg:py-7 lg:gap-x-1 text-[13px] lg:text-base font-sans text-ink-faint lg:text-ink-dim text-center leading-relaxed">
        <a href="https://www.war.gov/UFO/" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors">war.gov/UFO</a>
        <span className="mx-1.5">&middot;</span>
        <a href="https://www.aaro.mil/" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors">AARO</a>
        <span className="mx-1.5">&middot;</span>
        <a href="https://www.dvidshub.net/" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors">DVIDS</a>
        <span className="mx-1.5">&middot;</span>
        <Link href="/sources" className="hover:text-accent transition-colors">Sources</Link>
        <span className="mx-1.5">&middot;</span>
        <Link href="/releases" className="hover:text-accent transition-colors">Releases</Link>
        <span className="mx-1.5">&middot;</span>
        <Link href="/about" className="hover:text-accent transition-colors">About</Link>
      </div>
    </footer>
  );
}
