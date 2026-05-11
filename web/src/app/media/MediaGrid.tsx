"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useCallback } from "react";
import { TabToggle } from "@/components/TabToggle";
import { MediaCard } from "@/components/MediaCard";
import { VideoCard } from "@/components/VideoCard";
import { DocumentCard } from "@/components/DocumentCard";

function MediaGridInner({ images, videos, documents }: { images: any[]; videos: any[]; documents: any[] }) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const rawTab = searchParams.get("tab");
  const tab = rawTab === "videos" ? "videos" : rawTab === "documents" ? "documents" : "images";

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

      {tab === "images" ? (
        images.length === 0 ? (
          <p className="py-12 text-center text-ink-faint">
            No images available yet. Source media is linked as the pipeline processes documents.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {images.map((item: any) => (
              <MediaCard key={item.id} incident={item} type="image" />
            ))}
          </div>
        )
      ) : tab === "videos" ? (
        videos.length === 0 ? (
          <p className="py-12 text-center text-ink-faint">
            No videos available yet. Source media is linked as the pipeline processes documents.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {videos.map((item: any) => (
              <VideoCard key={item.id} video={item} />
            ))}
          </div>
        )
      ) : (
        documents.length === 0 ? (
          <p className="py-12 text-center text-ink-faint">
            No document covers available yet. Covers are rendered as the pipeline processes PDFs.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {documents.map((doc: any) => (
              <DocumentCard key={doc.id} document={doc} />
            ))}
          </div>
        )
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
