# hookrelay

A tiny multi-tenant webhook relay. It signs outgoing events with HMAC-SHA256,
delivers them through a pluggable transport, and retries failures.

This repository is a synthetic demo project: there is no real network access
and every URL points at `example.com`.

## Layout

- `hookrelay/` - Python 3.11+ package, standard library only.
  - `ratelimit/bucket.py` - token bucket limiter.
  - `ratelimit/registry.py` - per-tenant buckets with an LRU cap.
  - `webhooks/signing.py` - timestamped HMAC signing and verification.
  - `webhooks/dispatcher.py` - delivery with backoff, jitter and rate limits.
  - `cli.py` - `python -m hookrelay` simulates a few deliveries.
- `dashboard/` - TypeScript helpers that format quota information.
- `tests/` - pytest suite.

## Rate limits

Every event is checked against two limits before it is sent:

1. **Per tenant** - each tenant gets its own token bucket, sized by
   `tenant_capacity` (burst) and `tenant_refill_per_sec` (sustained rate).
   At most `max_tenants` buckets are kept; the least recently used tenant is
   evicted first and starts with a full bucket if it returns.
2. **Global** - `bucket_capacity` / `bucket_refill_per_sec` cap the relay as a
   whole.

A refused event is not sent. Its `DeliveryResult` has `reason` set to
`tenant_rate_limited` or `rate_limited` and `retry_after` set to the number of
seconds until it would be accepted.

Failed deliveries are retried up to `max_attempts` times, but only for 5xx
responses, 429, and transport errors. The delay starts at `retry_delay_sec`,
doubles each time up to `retry_max_delay_sec`, and gets up to
`retry_jitter_sec` of random jitter. A numeric `Retry-After` header on a
retryable response overrides the computed delay.

Signatures are now `t=<unix seconds>,v1=<hex>` and are rejected outside a
five-minute window. Bare hex signatures are still accepted by `verify` for one
release.

## Running

```
python -m pytest -q
python -m hookrelay
npm install && npm run typecheck
npx tsx dashboard/src/demo.ts
```
