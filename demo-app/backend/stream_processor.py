import asyncio
import base64
import json
import os
from datetime import datetime
from io import BytesIO

import cv2
import yt_dlp
from openai import OpenAI
from PIL import Image

from database import SessionLocal
from embedding_utils import generate_embedding
from models import AnalysisLog


def _get_groq_client() -> OpenAI:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set; cannot call Groq Vision.")
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
    )


class StreamProcessor:
    def __init__(self, youtube_url, source_name="Euronews"):
        self.youtube_url = youtube_url
        self.source_name = source_name
        self.cap = None
        self.running = False

    def get_stream_url(self):
        """Get stream URL from YouTube via yt-dlp."""
        ydl_opts = {
            "format": "best[ext=mp4]",
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.youtube_url, download=False)
                return info["url"]
        except Exception as e:
            print(f"Error getting stream URL: {e}")
            return None

    async def process_stream(self, callback):
        """Continuously process stream with Groq."""
        self.running = True
        print(f"Starting stream processing for {self.source_name}...")

        frame_count = 0
        reconnect_attempts = 0
        max_reconnect = 3

        while self.running and reconnect_attempts < max_reconnect:
            try:
                stream_url = self.get_stream_url()
                if not stream_url:
                    print("Failed to get stream URL. Retrying in 10s...")
                    await asyncio.sleep(10)
                    reconnect_attempts += 1
                    continue

                self.cap = cv2.VideoCapture(stream_url)
                if not self.cap.isOpened():
                    print("Failed to open video stream. Retrying...")
                    await asyncio.sleep(10)
                    reconnect_attempts += 1
                    continue

                print(f"Connected to {self.source_name} stream")
                reconnect_attempts = 0

                while self.running:
                    ret, frame = self.cap.read()

                    if not ret:
                        print("Stream ended or error. Reconnecting...")
                        break

                    frame_count += 1

                    # Process roughly every 15 seconds (~30fps => 450 frames)
                    if frame_count % 450 == 0:
                        try:
                            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            pil_image = Image.fromarray(rgb_frame)

                            analysis = await self.analyze_frame_comprehensive(pil_image)

                            if analysis:
                                self.save_to_db(analysis)
                                await callback(analysis)

                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Processed frame {frame_count}")

                        except Exception as e:
                            print(f"Error analyzing frame: {e}")

                    await asyncio.sleep(0.01)

            except Exception as e:
                print(f"Stream error: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)
                reconnect_attempts += 1
            finally:
                if self.cap:
                    self.cap.release()

    def image_to_base64(self, image):
        """Convert PIL Image to base64 string."""
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    async def analyze_frame_comprehensive(self, image):
        """Full analysis of a frame via Groq Vision."""

        image_base64 = self.image_to_base64(image)

        prompt = """
You are a real-time news vision analyzer. Analyze the frame and return JSON:
{
  "headline_ocr": "Headline text",
  "summary": "Short English summary",
  "vietnamese_translation": "Vietnamese translation",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "sentiment_score": 0.0,
  "subtitle_vi": "Short Vietnamese caption"
}
Return JSON only, no markdown.
"""

        try:
            client = _get_groq_client()
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                            },
                        ],
                    }
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            text = response.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)

            data["source"] = self.source_name
            data["timestamp"] = datetime.now().isoformat()
            data["ocr_text"] = data.get("headline_ocr", "")

            return data

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Raw response: {text}")
            return None
        except Exception as e:
            print(f"Groq API Error: {e}")
            return None

    def save_to_db(self, data):
        """Persist analysis result to PostgreSQL."""
        db = SessionLocal()
        try:
            embedding = None
            try:
                embed_text = "\n".join(
                    filter(
                        None,
                        [
                            data.get("summary", ""),
                            data.get("vietnamese_translation", ""),
                            data.get("ocr_text", ""),
                        ],
                    )
                )
                if embed_text.strip():
                    embedding = generate_embedding(embed_text)
                    if not embedding or len(embedding) != AnalysisLog.embedding.type.dimensions:
                        embedding = None
            except Exception as embed_exc:
                print(f"Embedding generation failed: {embed_exc}")

            log = AnalysisLog(
                source=data["source"],
                summary=data.get("summary", ""),
                vietnamese_translation=data.get("vietnamese_translation", ""),
                raw_text=data.get("ocr_text", ""),
                sentiment_score=data.get("sentiment_score", 0.0),
                trending_keywords=data.get("keywords", []),
                video_timestamp=datetime.now().strftime("%H:%M:%S"),
                embedding=embedding,
            )
            db.add(log)
            db.commit()
            print(f"Saved to database: {data.get('summary', '')[:50]}...")
        except Exception as e:
            print(f"DB Error: {e}")
            db.rollback()
        finally:
            db.close()

    def stop(self):
        """Stop the stream processor."""
        self.running = False
        if self.cap:
            self.cap.release()
        print(f"Stopped processing {self.source_name}")
