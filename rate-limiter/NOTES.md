
# Design Notes

Extended notes on approach, tradeoffs, and next steps — kept separate from
the README so the README itself stays to the requested 3–6 sentences.

## Approach & tradeoffs

I implemented an **exact sliding window** (a per-key log of request
timestamps, trimmed to the trailing `window_seconds` on every call) rather
than a fixed-bucket counter, because fixed buckets let a client double
their effective rate by clustering requests around a bucket boundary. The
tradeoff is O(N) memory per key for the requests currently in-window,
versus O(1) for a fixed-window counter — acceptable for typical API
rate limits (tens to low-hundreds of requests per window).

As a bonus, I added a **token bucket** behind the same `RateLimiter`
interface, since it's a genuinely different tradeoff: it permits bursts up
to the bucket capacity while still enforcing a long-run average rate, which
suits traffic that's naturally bursty (e.g. a client polling then catching
up). Both policies share the same `Clock` abstraction so tests are
deterministic — time never actually elapses in a test, it's advanced
explicitly via `FakeClock.advance()`.

**Concurrency**: both limiters guard their internal state with a single
`threading.Lock`. That's correct and simple, and fine for the expected
load of an internal API gate, but it does serialize all `allow()` calls
across *every* key. Under heavy multi-core contention I'd move to one lock
per key (e.g. a `key -> Lock` map, itself guarded briefly during creation)
so unrelated keys stop contending with each other — I didn't do that here
to keep the implementation easy to reason about, since correctness was the
higher priority for this exercise.

**Idle-key cleanup**: each limiter opportunistically evicts keys that have
had no activity for `idle_ttl_seconds` (default: 10x the window), so a
service that sees many one-off or short-lived keys (e.g. anonymous
session IDs) doesn't leak memory forever. Cleanup runs at most once per
`idle_ttl_seconds`, not on every call, to keep steady-state overhead O(1).

## What would change under a distributed backend

The exercise asks for in-memory only, but structured for a future swap.
The `allow(key)` interface is intentionally the *only* thing callers
depend on — internally, a Redis-backed implementation would:

- Store each key's request log as a Redis **sorted set** (score = timestamp),
  with `ZREMRANGEBYSCORE` to trim expired entries, `ZCARD` to count, and
  `ZADD` to record — wrapped in a Lua script (or `MULTI`/`EXEC`) so the
  trim-count-add sequence is atomic across replicas, replacing the
  in-process lock.
- Or, for the token bucket, use `INCRBY`/`SET` with a TTL and do the refill
  math in a Lua script for the same atomicity guarantee.
- Rely on Redis's own TTL/eviction instead of the manual idle-key cleanup
  here.
- Need to consider clock skew across app servers (Redis's own server time,
  via `TIME`, sidesteps this) and the added network round-trip latency
  per `allow()` call, which single-process in-memory doesn't have.

## What I'd do next with more time

- Per-key locks (see above) for better concurrency under contention.
- A background cleanup thread instead of piggy-backing cleanup on
  `allow()` calls, so cleanup timing isn't coupled to traffic patterns.
- Return richer info than a bool (e.g. remaining quota, retry-after
  seconds) so callers can set proper `Retry-After` / `X-RateLimit-*`
  response headers.
- Property-based tests (e.g. Hypothesis) to fuzz sequences of
  allow()/advance() calls and assert the allowed count never exceeds the
  configured limit in any window, as a complement to the example-based
  tests here.
