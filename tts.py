import asyncio
import os
import re


def _safe_filename_component(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_\-]+", "", text)
    return text or "word"


async def _edge_tts_save(text: str, voice: str, out_path: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out_path)


def synthesize_word_mp3(word: str, out_dir: str, *, voice: str = "en-US-JennyNeural") -> tuple[str, str]:
    """
    產生單字發音 mp3。
    回傳 (absolute_path, filename) 供 AnkiConnect audio 使用。
    """
    filename = f"tts_{_safe_filename_component(word)}.mp3"
    out_path = os.path.join(out_dir, filename)
    asyncio.run(_edge_tts_save(word, voice, out_path))
    return out_path, filename

