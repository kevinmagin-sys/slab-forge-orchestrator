import asyncio
import re
from typing import Dict, Any

import httpx


PRICE_RE = re.compile(r"\$\s?([0-9,.]+)")


async def fetch_and_parse(client: httpx.AsyncClient, url: str, timeout: float = 10.0) -> Dict[str, Any]:
    resp = {"url": url, "status": None, "text_snippet": None, "prices": []}
    try:
        r = await client.get(url, timeout=timeout)
        resp["status"] = r.status_code
        text = r.text[:2000]
        resp["text_snippet"] = text[:500]
        resp["prices"] = PRICE_RE.findall(text)
    except Exception as e:
        resp["error"] = str(e)
    return resp
