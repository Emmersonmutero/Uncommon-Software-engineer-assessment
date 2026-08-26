# Uncommon Software Engineer Instructor Assessment

## Overview

This repository contains the two parts of the assessment: a per-key in-memory rate limiter and a system design for a large-scale notification service.

## Repository Structure

```text
.
├── .gitignore
├── README.md
├── pyproject.toml
├── requirements-dev.txt
├── rate-limiter/
│   ├── README.md
│   ├── pyproject.toml
│   ├── example.py
│   ├── NOTES.md
│   ├── ratelimiter/
│   │   ├── __init__.py
│   │   ├── clock.py
│   │   ├── interfaces.py
│   │   ├── sliding_window.py
│   │   └── token_bucket.py
│   └── tests/
│       ├── test_concurrency.py
│       ├── test_sliding_window.py
│       └── test_token_bucket.py
└── system-design/
    ├── DESIGN.md
    ├── architecture.dot
    └── architecture.png
```

## Part 1 — Rate Limiter

The rate limiter keeps per-client state in memory, exposes a simple `allow(key) -> bool` interface, and supports both a sliding-window policy and an interchangeable token-bucket policy behind the same API.

## Running the Project

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Running Tests

```bash
pytest -q
```

## Part 2 — Notification Service

The system design is in `system-design/DESIGN.md`, and the architecture diagram is in `system-design/architecture.dot` with the rendered PNG in `system-design/architecture.png`.

## Technical Decisions

- Sliding-window enforcement avoids the common fixed-window boundary bug by checking the actual rolling time window.
- The limiter stores state in memory only and keeps the interface simple so a distributed backend could be introduced later without changing caller code.
- The notification design uses separate transactional and bulk queues, durable idempotency, and provider-level retry/failover to keep time-sensitive traffic reliable even under spikes.
