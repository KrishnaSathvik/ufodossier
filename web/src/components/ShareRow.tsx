"use client";

import { useState } from "react";

interface ShareRowProps {
  url: string;
  title: string;
}

export function ShareRow({ url, title }: ShareRowProps) {
  const [copied, setCopied] = useState(false);

  const fullUrl = `https://ufodossier.com${url}`;
  const text = encodeURIComponent(title);
  const encodedUrl = encodeURIComponent(fullUrl);

  function handleCopy() {
    navigator.clipboard.writeText(fullUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="flex items-center gap-4 text-sm text-ink-faint py-4">
      <button
        onClick={handleCopy}
        className="hover:text-accent transition-colors"
      >
        {copied ? "Link copied" : "Copy link"}
      </button>
      <a
        href={`https://x.com/intent/tweet?text=${text}&url=${encodedUrl}`}
        target="_blank"
        rel="noopener noreferrer"
        className="hover:text-accent transition-colors"
      >
        X
      </a>
      <a
        href={`https://bsky.app/intent/compose?text=${text}+${encodedUrl}`}
        target="_blank"
        rel="noopener noreferrer"
        className="hover:text-accent transition-colors"
      >
        Bluesky
      </a>
    </div>
  );
}
