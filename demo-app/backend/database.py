import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mediamonitor")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

TEST_MODE = os.getenv("TEST_MODE") == "1"

# Ensure pgvector extension exists (skip if TEST_MODE or sqlite)
if not TEST_MODE and engine.url.get_backend_name() != "sqlite":
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:
        # Extension may require superuser; log and continue to avoid breaking startup
        print(f"Warning: could not ensure pgvector extension: {exc}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
