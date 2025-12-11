import asyncio
import os

from ingestion_queue import IngestionQueue
from whisper_stream_processor import WhisperStreamProcessor


def _default_sources():
    env = os.getenv("WHISPER_SOURCES")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    return [
        "https://www.youtube.com/watch?v=pykpO5kQJ98",  # Euronews (UI live channel)
        "https://www.youtube.com/watch?v=gCNeDWCI0vo",  # Al Jazeera English (UI live channel)
        # CNN audio stream used in UI live channel
        "https://tunein.cdnstream1.com/2868_96.mp3?aw_0_1st.playerid=SLb0WwgW&aw_0_1st.skey=1765272278&aw_0_1st.abtest=&partnerId=SLb0WwgW&aw_0_1st.stationId=s20407&aw_0_1st.premium=false&source=TuneIn&aw_0_1st.platform=tunein&aw_0_1st.genre_id=g3124&aw_0_1st.class=talk&aw_0_1st.ads_partner_alias=emb.CNN&aw_0_azn.planguage=en&aw_0_1st.is_ondemand=false&aw_0_1st.topicId=na&aw_0_1st.programId=p4648826&aw_0_1st.affiliateIds=a38460%2ca33291%2ca39100%2ca40075%2ca39163&aw_0_1st.bandId=16",
    ]


def build_processor(queue: IngestionQueue) -> WhisperStreamProcessor:
    sources = _default_sources()
    cap_secs = int(os.getenv("WHISPER_CAPTURE_SECONDS", "45"))
    break_secs = int(os.getenv("WHISPER_BREAK_SECONDS", "15"))
    rate = int(os.getenv("WHISPER_CAPTURE_RATE", "1"))
    enabled = True

    # Allow runtime overrides persisted in Redis
    cfg = queue.load_config()
    if cfg:
        sources = cfg.get("sources") or sources
        cap_secs = int(cfg.get("capture_seconds") or cap_secs)
        break_secs = int(cfg.get("break_seconds") or break_secs)
        rate = int(cfg.get("capture_rate") or rate)
        if "enabled" in cfg:
            enabled = bool(cfg.get("enabled"))

    return WhisperStreamProcessor(
        sources=sources,
        capture_seconds=cap_secs,
        break_seconds=break_secs,
        capture_rate=rate,
        # type: ignore
        enabled=enabled,
    )


async def main():
    queue = IngestionQueue.from_env()
    if not queue:
        raise RuntimeError("REDIS_URL is required for ingestor service")

    processor = build_processor(queue)
    stop_event = asyncio.Event()

    async def refresh_config():
        while not stop_event.is_set():
            try:
                cfg = queue.load_config()
                if cfg:
                    cap = cfg.get("capture_seconds")
                    brk = cfg.get("break_seconds")
                    rate = cfg.get("capture_rate")
                    enabled = cfg.get("enabled")
                    cap = int(cap) if cap else None
                    brk = int(brk) if brk is not None else None
                    rate = int(rate) if rate else None
                    processor.update_config(
                        sources=cfg.get("sources"),
                        capture_seconds=cap,
                        break_seconds=brk,
                        capture_rate=rate,
                        enabled=enabled,
                    )
            except Exception as exc:
                print(f"[Ingestor] Config refresh error: {exc}")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                continue

    async def enqueue_callback(data: dict):
        # Push raw analysis dict; backend consumer will broadcast and persist.
        for attempt in range(3):
            try:
                queue.push(data)
                try:
                    src = data.get("source") or data.get("channel") or "unknown"
                    title = data.get("title") or data.get("english_summary") or data.get("ocr_text") or ""
                    print(f"[Ingestor] Enqueued event from {src}: {title[:80]}")
                except Exception:
                    pass
                return
            except Exception as exc:
                # Retry quickly a few times to tolerate transient Redis blips
                print(f"[Ingestor] Failed to push to queue (attempt {attempt + 1}/3): {exc}")
                await asyncio.sleep(1)
        print("[Ingestor] Dropping event after repeated Redis push failures.")

    refresher = asyncio.create_task(refresh_config())

    while True:
        try:
            print(f"[Ingestor] Starting run loop. Sources: {processor.sources}")
            await processor.run(enqueue_callback)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"[Ingestor] Error: {exc}. Restarting in 5s.")
            await asyncio.sleep(5)
        else:
            # run exited without raising (likely disabled/no sources). Avoid tight loop.
            status = processor.status()
            last_err = status.get("last_error")
            if last_err:
                print(f"[Ingestor] Stopped run loop: {last_err}. Retrying in 5s.")
            await asyncio.sleep(5)

    await processor.stop()
    stop_event.set()
    refresher.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
