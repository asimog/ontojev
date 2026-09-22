import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = { title: "CancerJEV · Synthetic Research Observatory", description: "Offline Phase 1 execution architecture" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><header className="site-header"><Link href="/" className="brand"><span className="brand-mark">CJ</span><span>CancerJEV<small>Research observatory</small></span></Link><nav><Link href="/runs">Runs</Link><Link href="/dossiers">Dossiers</Link><Link href="/system">System</Link></nav><span className="phase">PHASE 1 · OFFLINE</span></header><main>{children}</main><footer>Fake execution architecture · zero GDC, Jev, or LLM research-provider calls</footer></body></html>;
}

