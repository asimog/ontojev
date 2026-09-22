import Link from "next/link";
import { RunFeed } from "@/components/RunFeed";

export default function Home() { return <><section className="hero"><div><span className="kicker">OFFLINE EXECUTION PROOF</span><h1>Watch a research run become a durable record.</h1><p>A deterministic synthetic process publishes one canonical event stream, immutable evidence revisions, narrow Jev-shaped judgments, competing fixture hypotheses, and a dossier.</p><div className="row"><Link className="button" href="/runs">Open research runs</Link><Link className="button secondary" href="/system">Inspect system</Link></div></div><div className="orb"><span>0</span><small>external<br />provider calls</small></div></section><section><div className="section-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>Persistent run feed</h2></div><Link href="/runs">View all →</Link></div><RunFeed compact /></section></>; }

