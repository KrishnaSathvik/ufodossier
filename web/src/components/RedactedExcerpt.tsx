/**
 * Renders a raw_excerpt with bracketed redactions styled visually.
 * Detects patterns like [SITE CODE NAME], [CALL SIGN 1], [REDACTED], etc.
 */
export function RedactedExcerpt({ text, className }: { text: string; className?: string }) {
  const parts = text.split(/(\[[A-Z][A-Z0-9 /\-]+\])/g);
  return (
    <span className={className}>
      {parts.map((part, i) =>
        /^\[[A-Z][A-Z0-9 /\-]+\]$/.test(part) ? (
          <span
            key={i}
            className="bg-ink/10 text-ink-faint px-1 rounded-sm font-mono text-[0.92em]"
            title="Redacted by source"
          >
            {part}
          </span>
        ) : (
          part
        )
      )}
    </span>
  );
}
