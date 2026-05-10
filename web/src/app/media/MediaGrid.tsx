"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useCallback } from "react";
import { TabToggle } from "@/components/TabToggle";
import { MediaCard } from "@/components/MediaCard";

function MediaGridInner({ images, videos, documents }: { images: any[]; videos: any[]; documents: any[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const rawTab = searchParams.get("tab");
  const tab = rawTab === "videos" ? "videos" : rawTab === "documents" ? "documents" : "images";
  const items = tab === "videos" ? videos : tab === "documents" ? documents : images;

  const setTab = useCallback(
    (value: string) => {
      router.push(`/media?tab=${value}`, { scroll: false });
    },
    [router],
  );

  return (
    <>
      <div className="mb-8">
        <TabToggle
          tabs={[
            { value: "images", label: "Images", count: images.length },
            { value: "videos", label: "Videos", count: videos.length },
            { value: "documents", label: "Documents", count: documents.length },
          ]}
          active={tab}
          onChange={setTab}
        />
      </div>

      {items.length === 0 ? (
        <p className="py-12 text-center text-ink-faint">
          No {tab} available yet. Source media is linked as the pipeline processes documents.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map((item: any) => (
            <MediaCard
              key={item.id}
              incident={item}
              type={tab === "videos" ? "video" : tab === "documents" ? "document" : "image"}
            />
          ))}
        </div>
      )}
    </>
  );
}

export function MediaGrid({ images, videos, documents }: { images: any[]; videos: any[]; documents: any[] }) {
  return (
    <Suspense fallback={<div className="py-12 text-center text-ink-faint">Loading...</div>}>
      <MediaGridInner images={images} videos={videos} documents={documents} />
    </Suspense>
  );
}
