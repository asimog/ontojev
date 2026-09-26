import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: "OntoJev · autonomous target discovery observatory",
  description:
    "Open-access GDC evidence, deterministic computational genomics, and bounded Jev semantic judgment over one canonical research record.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <SiteHeader />
        <main>{children}</main>
        <footer className="site-footer">
          <div className="footer-grid">
            <div>
              <h3>Claim boundary</h3>
              <p>
                A computational target candidate is not an experimentally validated, therapeutically
                validated, or clinical target. Functional and external axes are deferred with their
                access reasons.
              </p>
              <p>
                Synthetic demonstration runs are labelled <strong>FAKE</strong> and make zero provider
                calls.
              </p>
            </div>
            <div>
              <h3>Control rule</h3>
              <p>Jev judges. Python decides. Python executes.</p>
              <p>Hypotheses are never evidence. Missing is not negative. Universe is not a shard.</p>
            </div>
            <div>
              <h3>Sources and record</h3>
              <p>Open-access GDC only · anonymous · no credentials.</p>
              <p><Link href="/system">System posture</Link> · <Link href="/runs">Canonical run history</Link></p>
            </div>
          </div>
          <div className="footer-base">
            <span>OntoJev · cancerjev engine</span>
            <span>Evidence is immutable; every run is one canonical event stream.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
