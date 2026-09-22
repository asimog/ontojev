export function StatusBanner({ error, updatedAt }: { error: string | null; updatedAt: string | null }) {
  if (!error) return null;
  return <div className="api-warning">API unavailable / last updated {updatedAt ? new Date(updatedAt).toLocaleTimeString() : "never"}. Retaining last-good data.</div>;
}

