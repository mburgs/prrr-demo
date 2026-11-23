import { formatQuota } from "./quota";

export interface TenantRow {
  tenant: string;
  remaining: number;
  capacity: number;
  retryAfterSec?: number;
}

export function renderTenantRow(row: TenantRow): string {
  return `${row.tenant.padEnd(14)} ${formatQuota(row.remaining, row.capacity, row.retryAfterSec)}`;
}

/** Most constrained tenants first; ties broken by name. Does not mutate `rows`. */
export function sortByRemaining(rows: readonly TenantRow[]): TenantRow[] {
  return [...rows].sort(
    (a, b) => a.remaining - b.remaining || a.tenant.localeCompare(b.tenant),
  );
}
