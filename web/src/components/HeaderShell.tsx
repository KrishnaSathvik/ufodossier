import { TopBarNav } from "./TopBar";

export function HeaderShell({
  active = "archive",
  showBanner = false,
  banner,
}: {
  active?: string;
  showBanner?: boolean;
  banner?: React.ReactNode;
}) {
  return (
    <>
      <header className="sticky top-0 shrink-0 bg-bg z-50 border-b border-rule">
        <TopBarNav active={active} />
        {showBanner ? banner : null}
      </header>
    </>
  );
}
