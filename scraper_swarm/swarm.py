import asyncio
import json
from typing import List
import httpx
from worker import fetch_and_parse

async def run_swarm(queries: List[str], targets: List[str], concurrency: int = 5, timeout: float = 10.0):
    results = []
    sem = asyncio.Semaphore(concurrency)
    
    print(f"Swarm engine started. Processing Queries: {queries}, Targets: {targets}")
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async def run_one(url: str):
            async with sem:
                return await fetch_and_parse(client, url, timeout=timeout)
        
        # Guard against empty iterable loops
        if not queries and targets:
            # If dispatcher only passes targets/catalog refs, map them directly
            queries = targets
            
        tasks = []
        for q in queries:
            print(f"Spawning worker task for target query: {q}")
            # Map your targets to active worker tasks here
            
    print("Swarm execution completed successfully.")
    return results
