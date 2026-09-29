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

/** Must match keys in web/src/lib/rag/example-cache.json */
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

// Keep source selection based on the original answer; simplify only its display.
function answerText(text: string, citations: Citation[]): string {
  const caseIds = new Set(citations.map((citation) => citation.case_id.toUpperCase()));
  return stripTrailingCitations(text)
    .replace(/\[([^\]]+)\]\([^\s)]+\)/g, (_, label: string) =>
      caseIds.has(label.toUpperCase()) || /^\d{4}-[A-Za-z]+-[A-Za-z0-9-]+$/.test(label) ? "" : label
    )
    .replace(/\[([A-Za-z0-9-]+)\]/g, (marker, id: string) =>
      caseIds.has(id.toUpperCase()) || /^\d{4}-[A-Za-z]+-[A-Za-z0-9-]+$/.test(id) ? "" : marker
    )
    .replace(/[ \t]+([.,;:!?])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function AnswerBody({ text, citations }: { text: string; citations: Citation[] }) {
  const blocks = answerText(text, citations).split(/\n{2,}/).filter((block) => block.trim());

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
                  {line.replace(/^(?:[-*]|\d+[.)])\s+/, "")}
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
                {line}
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
  const latestTurn = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    latestTurn.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [turns.length]);

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

    let receivedText = false;
    const write = (payload: { type?: string; text?: string; citations?: Citation[]; slug?: string }) => {
      if (payload.text?.trim()) receivedText = true;
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
      if (!receivedText) write({ type: "replace", text: "No answer was returned. Please try again." });
    } catch {
      write({ type: "replace", text: "Something went wrong. Please try again." });
    } finally {
      setLoading(false);
      field.current?.focus();
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-3">
        <h1 className="font-serif text-2xl md:text-4xl font-medium">Ask the archive</h1>
        {turns.length > 0 && <button type="button" disabled={loading} onClick={() => { setTurns([]); setQuestion(""); field.current?.focus(); }} className="shrink-0 text-sm text-ink-dim hover:text-ink underline underline-offset-4 disabled:opacity-40 disabled:cursor-not-allowed">New chat</button>}
      </div>
      <p className="text-ink-dim mb-8 max-w-prose">
        Ask about a sighting, a place, a year, or a file in this archive.
      </p>
      <section aria-label="Archive chat">
        <div className="space-y-8">
          {turns.length === 0 && (
            <div className="py-4">
              <h2 className="font-serif text-xl mb-4">What would you like to explore?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" onClick={() => handleAsk(example)} className="text-left text-sm lg:text-base text-ink-dim hover:text-ink border border-rule rounded-lg px-4 py-3 hover:bg-bg-elev hover:border-ink-faint transition-colors">{example}<span aria-hidden="true" className="text-accent ml-2">↗</span></button>
                ))}
              </div>
            </div>
          )}
          {turns.map((turn, index) => {
            const answer = stripTrailingCitations(turn.answer);
            const sources = answer ? sourcesFor(answer, turn.citations) : [];
            const answering = loading && index === turns.length - 1;
            return (
              <div key={turn.id} ref={index === turns.length - 1 ? latestTurn : undefined} className="space-y-5 scroll-mt-40">
                <div className="flex justify-end">
                  <div className="max-w-[90%] md:max-w-[75%] rounded-2xl rounded-tr-sm bg-bg-quiet px-4 py-3 md:px-5 [overflow-wrap:anywhere]">
                    <p className="text-xs font-medium text-ink-dim mb-1">You</p>
                    <p className="text-base leading-relaxed whitespace-pre-wrap">{turn.question}</p>
                  </div>
                </div>
                <div className="max-w-[95%] md:max-w-[85%] rounded-2xl rounded-tl-sm border border-rule px-4 py-4 md:px-5 [overflow-wrap:anywhere]">
                  <p className="text-xs font-medium text-ink-dim mb-3">Archive assistant</p>
                  {answer && <div className="reading-column text-base leading-relaxed text-ink"><AnswerBody text={answer} citations={turn.citations} /></div>}
                  {answering && (
                    <div role="status" className={`flex items-center gap-2.5 text-sm text-ink-dim ${answer ? "mt-4" : ""}`}>
                      <span aria-hidden="true" className="h-4 w-4 rounded-full border-2 border-rule border-t-accent motion-safe:animate-spin" />
                      <span>{answer ? "Writing answer…" : "Searching the archive…"}</span>
                    </div>
                  )}
                  {sources.length > 0 && (
                    <div className="mt-5 pt-4 border-t border-rule">
                      <p className="text-xs font-medium text-ink-dim mb-2">Source records</p>
                      <ul className="space-y-2">{sources.map((citation) => (
                        <li key={citation.id}><Link href={citation.href ?? `/incident/${citation.slug ?? citation.id}`} className="text-sm text-accent hover:underline">{citation.title} ↗</Link></li>
                      ))}</ul>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          handleAsk();
        }}
        className="mt-8"
      >
        <div>
          <label htmlFor="archive-question" className="sr-only">Your message</label>
          <div className="flex items-end gap-2 rounded-lg border border-rule bg-bg p-2 focus-within:border-accent">
            <textarea
              ref={field}
              id="archive-question"
              value={question}
              rows={1}
              onChange={(event) => {
                setQuestion(event.target.value);
                event.target.style.height = "auto";
                event.target.style.height = `${Math.min(event.target.scrollHeight, 128)}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  handleAsk();
                }
              }}
              placeholder="Ask about a case, a place, or a year"
              disabled={loading}
              className="min-w-0 flex-1 resize-none bg-bg px-2 py-2 text-sm lg:text-base text-ink outline-none max-h-32"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="shrink-0 rounded-md bg-ink text-bg px-4 py-2 text-sm lg:text-base font-medium hover:opacity-80 disabled:opacity-30 disabled:cursor-not-allowed transition-opacity"
            >
              Send
            </button>
          </div>
          <p className="mt-2 text-[11px] lg:text-xs text-ink-faint">
            Answers stay tied to the released records. Enter sends. Shift+Enter adds a line.
          </p>
        </div>
      </form>
      </section>
    </div>
  );
}
