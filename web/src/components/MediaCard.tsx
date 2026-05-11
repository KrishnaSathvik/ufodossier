import Link from "next/link";
import Image from "next/image";

interface MediaCardProps {
  incident: any;
  type: "image" | "video" | "document";
}

export function MediaCard({ incident, type }: MediaCardProps) {
  const href = incident.slug ? `/incident/${incident.slug}` : null;

  const content = (
    <>
      <div className="aspect-video bg-bg-quiet relative overflow-hidden">
        {type === "image" && incident.image_url ? (
          <Image
            src={incident.image_url}
            alt={incident.title}
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            className="object-cover group-hover:scale-[1.02] transition-transform duration-300"
          />
        ) : type === "video" ? (
          <>
            {incident.image_url ? (
              <Image
                src={incident.image_url}
                alt={incident.title}
                fill
                sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                className="object-cover group-hover:scale-[1.02] transition-transform duration-300"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-bg-quiet" />
            )}
            {/* Play icon overlay */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-12 h-12 rounded-full bg-ink/60 flex items-center justify-center group-hover:bg-accent/80 transition-colors">
                <svg className="text-bg ml-0.5" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
            </div>
            {incident.source_duration_seconds && (
              <span className="absolute bottom-2 right-2 bg-ink/80 text-bg text-xs font-mono px-1.5 py-0.5">
                {Math.floor(incident.source_duration_seconds / 60)}:{String(incident.source_duration_seconds % 60).padStart(2, "0")}
              </span>
            )}
          </>
        ) : type === "document" && incident.cover_image_url ? (
          <div className="w-full h-full relative">
            <Image
              src={incident.cover_image_url}
              alt={incident.title}
              fill
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
              className="object-cover opacity-70"
            />
            <div className="absolute inset-0 bg-bg/30" />
            <span className="absolute bottom-2 left-2 text-[10px] font-mono uppercase tracking-tracked text-ink-faint bg-bg/80 px-1.5 py-0.5 border border-rule">
              Document
            </span>
          </div>
        ) : null}
      </div>
      <div className="mt-2.5">
        <h3 className="font-serif text-sm font-medium leading-snug group-hover:text-accent transition-colors line-clamp-2">
          {incident.title}
        </h3>
        <div className="mt-1 flex items-center gap-3 text-xs text-ink-faint">
          <span>{incident.occurred_at ?? "Undated"}</span>
          {incident.branch && <span className="font-mono uppercase">{incident.branch}</span>}
        </div>
      </div>
    </>
  );

  if (href) {
    return (
      <Link href={href} className="group block overflow-hidden">
        {content}
      </Link>
    );
  }

  return <div className="group block overflow-hidden">{content}</div>;
}
