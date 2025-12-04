import os
from datetime import datetime, timedelta

from openai import OpenAI
from sqlalchemy.orm import Session

from embedding_utils import generate_embedding
from models import AnalysisLog

# Configure Groq / OpenAI-compatible client
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
)


def _prepare_text_for_embedding(log: AnalysisLog) -> str:
    parts = [
        log.summary or "",
        log.vietnamese_translation or "",
        log.raw_text or "",
        ", ".join(log.trending_keywords or []),
    ]
    return "\n".join(p for p in parts if p)


def _ensure_embeddings(logs, db: Session):
    updated = False
    for log in logs:
        if log.embedding is None:
            try:
                text = _prepare_text_for_embedding(log)
                embedding = generate_embedding(text)
                if embedding:
                    log.embedding = embedding
                    updated = True
            except Exception as exc:
                print(f"Embedding generation failed for log {log.id}: {exc}")
    if updated:
        db.commit()


async def answer_question(question: str, db: Session):
    """Answer user question using vector search over recent AnalysisLog entries."""

    time_threshold = datetime.now() - timedelta(minutes=30)

    # Ensure recent logs have embeddings
    recent_candidates = (
        db.query(AnalysisLog)
        .filter(AnalysisLog.timestamp >= time_threshold)
        .order_by(AnalysisLog.timestamp.desc())
        .limit(50)
        .all()
    )
    _ensure_embeddings(recent_candidates, db)

    question_embedding = []
    try:
        question_embedding = generate_embedding(question)
    except Exception as exc:
        print(f"Question embedding error: {exc}")

    if question_embedding:
        vector_logs = (
            db.query(AnalysisLog)
            .filter(
                AnalysisLog.timestamp >= time_threshold,
                AnalysisLog.embedding != None,  # noqa: E711
            )
            .order_by(AnalysisLog.embedding.cosine_distance(question_embedding))
            .limit(8)
            .all()
        )
    else:
        vector_logs = []

    if not vector_logs:
        vector_logs = (
            db.query(AnalysisLog)
            .filter(AnalysisLog.timestamp >= time_threshold)
            .order_by(AnalysisLog.timestamp.desc())
            .limit(8)
            .all()
        )

    context_parts = []
    if vector_logs:
        context_parts.append("=== Context from vector search (recent) ===\n")
        for log in vector_logs:
            keywords = ", ".join(log.trending_keywords or [])
            context_parts.append(
                f"Time: {log.timestamp.strftime('%H:%M:%S') if log.timestamp else ''}\n"
                f"Source: {log.source}\n"
                f"Summary (EN): {log.summary}\n"
                f"Translation (VI): {log.vietnamese_translation}\n"
                f"Keywords: {keywords}\n"
                f"Sentiment: {log.sentiment_score}\n"
                "---\n"
            )
    else:
        context_parts.append("No analysis data available yet.\n")

    context = "".join(context_parts)

    prompt = f"""
You are an AI news assistant. Use the context to answer in Vietnamese.

CONTEXT (from vector search):
{context}

QUESTION:
{question}

GUIDELINES:
- Reply in Vietnamese, concise and accurate
- Use the provided context; if insufficient, say so
- Limit to 3-4 sentences

ANSWER:
"""

    # Try up to 5 times with context
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=500,
            )

            answer = response.choices[0].message.content.strip()
            return {
                "answer": answer,
                "context_used": len(vector_logs),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"Groq Chat attempt {attempt + 1} failed: {e}")

    # Final fallback: ask directly without context
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": f"Trả lời ngắn gọn bằng tiếng Việt câu hỏi sau: {question}",
                }
            ],
            temperature=0.4,
            max_tokens=300,
        )
        answer = response.choices[0].message.content.strip()
        return {
            "answer": answer,
            "context_used": 0,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Groq Chat fallback failed: {e}")
        return {
            "answer": "Xin loi, toi gap loi khi xu ly cau hoi. Vui long thu lai.",
            "context_used": 0,
            "timestamp": datetime.now().isoformat(),
        }
