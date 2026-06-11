import argparse
import sys
import asyncio
from swarm import run_swarm

def main():
    p = argparse.ArgumentParser(description="Scraper Swarm Entrypoint")
    p.add_argument("--query", type=str, help="Search query for target assets", default=None)
    p.add_argument("--catalog_ref", type=str, help="Catalog reference ID", default=None)
    
    args = p.parse_args()
    
    # Ensure variables are cleanly structured as pure lists
    search_queries = [str(args.query)] if args.query else []
    search_targets = [str(args.catalog_ref)] if args.catalog_ref else []
    
    if not search_queries and not search_targets:
        print("Error: Either --query or --catalog_ref must be provided.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Initializing swarm pipeline for catalog_ref: {args.catalog_ref}")
    
    # Execute the async swarm passing exact required lists positionally
    asyncio.run(run_swarm(search_queries, search_targets))

if __name__ == "__main__":
    main()
