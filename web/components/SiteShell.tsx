import { SiteFooter } from "./SiteFooter";
import { PublicDemoNotice } from "./PublicDemoNotice";
import { SiteHeader } from "./SiteHeader";

export function SiteShell({ children }: { children: React.ReactNode }) {
  return <><SiteHeader /><PublicDemoNotice /><main>{children}</main><SiteFooter /></>;
}

