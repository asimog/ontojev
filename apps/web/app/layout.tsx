import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = { title: "CancerJEV · Research Observatory", description: "Open-access GDC evidence with deterministic science and Jev semantic judgment" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><header className="site-header"><Link href="/" className="brand"><span className="brand-mark">CJ</span><span>CancerJEV<small>Research observatory</small></span></Link><nav><Link href="/runs">Runs</Link><Link href="/dossiers">Dossiers</Link><Link href="/system">System</Link></nav><span className="phase">PHASE 3 · OPEN GDC + JEV</span></header><main>{children}</main><footer>Open-access GDC only · deterministic measurements · Jev semantic judgment · no LLM hypotheses</footer></body></html>;
}

