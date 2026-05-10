"use client";

import { useState } from "react";
import Link from "next/link";

interface Citation {
  id: string;
  slug: string | null;
  case_id: string;
  title: string;
  occurred_at: string | null;
  location_text: string | null;
}

/**
 * Strip trailing markdown-style citation lists that Claude sometimes appends
 * despite instructions not to. Matches patterns like:
 * "Sources:\n* [text](url)" or "References:\n- [text](url)"
 */
function stripTrailingCitations(text: string): string {
  return text.replace(/\n{1,2}(?:Sources|References|Citations|Cited cases):?\s*\n(?:\s*[-*]\s*\[.+?\]\(.+?\).*\n?)+$/i, "").trimEnd();
}

export function AskForm() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [permalink, setPermalink] = useState<string | null>(null);

  async function handleAsk(e?: React.FormEvent) {
    e?.preventDefault();
    if (!question.trim() || loading) return;

    setLoading(true);
    setAnswer("");
    setCitations([]);
    setPermalink(null);

    try {
      const r = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!r.ok) throw new Error("query failed");

      const reader = r.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          // Flush remaining bytes from the decoder
          buf += decoder.decode();
          break;
        }
        buf += decoder.decode(value, { stream: true });

        const parts = buf.split("\n\n");
        buf = parts.pop() ?? ""; // Keep incomplete trailing chunk
        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(part.slice(6));
            if (payload.type === "text") setAnswer((a) => a + payload.text);
            else if (payload.type === "citations") setCitations(payload.citations);
            else if (payload.type === "slug") setPermalink(payload.slug);
          } catch {
            // Malformed JSON chunk — skip
          }
        }
      }

      // Process any remaining complete event still in buf after stream ends
      if (buf.trim()) {
        for (const part of buf.split("\n\n")) {
          if (!part.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(part.slice(6));
            if (payload.type === "text") setAnswer((a) => a + payload.text);
            else if (payload.type === "citations") setCitations(payload.citations);
            else if (payload.type === "slug") setPermalink(payload.slug);
          } catch {
            // Incomplete final chunk — discard
          }
        }
      }
    } catch {
      setAnswer("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  // Clean the answer: strip any markdown citation lists Claude may have appended
  const displayAnswer = stripTrailingCitations(answer);

  const examples = [
    "What did the FBI investigate in 1947?",
    "Which incidents involved radar detection?",
    "What happened near Washington D.C.?",
    "Are there any NASA-related sightings?",
  ];

  return (
    <>
      <form onSubmit={handleAsk} className="relative mb-4">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Search the declassified archive..."
          className="w-full bg-bg border border-rule focus:border-accent pl-4 pr-20 py-3 text-sm text-ink outline-none transition-colors"
          disabled={loading}
          autoFocus
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="absolute right-1 top-1/2 -translate-y-1/2 px-3 py-1.5 text-sm text-ink-dim hover:text-ink disabled:opacity-30 transition-colors"
        >
          {loading ? "Searching..." : "Ask"}
        </button>
      </form>

      <div className="flex gap-2 flex-wrap mb-10">
        {examples.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => setQuestion(ex)}
            className="text-sm text-ink-dim hover:text-ink border border-rule px-3 py-1 hover:border-ink-faint transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      {(answer || loading) && (
        <div className="border-t border-rule pt-8">
          <div className="font-serif text-[17px] leading-[1.7] text-ink whitespace-pre-wrap">
            {displayAnswer || (
              <span className="text-ink-faint text-sm">Searching the archive...</span>
            )}
          </div>

          {citations.length > 0 && (
            <div className="mt-8 pt-6 border-t border-rule">
              <h3 className="text-xs font-mono uppercase tracking-tracked text-ink-faint mb-3">
                Cited cases
              </h3>
              <ul className="space-y-1">
                {citations.map((c) => (
                  <li key={c.id} className="font-mono text-xs flex gap-3 items-baseline py-1">
                    <Link
                      href={`/incident/${c.slug ?? c.id}`}
                      className="text-accent hover:underline shrink-0"
                    >
                      [{c.case_id}]
                    </Link>
                    <span className="text-ink-faint">&middot;</span>
                    <span className="text-accent/70">
                      {c.occurred_at ?? "?"}
                    </span>
                    <span className="text-ink-faint">&middot;</span>
                    <span className="text-ink-dim truncate">
                      {c.location_text ?? "\u2014"}
                    </span>
                    <span className="text-ink-faint">&middot;</span>
                    <span className="text-ink truncate">
                      {c.title}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {permalink && (
            <div className="mt-6 pt-4 border-t border-rule flex justify-between items-center text-xs text-ink-faint">
              <span className="font-mono truncate">/ask/{permalink}</span>
              <button
                onClick={() => navigator.clipboard.writeText(`${window.location.origin}/ask/${permalink}`)}
                className="hover:text-ink transition-colors ml-4 shrink-0"
              >
                Copy link
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
