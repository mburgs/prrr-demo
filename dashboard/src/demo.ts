import { summarize } from "./summary";
import { renderTenantRow, sortByRemaining, type TenantRow } from "./tenantRow";

const rows: TenantRow[] = [
  { tenant: "tenant-red", remaining: 2.6, capacity: 5 },
  { tenant: "tenant-blue", remaining: 5, capacity: 5 },
  { tenant: "tenant-green", remaining: 0, capacity: 5, retryAfterSec: 1.2 },
];

for (const row of sortByRemaining(rows)) {
  console.log(renderTenantRow(row));
}
console.log(summarize(rows));
