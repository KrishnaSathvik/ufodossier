"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

interface Citation {
  id: string;
  slug: string | null;
  case_id: string;
  title: string;
  occurred_at: string | null;
  location_text: string | null;
  href?: string;
}

interface Turn {
  id: string;
  question: string;
  answer: string;
  citations: Citation[];
}

const EXAMPLES = [
  "What did the FBI investigate in 1947?",
  "Which incidents involved radar detection?",
  "What happened near Washington D.C.?",
  "Are there any NASA-related sightings?",
];

function stripTrailingCitations(text: string): string {
  return text.replace(/\n{1,2}(?:Sources|References|Citations|Cited cases):?\s*\n(?:\s*[-*]\s*\[.+?\]\(.+?\).*\n?)+$/i, "").trimEnd();
}

function citedIdsIn(text: string): Set<string> {
  return new Set(Array.from(text.matchAll(/\[([A-Za-z0-9-]+)\]/g), (match) => match[1].toUpperCase()));
}

function sourcesFor(text: string, citations: Citation[]): Citation[] {
  const named = citedIdsIn(text);
  const lower = text.toLowerCase();
  const picked = citations.filter((citation) => {
    if (named.has(citation.case_id.toUpperCase())) return true;
    if (lower.includes(citation.case_id.toLowerCase())) return true;
    const title = citation.title.toLowerCase();
    return title.length > 16 && lower.includes(title.slice(0, 48));
  });
  if (picked.length > 0) return picked;
  if (/do not answer|does not answer|nothing in the records|no matching records/i.test(text)) return [];
  return citations;
}

function InlineText({ text, citations }: { text: string; citations: Citation[] }) {
  const byCase = new Map(citations.map((citation) => [citation.case_id.toUpperCase(), citation]));
  const parts = text.split(/(\[[A-Za-z0-9-]+\])/g);

  return (
    <>
      {parts.map((part, index) => {
        const match = part.match(/^\[([A-Za-z0-9-]+)\]$/);
        const citation = match ? byCase.get(match[1].toUpperCase()) : undefined;
        if (!citation) return <span key={index}>{part}</span>;
        return (
          <Link
            key={index}
            href={citation.href ?? `/incident/${citation.slug ?? citation.id}`}
            className="text-accent hover:underline"
          >
            {part}
          </Link>
        );
      })}
    </>
  );
}

function AnswerBody({ text, citations }: { text: string; citations: Citation[] }) {
  const blocks = stripTrailingCitations(text).split(/\n{2,}/).filter((block) => block.trim());

  return (
    <div className="space-y-4">
      {blocks.map((block, index) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        const bullets = lines.length > 1 && lines.every((line) => /^[-*]\s+/.test(line));
        const numbered = lines.length > 1 && lines.every((line) => /^\d+[.)]\s+/.test(line));

        if (bullets || numbered) {
          const ListTag = numbered ? "ol" : "ul";
          return (
            <ListTag
              key={index}
              className={`space-y-2 pl-5 ${numbered ? "list-decimal" : "list-disc"}`}
            >
              {lines.map((line) => (
                <li key={line}>
                  <InlineText text={line.replace(/^(?:[-*]|\d+[.)])\s+/, "")} citations={citations} />
                </li>
              ))}
            </ListTag>
          );
        }

        return (
          <p key={index}>
            {lines.map((line, lineIndex) => (
              <span key={lineIndex}>
                {lineIndex > 0 ? " " : null}
                <InlineText text={line} citations={citations} />
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function applyEvent(turn: Turn, payload: { type?: string; text?: string; citations?: Citation[]; slug?: string }): Turn {
  if (payload.type === "text") return { ...turn, answer: turn.answer + (payload.text ?? "") };
  if (payload.type === "replace") return { ...turn, answer: payload.text ?? "" };
  if (payload.type === "citations") return { ...turn, citations: payload.citations ?? [] };
  return turn;
}

export function AskForm() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  async function handleAsk(text?: string) {
    const asked = (text ?? question).trim();
    if (!asked || loading) return;

    const id = crypto.randomUUID();
    setQuestion("");
    if (field.current) field.current.style.height = "auto";
    setTurns((current) => [
      ...current,
      { id, question: asked, answer: "", citations: [] },
    ]);
    setLoading(true);

    const write = (payload: { type?: string; text?: string; citations?: Citation[]; slug?: string }) => {
      setTurns((current) => current.map((turn) => (turn.id === id ? applyEvent(turn, payload) : turn)));
    };

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: asked }),
      });
      if (!response.ok || !response.body) throw new Error("query failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          buf += decoder.decode();
          break;
        }
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          try {
            write(JSON.parse(part.slice(6)));
          } catch {
            // Malformed chunk — skip
          }
        }
      }

      if (buf.trim()) {
        for (const part of buf.split("\n\n")) {
          if (!part.startsWith("data: ")) continue;
          try {
            write(JSON.parse(part.slice(6)));
          } catch {
            // Incomplete final chunk — discard
          }
        }
      }
    } catch {
      write({ type: "replace", text: "Something went wrong. Please try again." });
    } finally {
      setLoading(false);
      field.current?.focus();
    }
  }

  return (
    <div className="flex flex-1 flex-col min-h-0">
      <div ref={scroller} className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-prose mx-auto px-4 md:px-6 py-6 md:py-10">
          {turns.length === 0 && (
            <div className="pt-6 md:pt-16">
              <h1 className="font-serif text-2xl md:text-4xl font-medium mb-3">Ask the archive</h1>
              <p className="text-ink-dim mb-8 max-w-md">
                Ask about a sighting, a place, a year, or a file in this archive.
              </p>
              <div className="flex flex-col gap-2">
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => handleAsk(example)}
                    className="text-left text-sm text-ink-dim hover:text-ink border border-rule px-3 py-2.5 hover:border-ink-faint transition-colors"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-8">
            {turns.map((turn) => {
              const answer = stripTrailingCitations(turn.answer);
              const sources = answer ? sourcesFor(answer, turn.citations) : [];
              return (
                <div key={turn.id} className="space-y-4">
                  <div className="flex justify-end">
                    <div className="max-w-[90%] sm:max-w-[80%] border border-rule bg-bg-elev px-4 py-3">
                      <p className="text-[10px] font-mono uppercase tracking-tracked text-ink-faint mb-1">You</p>
                      <p className="text-sm md:text-[15px] leading-relaxed">{turn.question}</p>
                    </div>
                  </div>

                  <div>
                    <p className="text-[10px] font-mono uppercase tracking-tracked text-ink-faint mb-2">Archive</p>
                    {answer ? (
                      <div className="font-serif text-[17px] md:text-lg leading-[1.7] text-ink">
                        <AnswerBody text={answer} citations={turn.citations} />
                      </div>
                    ) : (
                      <p className="text-sm text-ink-faint">Reading the records...</p>
                    )}

                    {sources.length > 0 && (
                      <div className="mt-4">
                        <p className="text-[10px] font-mono uppercase tracking-tracked text-ink-faint mb-1">Sources</p>
                        <p className="text-sm text-ink-dim mb-2">Opened from the records used in this answer.</p>
                        <ul className="space-y-1.5">
                          {sources.map((citation) => (
                            <li key={citation.id}>
                              <Link
                                href={citation.href ?? `/incident/${citation.slug ?? citation.id}`}
                                className="text-sm text-accent hover:underline"
                              >
                                {citation.title}
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          handleAsk();
        }}
        className="border-t border-rule bg-bg"
      >
        <div className="max-w-prose mx-auto px-4 md:px-6 py-3">
          <div className="flex items-end gap-2">
            <textarea
              ref={field}
              value={question}
              rows={1}
              onChange={(event) => {
                setQuestion(event.target.value);
                event.target.style.height = "auto";
                event.target.style.height = `${Math.min(event.target.scrollHeight, 128)}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleAsk();
                }
              }}
              placeholder="Ask about a case, a place, or a year"
              disabled={loading}
              className="flex-1 resize-none bg-bg border border-rule focus:border-accent px-3 py-2.5 text-sm text-ink outline-none max-h-32"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="shrink-0 border border-rule px-4 py-2.5 text-sm text-ink hover:border-accent hover:text-accent disabled:opacity-30 transition-colors"
            >
              Ask
            </button>
          </div>
          <p className="mt-2 text-[11px] text-ink-faint">
            Answers stay tied to the released records. Enter sends. Shift+Enter adds a line.
          </p>
        </div>
      </form>
    </div>
  );
}
