export function chainCursor(loadedCursor: string | null | undefined, firstPageCursor: string | null | undefined): string | null {
  return loadedCursor !== undefined ? loadedCursor : firstPageCursor ?? null;
}

export function mergeUniqueById<T>(first: T[], extra: T[], key: (item: T) => string): T[] {
  const seen = new Set(first.map(key));
  return [...first, ...extra.filter((item) => !seen.has(key(item)))];
}
