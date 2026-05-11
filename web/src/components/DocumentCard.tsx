import Link from "next/link";
import Image from "next/image";

interface DocumentCardProps {
  document: {
    id: string;
    filename: string;
    url: string;
    cover_image_url: string;
    page_count: number | null;
    agency: string | null;
    incident_slug: string | null;
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
        <span className="absolute top-2 left-2 bg-bg/80 px-2 py-0.5 text-[10px] font-mono uppercase tracking-tracked text-ink-faint border border-rule">
          Document
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

  if (doc.incident_slug) {
    return (
      <Link href={`/incident/${doc.incident_slug}`} className="group block overflow-hidden">
        {inner}
      </Link>
    );
  }

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
