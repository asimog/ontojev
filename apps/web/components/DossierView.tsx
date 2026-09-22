"use client";

import { useEffect, useState } from "react";
import { api, apiUrl } from "@/lib/api";

type Section = { availability: string; reason: string | null; narrative: string | null };
type Dossier = { dossier_id: string; warning: string; sections: Record<string, Section> };

export function DossierView({ dossierId }: { dossierId: string }) {
  const [data, setData] = useState<Dossier | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api<Dossier>(`/api/dossiers/${dossierId}`, controller.signal)
      .then((dossier) => {
        setData(dossier);
        setError(null);
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setError("Dossier unavailable");
      });
    return () => controller.abort();
  }, [dossierId]);
  if (error) return <div className="api-warning">{error}</div>;
  if (!data) return <div className="panel empty">Loading dossier…</div>;
  return <article className="dossier"><header className="warning-panel"><span>RESEARCH ONLY · FAKE</span><h1>SYNTHETIC DEMONSTRATION</h1><p>{data.warning}</p><a className="button secondary" href={apiUrl(`/api/dossiers/${dossierId}?format=markdown`)}>Download derived Markdown</a></header>{Object.entries(data.sections).map(([key, section]) => <section className="panel" key={key}><div className="row spread"><h2>{key.replaceAll("_", " ")}</h2><span className="availability">{section.availability}</span></div><p>{section.narrative ?? section.reason}</p></section>)}</article>;
}
