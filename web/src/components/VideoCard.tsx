"use client";

import { useState } from "react";

interface VideoCardProps {
  video: {
    id: string;
    filename: string;
    url: string;
    embed_url: string;
    thumbnail_url: string | null;
    agency: string | null;
    blurb: string | null;
  };
}

function formatTitle(filename: string): string {
  if (filename.length <= 60) return filename;
  return filename.slice(0, 57) + "...";
}

export function VideoCard({ video }: VideoCardProps) {
  const [playing, setPlaying] = useState(false);

  return (
    <div className="group block overflow-hidden">
      <div className="aspect-video bg-bg-quiet relative overflow-hidden border border-rule">
        {playing ? (
          <iframe
            src={video.embed_url}
            title={video.filename}
            allow="autoplay; fullscreen"
            allowFullScreen
            className="w-full h-full border-0"
          />
        ) : (
          <button
            onClick={() => setPlaying(true)}
            className="w-full h-full relative cursor-pointer bg-[#111]"
          >
            {video.thumbnail_url && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={video.thumbnail_url}
                alt=""
                className="absolute inset-0 w-full h-full object-cover"
              />
            )}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-14 h-14 rounded-full bg-ink/50 flex items-center justify-center group-hover:bg-accent/80 transition-colors">
                <svg
                  className="text-bg ml-0.5"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
            </div>
            {video.agency && (
              <span className="absolute top-2 left-2 bg-bg/80 px-2 py-0.5 text-[10px] font-mono uppercase tracking-tracked text-ink-faint border border-rule">
                {video.agency}
              </span>
            )}
          </button>
        )}
      </div>
      <div className="mt-2.5">
        <h3 className="font-serif text-sm font-medium leading-snug group-hover:text-accent transition-colors line-clamp-2">
          {formatTitle(video.filename)}
        </h3>
        {video.blurb && (
          <p className="mt-1 text-xs text-ink-faint line-clamp-2 leading-relaxed">
            {video.blurb}
          </p>
        )}
      </div>
    </div>
  );
}
