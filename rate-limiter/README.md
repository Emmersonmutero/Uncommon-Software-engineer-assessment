# In-Memory Rate Limiter

The sliding-window limiter keeps a per-key deque of timestamps and removes anything older than the active window before checking quota, so the limit is enforced against the real rolling window instead of a fixed bucket boundary. The main tradeoff is simplicity and correctness versus throughput under contention: a single lock keeps the implementation safe and predictable, but it serializes requests across keys during heavy concurrency. The injectable `Clock` and `FakeClock` keep tests deterministic without depending on real time. With more time, the next step would be per-key locking, clearer retry-after metadata, and a cleaner cleanup strategy for long-lived deployments.

## Usage

```python
from ratelimiter import SlidingWindowLimiter

limiter = SlidingWindowLimiter(max_requests=100, window_seconds=60)

if limiter.allow("client-42"):
    handle_request()
else:
    return_429()
```

Run the demo with `python example.py`.
