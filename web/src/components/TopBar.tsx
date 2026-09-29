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
    <div className="max-w-content mx-auto px-4 md:px-6">
      <div className="h-14 flex items-center justify-between gap-4">
        <Link href="/" className="text-sm font-sans font-semibold tracking-tracked text-ink uppercase shrink-0">
          UFO Dossier
        </Link>
        <div className="flex items-center gap-4">
          <nav className="hidden sm:flex items-center gap-4">
            <NavLinks active={active} className="text-sm" />
          </nav>
          <ThemeToggle />
        </div>
      </div>
      <nav className="sm:hidden flex items-center justify-between pb-3">
        <NavLinks active={active} className="text-sm" />
      </nav>
    </div>
  );
}

/** @deprecated Prefer HeaderShell so the status banner stays under the nav. */
export function TopBar({ active = "archive" }: { active?: string }) {
  return (
    <>
      <header className="fixed top-0 left-0 right-0 bg-bg z-50 border-b border-rule">
        <TopBarNav active={active} />
      </header>
      <div className="h-[5.5rem] sm:h-14" />
    </>
  );
}
