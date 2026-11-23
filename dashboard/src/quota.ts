/**
 * Human-readable quota, e.g. "7/10 (70%)". When the quota is exhausted and the
 * server told us how long to wait, appends ", retry in 3s".
 */
export function formatQuota(
  remaining: number,
  capacity: number,
  retryAfterSec?: number,
): string {
  if (capacity <= 0) {
    return "n/a";
  }
  const whole = Math.max(0, Math.floor(remaining));
  const pct = Math.round((whole / capacity) * 100);
  const base = `${whole}/${capacity} (${pct}%)`;
  if (whole === 0 && retryAfterSec !== undefined) {
    return `${base}, retry in ${Math.ceil(retryAfterSec)}s`;
  }
  return base;
}
