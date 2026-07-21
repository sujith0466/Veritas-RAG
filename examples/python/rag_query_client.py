#!/usr/bin/env python3
"""
RAGuard AI - Python Client Example
Demonstrates how to authenticate and execute a query against the RAGuard API.
"""
import os
import json
import httpx
import asyncio

API_URL = os.getenv("RAGUARD_API_URL", "http://localhost:8000/api/v1")
TENANT_ID = os.getenv("RAGUARD_TENANT_ID", "acme-corp")
JWT_TOKEN = os.getenv("RAGUARD_JWT_TOKEN", "test-token") # In dev, auth is mocked if not provided

async def execute_query(query: str):
    print(f"Executing Query: '{query}'")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JWT_TOKEN}"
    }
    
    payload = {
        "tenant_id": TENANT_ID,
        "query": query,
        "top_k": 3
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_URL}/query/search",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            print("\n[+] Response Received:")
            print(f"Answer: {data.get('answer')}")
            print(f"Confidence Score: {data.get('confidence_score')}")
            print(f"Reliability Status: {data.get('reliability_status')}")
            print(f"Citations: {data.get('citations')}")
            
        except httpx.HTTPStatusError as e:
            print(f"[-] HTTP Error: {e.response.status_code}")
            print(e.response.text)
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    test_query = "What is the refund policy for enterprise licenses?"
    asyncio.run(execute_query(test_query))
