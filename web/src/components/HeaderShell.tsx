import { StatusBanner } from "./StatusBanner";
import { TopBarNav } from "./TopBar";

export function HeaderShell({
  active = "archive",
  showBanner = false,
}: {
  active?: string;
  showBanner?: boolean;
}) {
  return (
    <>
      <header className="fixed top-0 left-0 right-0 bg-bg z-50 border-b border-rule">
        <TopBarNav active={active} />
        {showBanner ? <StatusBanner /> : null}
      </header>
      <div className={showBanner ? "h-[7.5rem] sm:h-[5.5rem]" : "h-[5.5rem] sm:h-14"} />
    </>
  );
}
