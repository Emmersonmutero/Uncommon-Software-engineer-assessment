"""Tiny runnable demo: `python example.py`"""

from ratelimiter import SlidingWindowLimiter, TokenBucketLimiter


def demo(limiter, label):
    print(f"\n-- {label} --")
    for i in range(6):
        decision = "ALLOWED" if limiter.allow("client-42") else "THROTTLED"
        print(f"request {i + 1}: {decision}")


if __name__ == "__main__":
    demo(SlidingWindowLimiter(max_requests=3, window_seconds=5), "Sliding window (3 req / 5s)")
    demo(TokenBucketLimiter(capacity=3, refill_rate=0.5), "Token bucket (burst 3, refill 0.5/s)")
