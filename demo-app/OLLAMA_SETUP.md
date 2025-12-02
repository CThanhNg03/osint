# Ollama embedding sidecar

We use Ollama to self-host embeddings via the OpenAI-compatible API.

1) Start services:
   ```bash
   docker-compose up -d embedding
   ```

2) Pull the embedding model inside the container (first time only):
   ```bash
   docker-compose exec embedding ollama pull nomic-embed-text
   ```
   - If you use a different model, update `EMBEDDING_MODEL` (and `EMBEDDING_DIM`) to match.

3) Backend env:
   ```
   EMBEDDING_BASE_URL=http://embedding:11434/v1
   EMBEDDING_MODEL=nomic-embed-text
   EMBEDDING_DIM=768
   EMBEDDING_API_KEY=ollama   # any string; Ollama does not enforce auth by default
   ```

4) Ensure pgvector column dimension matches your embedding size. For `nomic-embed-text`:
   ```sql
   ALTER TABLE analysis_logs ALTER COLUMN embedding TYPE vector(768);
   ```

5) Restart backend after model is pulled.
