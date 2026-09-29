"use client";

import { usePathname } from "next/navigation";
import { HeaderShell } from "./HeaderShell";
import { Footer } from "./Footer";

/** All routes, including error and not-found states, share the same chrome. */
export function SiteFrame({ children, banner }: { children: React.ReactNode; banner: React.ReactNode }) {
  const pathname = usePathname();
  const section = pathname.split("/")[1];
  const active = !section || section === "incidents" || section === "incident"
    ? "archive"
    : section === "source" ? "sources" : section;
  const application = pathname === "/map";

  return (
    <div className={`site-frame flex flex-col min-h-dvh ${application ? "site-frame-app h-dvh overflow-hidden" : ""}`}>
      <HeaderShell active={active} showBanner={pathname === "/"} banner={banner} />
      <div className="flex flex-col flex-1 min-h-0">{children}</div>
      <Footer />
    </div>
  );
}
