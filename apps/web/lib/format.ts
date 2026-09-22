export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString();
}

export function formatDuration(startIso: string | null | undefined, endIso: string | null | undefined): string {
  if (!startIso) return "—";
  const milliseconds = Math.max(0, new Date(endIso ?? Date.now()).getTime() - new Date(startIso).getTime());
  const seconds = Math.floor(milliseconds / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value == null) return "unknown";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MiB`;
}

export function formatCount(value: number | null | undefined): string {
  return value == null ? "unknown" : String(value);
}

export function formatCost(value: number | null | undefined): string {
  return value == null ? "unknown" : `$${value.toFixed(2)}`;
}

export function formatLabel(value: string): string {
  return value.replaceAll("_", " ");
}
