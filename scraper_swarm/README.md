Scraper Swarm
===============

This folder contains a small, polite scraper swarm scaffold used to run market sweeps for a catalog item.

Files:
- `targets.json` - list of marketplace endpoints (templates) to query.
- `worker.py` - an async worker that fetches a URL and extracts simple price-like tokens.
- `swarm.py` - orchestrates many concurrent requests with rate limiting and retries.
- `run_swarm.py` - CLI wrapper to run a sweep and save results.

Usage example:

python3 scraper_swarm/run_swarm.py --query "Mock Industrial Part" --workers 5 --out static/uploads/market_sweep.json

Note: Be responsible when running against real marketplaces. Respect `robots.txt` and rate limits, and ensure you have permission to scrape the targets.
