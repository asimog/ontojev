const API_URL = process.env.NEXT_PUBLIC_CANCERJEV_API_URL ?? "http://127.0.0.1:8000";

export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json() as Promise<T>;
}

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

