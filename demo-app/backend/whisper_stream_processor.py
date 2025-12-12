import asyncio
import json
import os
import subprocess
from datetime import datetime
from typing import Callable, Iterable, Optional

import yt_dlp
from openai import OpenAI


def _make_audio_client() -> OpenAI:
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY/OPENAI_API_KEY for Whisper ASR")
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
    )


def _friendly_source_name(src: str) -> str:
    """Map raw URLs/IDs to a readable live channel name for UI consistency."""
    s = (src or "").lower()
    if "pykp05kqj98" in s or "pykp" in s or "euronews" in s:
        return "Euronews"
    if "gcne" in s or "al jazeera" in s or "gcnedwci0vo" in s:
        return "Al Jazeera English"
    if "tunein.cdnstream1.com/2868_96.mp3" in s or "cnn" in s:
        return "CNN Audio"
    return src


def _is_probable_ad(text: str, summary: str) -> bool:
    """Heuristic to drop obvious promo/bumper content."""
    blob = f"{text or ''} {summary or ''}".lower()
    if not blob.strip():
        return False
    promo_phrases = [
        "connects viewers",
        "promotes animal welfare",
        "sponsored by",
        "thanks for watching",
        "subscribe for more",
        "you're listening to cnn",
        "euronews connects viewers",
        "breaking news updates around the clock",
    ]
    return any(p in blob for p in promo_phrases)


class WhisperStreamProcessor:
    """Background loop that records short clips from multiple sources and transcribes with Whisper."""

    def __init__(
        self,
        sources: Iterable[str],
        capture_seconds: int = 45,
        break_seconds: int = 15,
        capture_rate: int = 1,
        enabled: bool = True,
    ):
        self.sources = [s for s in sources if s]
        self.capture_seconds = capture_seconds
        self.break_seconds = break_seconds
        self.capture_rate = max(1, capture_rate)
        self.enabled = enabled
        self._stop_event = asyncio.Event()
        self._stop_event.set()
        self._client: Optional[OpenAI] = None
        self._last_result: dict | None = None
        self._last_error: str | None = None

    def update_config(
        self,
        sources: Optional[Iterable[str]] = None,
        capture_seconds: Optional[int] = None,
        break_seconds: Optional[int] = None,
        capture_rate: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        if sources is not None:
            cleaned = [s.strip() for s in sources if (s or "").strip()]
            self.sources = cleaned or self.sources
        if capture_seconds is not None and capture_seconds > 0:
            self.capture_seconds = capture_seconds
        if break_seconds is not None and break_seconds >= 0:
            self.break_seconds = break_seconds
        if capture_rate is not None and capture_rate > 0:
            self.capture_rate = capture_rate
        if enabled is not None:
            self.enabled = bool(enabled)

    def status(self):
        return {
            "enabled": self.enabled,
            "running": not self._stop_event.is_set(),
            "sources": self.sources,
            "capture_seconds": self.capture_seconds,
            "break_seconds": self.break_seconds,
            "capture_rate": self.capture_rate,
            "last_result": self._last_result,
            "last_error": self._last_error,
        }

    async def run(self, callback: Callable[[dict], asyncio.Future]):
        self._stop_event.clear()
        if not self.sources:
            self._last_error = "No ASR sources configured"
            self._stop_event.set()
            return

        try:
            self._client = _make_audio_client()
        except Exception as exc:
            self._last_error = str(exc)
            self._stop_event.set()
            return

        while not self._stop_event.is_set():
            if not self.enabled:
                self._last_error = "ASR disabled"
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=max(5, self.break_seconds or 5))
                except asyncio.TimeoutError:
                    continue
            for source in list(self.sources):
                if self._stop_event.is_set():
                    break
                for _ in range(max(1, self.capture_rate)):
                    if self._stop_event.is_set():
                        break
                    try:
                        await self._process_source(source, callback)
                    except Exception as exc:
                        self._last_error = str(exc)
                        print(f"[WhisperStream] Error processing {source}: {exc}")
                    if self.break_seconds:
                        try:
                            await asyncio.wait_for(self._stop_event.wait(), timeout=self.break_seconds)
                        except asyncio.TimeoutError:
                            pass

    async def _process_source(self, source: str, callback: Callable[[dict], asyncio.Future]):
        stream_url = await asyncio.to_thread(self._get_stream_url, source)
        if not stream_url:
            raise RuntimeError(f"Could not resolve stream URL for {source}")

        display_source = _friendly_source_name(source)
        audio_bytes = await asyncio.to_thread(self._record_audio_clip, stream_url, self.capture_seconds)
        if not audio_bytes:
            raise RuntimeError("No audio captured")

        analysis = await asyncio.to_thread(self._transcribe_audio, audio_bytes, display_source)
        if analysis:
            self._last_result = {
                "source": display_source,
                "text": analysis.get("headline_ocr") or analysis.get("summary") or "",
                "timestamp": analysis.get("timestamp"),
            }
            self._last_error = None
            await callback(analysis)

    def _get_stream_url(self, url: str) -> str | None:
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("url")
        except Exception as exc:
            self._last_error = f"yt-dlp failed: {exc}"
            return None

    def _record_audio_clip(self, stream_url: str, duration: int) -> bytes:
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "quiet",
            "-i",
            stream_url,
            "-t",
            str(duration),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "wav",
            "-",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as exc:
            self._last_error = f"ffmpeg capture failed: {exc.stderr.decode(errors='ignore')[:200]}"
            return b""

    def _transcribe_audio(self, audio_bytes: bytes, source_name: str) -> dict | None:
        if not self._client:
            self._client = _make_audio_client()
        model_name = os.getenv("WHISPER_MODEL", "whisper-large-v3")
        now_ts = datetime.now().isoformat()

        def _normalize_segments(raw_segments):
            cleaned = []
            for seg in raw_segments or []:
                # OpenAI objects expose attributes; dicts are already serializable
                if hasattr(seg, "model_dump"):
                    seg = seg.model_dump()
                elif not isinstance(seg, dict):
                    seg = {
                        "id": getattr(seg, "id", None),
                        "start": getattr(seg, "start", None),
                        "end": getattr(seg, "end", None),
                        "text": getattr(seg, "text", None),
                        "avg_logprob": getattr(seg, "avg_logprob", None),
                    }
                cleaned.append(seg)
            return cleaned

        try:
            transcription = self._client.audio.transcriptions.create(
                model=model_name,
                file=("audio.wav", audio_bytes),
                response_format="verbose_json",
            )
        except Exception as exc:
            self._last_error = f"Whisper transcription failed: {exc}"
            return None

        if hasattr(transcription, "text"):
            text = getattr(transcription, "text", "")
            language = getattr(transcription, "language", None)
            duration_val = getattr(transcription, "duration", None)
            segments_val = getattr(transcription, "segments", None)
        else:
            payload = transcription if isinstance(transcription, dict) else {}
            text = payload.get("text", "")
            language = payload.get("language")
            duration_val = payload.get("duration")
            segments_val = payload.get("segments")

        if duration_val is not None:
            duration_val = str(duration_val)

        segments_clean = _normalize_segments(segments_val)

        summary_en, translation_vi, subtitle_vi = self._summarize_and_translate(text)
        # Drop probable ads/bumper content by clearing summaries so the API can ignore them
        if _is_probable_ad(text, summary_en):
            summary_en = ""
            translation_vi = ""
            subtitle_vi = ""

        def _clean(value: str) -> str:
            v = (value or "").strip()
            # Drop simple markdown emphasis and prefixes the model might emit
            for prefix in ("**Vietnamese Translation:**", "Vietnamese Translation:", "Translation:", "**"):
                if v.startswith(prefix):
                    v = v[len(prefix):].strip()
            if v.startswith("*") and v.endswith("*"):
                v = v.strip("* ").strip()
            return v

        headline = _clean(summary_en or "")

        return {
            "source": source_name,
            "headline_ocr": headline,
            "summary": summary_en or "",
            "vietnamese_translation": _clean(translation_vi),
            "keywords": [],
            "sentiment_score": 0.0,
            "subtitle_vi": _clean(subtitle_vi or translation_vi),
            "timestamp": now_ts,
            "language": language,
            "duration": duration_val,
            "segments": segments_clean,
        }

    def _summarize_and_translate(self, text: str) -> tuple[str, str, str]:
        """Return (english_summary, vietnamese_translation, vietnamese_caption)."""
        if not text or not text.strip():
            return "", "", ""

        def _strip_markdown(val: str) -> str:
            v = (val or "").strip()
            # Remove common bold markers and headings the model might emit
            for prefix in ("**Vietnamese Translation:**", "Vietnamese Translation:", "Translation:", "**Summary:**", "**"):
                if v.startswith(prefix):
                    v = v[len(prefix):].strip()
            v = v.strip("* ").strip()
            return v

        prompt = f"""
You are a concise translator and summarizer.
Return STRICT JSON only (no markdown) with exactly these keys:
{{
  "summary_en": "short English summary (max 2 sentences)",
  "translation_vi": "natural Vietnamese translation of the transcript",
  "caption_vi": "very short Vietnamese caption, max 12 words"
}}

Transcript:
{text}
"""
        try:
            resp = self._client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=220,
            )
            content = resp.choices[0].message.content.strip()
            # Try strict JSON first; fall back to line parsing
            try:
                data = json.loads(content.replace("```json", "").replace("```", "").strip())
            except Exception:
                data = {}

            if not data:
                parts = [p.strip("- •").strip() for p in content.split("\n") if p.strip()]
                summary_en = parts[0] if parts else text[:200]
                translation_vi = parts[1] if len(parts) > 1 else ""
                caption_vi = parts[2] if len(parts) > 2 else translation_vi or summary_en
            else:
                summary_en = data.get("summary_en") or text[:200]
                translation_vi = data.get("translation_vi") or ""
                caption_vi = data.get("caption_vi") or translation_vi or summary_en
            return (
                _strip_markdown(summary_en),
                _strip_markdown(translation_vi),
                _strip_markdown(caption_vi),
            )
        except Exception as exc:
            self._last_error = f"Summarize/translate failed: {exc}"
            return text[:200], "", ""

    async def stop(self):
        self._stop_event.set()
