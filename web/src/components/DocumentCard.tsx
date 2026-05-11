import Image from "next/image";

interface DocumentCardProps {
  document: {
    id: string;
    filename: string;
    url: string;
    cover_image_url: string;
    page_count: number | null;
    agency: string | null;
  };
}

function truncateFilename(name: string, max: number = 50): string {
  if (name.length <= max) return name;
  return name.slice(0, max - 3) + "...";
}

export function DocumentCard({ document: doc }: DocumentCardProps) {
  const inner = (
    <>
      <div className="relative overflow-hidden bg-bg-quiet" style={{ height: "280px" }}>
        <Image
          src={doc.cover_image_url}
          alt={`Cover of ${doc.filename}`}
          fill
          sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
          className="object-cover group-hover:scale-[1.02] transition-transform duration-300"
        />
        <span className="absolute top-2 left-2 bg-bg/80 px-2 py-0.5 text-[10px] font-mono uppercase tracking-tracked text-ink-faint border border-rule flex items-center gap-1">
          PDF
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </span>
      </div>
      <div className="mt-2.5">
        <h3 className="font-serif text-sm font-medium leading-snug group-hover:text-accent transition-colors line-clamp-2">
          {truncateFilename(doc.filename)}
        </h3>
        <div className="mt-1 flex items-center gap-3 text-xs text-ink-faint">
          {doc.page_count && <span>{doc.page_count} pages</span>}
          {doc.agency && <span className="font-mono uppercase">{doc.agency}</span>}
        </div>
      </div>
    </>
  );

  return (
    <a
      href={doc.url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block overflow-hidden"
    >
      {inner}
    </a>
  );
}
