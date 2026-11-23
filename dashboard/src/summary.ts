import { formatRemaining } from "./quota";
import type { TenantRow } from "./tenantRow";

export function summarize(rows: TenantRow[]): string {
  const remaining = rows.reduce((sum, r) => sum + r.remaining, 0);
  const capacity = rows.reduce((sum, r) => sum + r.capacity, 0);
  return `${rows.length} tenants, pool ${formatRemaining(remaining, capacity)}`;
}
