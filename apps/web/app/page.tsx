import Link from "next/link";
import { ActiveRunPanel } from "@/components/ActiveRunPanel";
import { RecentDossiers } from "@/components/RecentDossiers";
import { RunFeed } from "@/components/RunFeed";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";

const SPINE = [
  { n: "01", title: "Release-pinned capability", kind: "", body: "Status, one project record and one aggregate open-file facet request derive a typed capability; readiness gates which profile may run autonomously." },
  { n: "02", title: "Mutation discovery", kind: "", body: "The complete release-bound protein-coding universe, distinct-case counting from released occurrences, canonical-transcript composition." },
  { n: "03", title: "Expression discovery", kind: "", body: "Case-labelled UQFPKM summaries and descriptive tails over the full universe with declared RETAIN / DROP / JEV_REVIEW dispositions." },
  { n: "04", title: "CNV shard sweep", kind: "", body: "Independent deterministic case shards over the project occurrence index; the terminal merge requires every shard." },
  { n: "05", title: "Modality union", kind: "", body: "RETAIN and preserved-review nominations compose into one canonical StatisticalState per gene — no parallel state model." },
  { n: "06", title: "Pre-Wide policy", kind: "policy", body: "Measured evidence bounds the Jev population. The full union stays persisted; cuts record explicit reasons; boundary ties fail closed." },
  { n: "07", title: "Wide Jev judgment", kind: "jev", body: "Noul/Choice questions judge coherence and uncertainty over typed projections only. Python policy admits; JEV_REVIEW states are never promotable." },
  { n: "08", title: "Candidate to dossier", kind: "", body: "Deep Jev, registered deterministic follow-ups, immutable EvidenceState revisions, bounded hypotheses and Stage 8 with a no-Jev comparison." },
];

const INVARIANTS = [
  { title: "Jev judges", body: "Semantic questions over bounded typed projections. No measurements, no maturity promotion, no tool selection." },
  { title: "Python decides", body: "Admission, next moves, retention, caps and terminal handling are deterministic code with recorded reasons." },
  { title: "Hypotheses are not evidence", body: "Generated text is labelled, reviewed as an input, and never writes a measured field." },
  { title: "Open access only", body: "Anonymous GDC reads with declared budgets. Missing data stays missing; it is never inferred as negative." },
];

const LEGEND = [
  { title: "Implemented", tone: "violet", body: "Contracts, methods and tests exist in the repository." },
  { title: "Production-wired", tone: "violet", body: "Reachable through normal autonomous Campaign, worker and API execution." },
  { title: "Live-verified", tone: "live", body: "Observed against real open-access GDC responses and real Jev calls." },
  { title: "Scientifically validated", tone: "amber", body: "A profile may run autonomously only after live evidence is reviewed. None is promoted yet." },
  { title: "Deferred", tone: "fake", body: "Arm Jev, added modalities, functional axes and therapeutic interpretation." },
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <div>
          <span className="kicker">Autonomous computational target discovery</span>
          <h1>Evidence first. Jev judges. Python decides.</h1>
          <p className="lede">
            OntoJev runs systematic open-access GDC campaigns: a complete-universe mutation scan,
            independent expression discovery and CNV case shards compose into one canonical
            <span className="mono"> StatisticalState</span>. Jev adds narrow semantic judgment over typed
            projections; deterministic Python policy admits candidates, drives immutable evidence
            revisions, and finalizes every candidate through Stage 8 and a dossier.
          </p>
          <div className="hero-actions">
            <Link className="button" href="/runs">Browse research runs</Link>
            <Link className="button secondary" href="/system">Inspect system posture</Link>
          </div>
        </div>
        <aside className="instrument" aria-label="Campaign invariants">
          <div className="eyebrow">Campaign invariants</div>
          <h3>What this deployment can and cannot claim</h3>
          <dl>
            <div className="instrument-row"><dt>GDC access</dt><dd>Open, anonymous</dd></div>
            <div className="instrument-row"><dt>Discovery universe</dt><dd>Complete gene enumeration</dd></div>
            <div className="instrument-row"><dt>Wide gate</dt><dd>Measured-evidence policy</dd></div>
            <div className="instrument-row"><dt>Candidate path</dt><dd>No operator flag</dd></div>
            <div className="instrument-row"><dt>LUAD profile</dt><dd><span className="badge amber">EXPERIMENTAL</span></dd></div>
          </dl>
          <p className="fine instrument-note">
            Software tests green ≠ scientific validation. Readiness is promoted only after a live
            campaign with real Jev completes and its dossier is reviewed.
          </p>
        </aside>
      </section>

      <SystemStatusPanel />
      <ActiveRunPanel />

      <section aria-labelledby="spine-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Canonical execution spine</span>
            <h2 id="spine-title">How one autonomous campaign runs</h2>
          </div>
          <Link href="/runs">See it in the record →</Link>
        </div>
        <div className="spine">
          {SPINE.map((step) => (
            <article className={`spine-step ${step.kind}`} key={step.n}>
              <span className="n">STEP {step.n}</span>
              <strong>{step.title}</strong>
              <p>{step.body}</p>
            </article>
          ))}
        </div>
      </section>

      <div className="invariants">
        {INVARIANTS.map((item) => (
          <div className="invariant" key={item.title}>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
          </div>
        ))}
      </div>

      <section>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Recent activity</span>
            <h2>Persistent run feed</h2>
          </div>
          <Link href="/runs">View all →</Link>
        </div>
        <RunFeed compact />
      </section>

      <RecentDossiers />

      <section>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Status vocabulary</span>
            <h2>How to read every claim on this site</h2>
          </div>
        </div>
        <div className="status-legend">
          {LEGEND.map((item) => (
            <div className="legend-item" key={item.title}>
              <strong><span className={`status-dot ${item.tone}`} aria-hidden="true" />{item.title}</strong>
              <p>{item.body}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
