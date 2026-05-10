export default function MapLoading() {
  return (
    <div className="flex items-center justify-center bg-bg" style={{ height: "calc(100vh - 96px)" }}>
      <p className="font-mono text-sm text-ink-faint animate-pulse">
        Loading map...
      </p>
    </div>
  );
}
