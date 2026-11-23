# hookrelay

A tiny multi-tenant webhook relay. It signs outgoing events with HMAC-SHA256,
delivers them through a pluggable transport, and retries failures.

This repository is a synthetic demo project: there is no real network access
and every URL points at `example.com`.

## Layout

- `hookrelay/` - Python 3.11+ package, standard library only.
  - `ratelimit/bucket.py` - token bucket limiter.
  - `webhooks/signing.py` - HMAC signing and verification.
  - `webhooks/dispatcher.py` - delivery with retries.
  - `cli.py` - `python -m hookrelay` simulates a few deliveries.
- `dashboard/` - TypeScript helpers that format quota information.
- `tests/` - pytest suite.

## Running

```
python -m pytest -q
python -m hookrelay
npm install && npm run typecheck
npx tsx dashboard/src/demo.ts
```
