"use client";

import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const links = [
  { href: "/", label: "Archive", key: "home" },
  { href: "/map", label: "Map", key: "map" },
  { href: "/collections", label: "Collections", key: "collections" },
  { href: "/media", label: "Media", key: "media" },
  { href: "/ask", label: "Ask", key: "ask" },
  { href: "/about", label: "About", key: "about" },
];

export function TopBar({ active = "archive" }: { active?: string }) {
  return (
    <>
      <header className="fixed top-0 left-0 right-0 bg-bg z-50">
        {/* Top row: wordmark + desktop nav + theme toggle */}
        <div className="max-w-content mx-auto px-4 md:px-6 h-14 flex items-center justify-between">
          <Link href="/" className="text-sm font-sans font-semibold tracking-tracked text-ink uppercase shrink-0">
            UFO Dossier
          </Link>

          {/* Desktop nav — inline */}
          <nav className="hidden md:flex items-center gap-6">
            {links.map((l) => (
              <Link
                key={l.key}
                href={l.href}
                className={`text-sm whitespace-nowrap transition-colors ${
                  active === l.key
                    ? "text-ink font-medium"
                    : "text-ink-dim hover:text-ink"
                }`}
              >
                {l.label}
              </Link>
            ))}
            <ThemeToggle />
          </nav>

          {/* Mobile theme toggle only */}
          <div className="md:hidden">
            <ThemeToggle />
          </div>
        </div>

        {/* Mobile nav — second row, centered */}
        <nav className="md:hidden border-t border-rule">
          <div className="flex items-center justify-center gap-6 h-10">
            {links.map((l) => (
              <Link
                key={l.key}
                href={l.href}
                className={`text-xs whitespace-nowrap transition-colors ${
                  active === l.key
                    ? "text-ink font-medium"
                    : "text-ink-dim hover:text-ink"
                }`}
              >
                {l.label}
              </Link>
            ))}
          </div>
        </nav>
      </header>
      {/* Spacer: 56px on desktop, 96px on mobile (56+40) */}
      <div className="h-24 md:h-14" />
    </>
  );
}
