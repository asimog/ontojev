type Vector = {
  noul?: { probability?: number; semantic_label?: string };
  choice?: { question_id?: string; chosen?: string; distribution?: Record<string, number>; confidence?: number };
  score?: { selected?: number; expected?: number; distribution?: Record<string, number>; confidence?: number; legend?: Record<string, string> };
};

export function JudgmentVector({ vector }: { vector: Vector }) {
  return (
    <section className="judgment" data-testid="judgment-vector">
      <div className="eyebrow violet">JEV JUDGMENT · FIXTURE RESPONSE</div>
      <div className="judgment-grid">
        {vector.noul && <article><span>Noul semantic probability</span><strong>{percent(vector.noul.probability)}</strong><small>{vector.noul.semantic_label}</small></article>}
        {vector.choice && <article><span>Choice</span><strong>{vector.choice.chosen}</strong><Distribution values={vector.choice.distribution} /><small>model confidence {percent(vector.choice.confidence)}</small></article>}
        {vector.score && <article><span>Score</span><strong>{vector.score.selected} / 4</strong><Distribution values={vector.score.distribution} /><small>model confidence {percent(vector.score.confidence)} · expected {vector.score.expected ?? "—"} · {scoreLegend(vector.score)}</small></article>}
      </div>
      <p className="fine">Semantic model output—not statistical significance, a p-value, or scientific confidence.</p>
    </section>
  );
}

function scoreLegend(score: NonNullable<Vector["score"]>): string {
  const selected = score.selected == null ? undefined : String(score.selected);
  return (selected ? score.legend?.[selected] : undefined) ?? "fixture 0..4 follow-up-value rubric";
}

function Distribution({ values }: { values?: Record<string, number> }) {
  if (!values) return null;
  return <div className="distribution">{Object.entries(values).map(([key, value]) => <span key={key}>{key} {percent(value)}</span>)}</div>;
}

function percent(value?: number) { return value == null ? "—" : `${Math.round(value * 100)}%`; }
