import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-rule mt-16">
      <div className="max-w-[1080px] mx-auto px-4 py-8 text-[13px] font-sans text-ink-faint text-center leading-relaxed">
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
