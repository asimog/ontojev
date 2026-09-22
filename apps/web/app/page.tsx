import Link from "next/link";
import { ActiveRunPanel } from "@/components/ActiveRunPanel";
import { RecentDossiers } from "@/components/RecentDossiers";
import { RunFeed } from "@/components/RunFeed";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";

export default function Home() {
  return (
    <>
      <section className="hero"><div><span className="kicker">OPEN GDC → DETERMINISTIC SCIENCE → JEV</span><h1>Watch a research run become a durable record.</h1><p>A bounded, anonymous, open-access GDC sweep produces deterministic StatisticalStates; Jev adds narrow semantic judgments; Python policy ranks and admits candidates. Every run is one canonical event stream with immutable artifacts.</p><div className="row"><Link className="button" href="/runs">Open research runs</Link><Link className="button secondary" href="/system">Inspect system</Link></div></div><div className="orb"><span>0</span><small>LLM<br />hypotheses</small></div></section>
      <SystemStatusPanel />
      <ActiveRunPanel />
      <section><div className="section-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>Persistent run feed</h2></div><Link href="/runs">View all →</Link></div><RunFeed compact /></section>
      <RecentDossiers />
    </>
  );
}
