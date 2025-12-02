import asyncio
import json
from typing import Any, Dict

from openai import OpenAI

from models import AnalysisLog


def _build_prompt(log: AnalysisLog) -> str:
    keywords = ", ".join(log.trending_keywords or [])
    context = f"""
Source: {log.source or ""}
Timestamp: {log.timestamp.isoformat() if log.timestamp else ""}
OCR/Raw Text: {log.raw_text or ""}
English Summary: {log.summary or ""}
Vietnamese Translation: {log.vietnamese_translation or ""}
Keywords: {keywords}
Sentiment Score: {log.sentiment_score}
"""

    instructions = """
You are an information extraction system that converts news text into a structured knowledge graph.
Extract entities, events, and relations based on the context above.

Return STRICT JSON (no markdown, no commentary) with this schema:
{
  "entities": [
    {"name": "Joe Biden", "type": "Person"}
  ],
  "events": [
    {
      "id": "event-1",
      "type": "Speech",
      "time": "2025-11-30T12:34:00Z",
      "location": "Washington, DC",
      "participants": ["Joe Biden"]
    }
  ],
  "relations": [
    {"subject": "Joe Biden", "predicate": "SUPPORTS", "object": "Ukraine"}
  ]
}

Rules:
- Infer entities and relations when confident; return empty arrays when unsure.
- Use ISO 8601 for times when possible.
- Use concise names; do not invent ids for entities, but you may assign a simple id to events.
- Output ONLY raw JSON compatible with json.loads.
"""
    return f"{context}\n\n{instructions}"


def _parse_json_response(raw_text: str) -> Dict[str, Any]:
    cleaned = raw_text.strip()
    fence_prefixes = ("```json", "```JSON", "```")
    for prefix in fence_prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    if cleaned.endswith("```"):
        cleaned = cleaned[: -3].strip()
    return json.loads(cleaned)


async def extract_kg_for_log(log: AnalysisLog, client: OpenAI) -> Dict[str, Any]:
    """Extract KG items from a single AnalysisLog row using Groq/OpenAI."""
    prompt = _build_prompt(log)

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=800,
    )

    text = response.choices[0].message.content.strip()
    kg_data = _parse_json_response(text)

    if "entities" not in kg_data:
        kg_data["entities"] = []
    if "events" not in kg_data:
        kg_data["events"] = []
    if "relations" not in kg_data:
        kg_data["relations"] = []

    return kg_data
