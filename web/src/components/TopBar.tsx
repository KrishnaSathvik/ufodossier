"use client";

import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const links = [
  { href: "/", label: "Archive", key: "archive" },
  { href: "/map", label: "Map", key: "map" },
  { href: "/collections", label: "Collections", key: "collections" },
  { href: "/media", label: "Media", key: "media" },
  { href: "/audio", label: "Audio", key: "audio" },
  { href: "/ask", label: "Ask", key: "ask" },
];

function NavLinks({ active, className }: { active: string; className: string }) {
  return (
    <>
      {links.map((l) => (
        <Link
          key={l.key}
          href={l.href}
          className={`whitespace-nowrap transition-colors ${className} ${
            active === l.key ? "text-ink font-medium" : "text-ink-dim hover:text-ink"
          }`}
        >
          {l.label}
        </Link>
      ))}
    </>
  );
}

export function TopBarNav({ active = "archive" }: { active?: string }) {
  return (
    <div className="site-shell">
      <div className="h-14 lg:h-16 flex items-center justify-between gap-4">
        <Link
          href="/"
          className="shrink-0 text-ink hover:opacity-90 transition-opacity text-sm lg:text-lg font-sans font-semibold tracking-tracked uppercase"
        >
          UFO Dossier
        </Link>
        <div className="flex items-center gap-4 lg:gap-6">
          <nav className="hidden sm:flex items-center gap-4 lg:gap-6">
            <NavLinks active={active} className="text-sm lg:text-base" />
          </nav>
          <ThemeToggle />
        </div>
      </div>
      <nav className="sm:hidden flex items-center justify-between pb-3">
        <NavLinks active={active} className="text-sm lg:text-base" />
      </nav>
    </div>
  );
}

/** @deprecated Prefer HeaderShell so the status banner stays under the nav. */
export function TopBar({ active = "archive" }: { active?: string }) {
  return (
    <>
      <header className="sticky top-0 shrink-0 bg-bg z-50 border-b border-rule">
        <TopBarNav active={active} />
      </header>
    </>
  );
}
