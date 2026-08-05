"""
JARVIS Internet Module (MVP version)
--------------------------------------
Simple web search wrapper. Uses Serper.dev (cheap Google Search API) —
swap this for anything else later (Bing, SerpAPI, Brave Search API)
without touching orchestrator.py, since it only calls `search(query)`.

Set env var:
    export SERPER_API_KEY=...
Get a free key at https://serper.dev
"""

import os
import requests


def search(query: str, num_results: int = 3) -> str:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return "Internet search is not configured (missing SERPER_API_KEY)."

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        organic = data.get("organic", [])[:num_results]

        if not organic:
            return "No results found."

        lines = []
        for item in organic:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            lines.append(f"- {title}: {snippet}")

        return "\n".join(lines)

    except Exception as e:
        return f"Search failed: {e}"
