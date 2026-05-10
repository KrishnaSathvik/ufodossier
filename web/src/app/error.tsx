"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen bg-bg flex flex-col items-center justify-center px-4 text-center">
      <span className="font-mono text-xs uppercase tracking-tracked text-critical border border-critical px-3 py-1 mb-6 inline-block transform -rotate-2">
        System fault
      </span>
      <h1 className="font-serif text-2xl md:text-4xl font-medium mb-4 text-ink">
        Something went wrong
      </h1>
      <p className="text-ink-dim mb-8 max-w-md">
        An unexpected error occurred while loading this page. The archive remains intact.
      </p>
      <button
        onClick={reset}
        className="px-5 py-2 border border-rule text-sm font-medium text-ink hover:border-ink-faint transition-colors"
      >
        Try again
      </button>
      {error.digest && (
        <p className="mt-6 text-xs font-mono text-ink-faint">
          Ref: {error.digest}
        </p>
      )}
    </div>
  );
}
