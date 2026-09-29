"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

export function BackLink({ href }: { href: string }) {
  const router = useRouter();

  return (
    <Link
      href={href}
      className="text-sm text-ink-faint hover:text-ink transition-colors"
      onClick={(event) => {
        const ref = document.referrer;
        if (!ref) return;
        try {
          if (new URL(ref).origin === window.location.origin) {
            event.preventDefault();
            router.back();
          }
        } catch {
          // A broken referrer uses the fallback link.
        }
      }}
    >
      &larr; Back
    </Link>
  );
}
