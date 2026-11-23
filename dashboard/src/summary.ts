import { formatQuota } from "./quota";
import { sortByRemaining, type TenantRow } from "./tenantRow";

export function summarize(rows: TenantRow[]): string {
  const remaining = rows.reduce((sum, r) => sum + r.remaining, 0);
  const capacity = rows.reduce((sum, r) => sum + r.capacity, 0);
  const [tightest] = sortByRemaining(rows);
  const tail = tightest ? `; tightest: ${tightest.tenant}` : "";
  return `${rows.length} tenants, pool ${formatQuota(remaining, capacity)}${tail}`;
}
