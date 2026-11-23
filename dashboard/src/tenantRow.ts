import { formatRemaining } from "./quota";

export interface TenantRow {
  tenant: string;
  remaining: number;
  capacity: number;
}

export function renderTenantRow(row: TenantRow): string {
  return `${row.tenant.padEnd(14)} ${formatRemaining(row.remaining, row.capacity)}`;
}
