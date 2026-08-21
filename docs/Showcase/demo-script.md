# Veritas RAG — Standard Demo Script

**Duration**: 10 Minutes
**Audience**: Technical Decision Makers

## Segment 1: The Hallucination Problem (2 mins)
*Visual: Standard ChatGPT / RAG flow failing.*
**Script**: "When users ask standard RAG systems about complex corporate policies, the LLM often guesses if the retrieval engine fails to find the exact paragraph. This results in plausible but factually incorrect answers—hallucinations."

## Segment 2: Enter Veritas RAG (3 mins)
*Visual: Veritas RAG Architecture Diagram.*
**Script**: "Veritas RAG wraps the RAG process. We intercept the query. Watch as I send the exact same question to Veritas RAG."
*Action: Execute cURL request via Postman.*
**Script**: "Notice the difference. Veritas RAG evaluated the retrieved context, realized it lacked coverage, and automatically rewrote the query to fetch better results. The final answer is strictly grounded."

## Segment 3: Security & Governance (3 mins)
*Action: Send a query containing a Social Security Number.*
**Script**: "In enterprise environments, data leakage is a massive risk. I just sent a query with an SSN. Behind the scenes, the Veritas RAG DLP engine intercepted it, redacted it to `[SSN_REDACTED]`, and sent the clean version to the LLM."

## Segment 4: Observability (2 mins)
*Visual: Grafana Dashboard.*
**Script**: "Every action is tracked. Here in our Grafana dashboard, we see the token consumption, the 95th percentile latency, and the exact confidence scores of every query over the last hour. If an anomaly occurs, our Prometheus alert rules fire immediately."
