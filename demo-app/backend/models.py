
import os

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from pgvector.sqlalchemy import Vector
from sqlalchemy.sql import func
from database import Base

# Embedding dimension (default for nomic-embed-text = 768)
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
class AnalysisLog(Base):
    __tablename__ = "analysis_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String, index=True)
    summary = Column(Text)
    vietnamese_translation = Column(Text)
    raw_text = Column(Text) # OCR text or transcript
    sentiment_score = Column(Float)
    trending_keywords = Column(JSON)
    video_timestamp = Column(String) # Timestamp in the video
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    kg_status = Column(String, default="pending")
    kg_raw = Column(JSON, nullable=True)
    kg_processed_at = Column(DateTime(timezone=True), nullable=True)
