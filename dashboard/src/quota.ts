/** Human-readable remaining quota, e.g. "7/10 (70%)". */
export function formatRemaining(remaining: number, capacity: number): string {
  if (capacity <= 0) {
    return "n/a";
  }
  const whole = Math.max(0, Math.floor(remaining));
  const pct = Math.round((whole / capacity) * 100);
  return `${whole}/${capacity} (${pct}%)`;
}
