import html
import logging
import re
import requests

import config
from tts import synthesize_word_mp3

log = logging.getLogger(__name__)

# `Front` 內占位；TTS 成功後替換為含 [sound:...] 的 div
W2C_AUDIO_MARKER = "__W2C_AUDIO__"

HR_BETWEEN_SENSES = '<hr style="border:none;border-top:1px solid #eee;margin:16px 0">'

# 義項內「英文釋義」與「詞性＋中文釋義」兩行（較大）
_FONT_DEF_PX = 22
# 次要內文 px：Synonyms、Usage、Examples、字根／記憶（roots_memory）、Front 音標／難度等（與 _FONT_DEF_PX 對照）
_FONT_BODY_PX = 18
# Front 單字（大標）
_FONT_WORD_PX = 32

# 例句內目標詞：模型以 ⟦…⟧ 標記，產卡時轉粗體＋底線、字色繼承（避免模型輸出任意 HTML）
_EXAMPLE_HL_OPEN = "\u27e6"
_EXAMPLE_HL_CLOSE = "\u27e7"
_EXAMPLE_HL_PATTERN = re.compile(
    re.escape(_EXAMPLE_HL_OPEN) + r"(.*?)" + re.escape(_EXAMPLE_HL_CLOSE),
    re.DOTALL,
)
_EXAMPLE_HL_SPAN = (
    '<span style="font-weight:bold;text-decoration:underline;font-style:inherit;color:inherit">{}</span>'
)


def _example_line_to_html(line: str) -> str:
    """將 example_sentence 單行中的 ⟦…⟧ 轉為粗體＋底線（預設字色）span，其餘字元 escape。"""
    if not line:
        return ""
    parts: list[str] = []
    last = 0
    for m in _EXAMPLE_HL_PATTERN.finditer(line):
        if m.start() > last:
            parts.append(html.escape(line[last : m.start()]))
        parts.append(_EXAMPLE_HL_SPAN.format(html.escape(m.group(1))))
        last = m.end()
    parts.append(html.escape(line[last:]))
    return "".join(parts)


def _invoke(action: str, **params) -> object:
    """呼叫 AnkiConnect API。"""
    payload = {"action": action, "version": 6, "params": params}
    response = requests.post(config.ANKI_CONNECT_URL, json=payload, timeout=10)
    response.raise_for_status()
    result = response.json()
    if result.get("error"):
        raise RuntimeError(f"AnkiConnect 錯誤：{result['error']}")
    return result["result"]


def ensure_deck_exists(deck_name: str) -> None:
    _invoke("createDeck", deck=deck_name)


def _parse_usage_items(usage_value: object) -> list[str]:
    if isinstance(usage_value, list):
        return [str(x).strip() for x in usage_value if str(x).strip()]
    if isinstance(usage_value, str):
        return [s.strip() for s in usage_value.split("\n") if s.strip()]
    return []


def _build_usage_block(usage_value: object, *, margin_top: str = "12px") -> str:
    usage_items = _parse_usage_items(usage_value)[:4]
    if not usage_items:
        return ""
    usage_list = "".join(f"<li>{u}</li>" for u in usage_items)
    return (
        f'<div style="margin-top:{margin_top};font-size:{_FONT_BODY_PX}px;line-height:1.5;text-align:left">'
        '<div style="font-weight:600;margin-bottom:4px">Usage:</div>'
        f'<ul style="margin:0;padding-left:1.1em">{usage_list}</ul>'
        "</div>"
    )


def _primary_pos(word: dict) -> str:
    s = word.get("senses")
    if isinstance(s, list) and s and isinstance(s[0], dict):
        return str(s[0].get("part_of_speech", "")).strip()
    return str(word.get("part_of_speech", "")).strip()


def _senses_for_card(word: dict) -> list[dict]:
    s = word.get("senses")
    out: list[dict] = []
    if isinstance(s, list):
        for x in s:
            if not isinstance(x, dict):
                continue
            pos = str(x.get("part_of_speech", "")).strip()
            de = str(x.get("definition", "")).strip()
            dz = str(x.get("definition_zh", "")).strip()
            if pos or de or dz:
                out.append(x)
    if out:
        return out
    pos = str(word.get("part_of_speech", "")).strip()
    de = str(word.get("definition", "")).strip()
    dz = str(word.get("definition_zh", "")).strip()
    if not pos and not de and not dz:
        return []
    return [
        {
            "part_of_speech": pos,
            "definition": de,
            "definition_zh": dz,
            "synonyms": word.get("synonyms") if isinstance(word.get("synonyms"), list) else [],
            "usage_patterns": word.get("usage_patterns", []),
            "example_sentence": word.get("example_sentence", ""),
        }
    ]


def _build_roots_memory_block(word: dict) -> str:
    text = str(word.get("roots_memory", "") or "").strip()
    if not text:
        return ""
    body = html.escape(text).replace("\n", "<br>")
    return (
        f'<div style="font-size:{_FONT_BODY_PX}px;line-height:1.5;text-align:left;margin-bottom:14px">'
        '<div style="font-weight:600;margin-bottom:6px">字根／記憶</div>'
        f'<div>{body}</div>'
        "</div>"
    )


def _build_synonyms_line(sense: dict) -> str:
    raw = sense.get("synonyms")
    items: list[str] = []
    if isinstance(raw, list):
        items = [str(x).strip() for x in raw if str(x).strip()]
    if not items:
        return ""
    return (
        f'<div style="margin-top:10px;font-size:{_FONT_BODY_PX}px;line-height:1.5;text-align:left">'
        f'Synonyms: {", ".join(items)}</div>'
    )


def _build_examples_for_sense(sense: dict) -> str:
    lines = [ln.strip() for ln in str(sense.get("example_sentence", "") or "").splitlines() if ln.strip()][:2]
    if not lines:
        return ""
    html_lines = [_example_line_to_html(ln) for ln in lines]
    return (
        '<div style="margin-top:14px;text-align:left">'
        f'<div style="font-size:{_FONT_BODY_PX}px;font-weight:600;letter-spacing:0.2px;margin-bottom:4px">Examples:</div>'
        f'<div style="font-size:{_FONT_BODY_PX}px;line-height:1.5;font-style:italic">{"<br>".join(html_lines)}</div>'
        "</div>"
    )


def _build_one_sense_inner(sense: dict) -> str:
    parts: list[str] = []
    pos = str(sense.get("part_of_speech", "")).strip()
    de = str(sense.get("definition", "")).strip()
    dz = str(sense.get("definition_zh", "")).strip()
    if de:
        parts.append(
            f'<div style="font-size:{_FONT_DEF_PX}px;font-weight:bold;line-height:1.45">{de}</div>'
        )
    # 詞性與中文釋義同一行（與英文釋義同為較大字級、一般字重）
    if pos and dz:
        parts.append(
            f'<div style="font-size:{_FONT_DEF_PX}px;margin-top:4px;line-height:1.5">'
            f"{pos} {dz}"
            "</div>"
        )
    elif dz:
        parts.append(
            f'<div style="font-size:{_FONT_DEF_PX}px;margin-top:4px;line-height:1.5">{dz}</div>'
        )
    elif pos:
        parts.append(
            f'<div style="font-size:{_FONT_DEF_PX}px;margin-top:4px;line-height:1.5">{pos}</div>'
        )
    syn = _build_synonyms_line(sense)
    if syn:
        parts.append(syn)
    ub = _build_usage_block(sense.get("usage_patterns", []), margin_top="12px")
    if ub:
        parts.append(ub)
    ex = _build_examples_for_sense(sense)
    if ex:
        parts.append(ex)
    return "".join(parts)


def _build_front(word: dict) -> str:
    phonetic = word.get("phonetic", "")
    difficulty = str(word.get("difficulty", "") or "").strip()
    diff_html = (
        f'<div style="font-size:{_FONT_BODY_PX}px;text-align:center;margin-top:10px;line-height:1.5">{difficulty}</div>'
        if difficulty
        else ""
    )
    return (
        f'<div style="font-size:{_FONT_WORD_PX}px;font-weight:bold;text-align:center;margin-bottom:6px;line-height:1.2">'
        f'{word["word"]}</div>'
        f'<div style="font-size:{_FONT_BODY_PX}px;text-align:center;line-height:1.5">{phonetic}</div>'
        f'<div style="text-align:center;margin-top:8px">{W2C_AUDIO_MARKER}</div>'
        f"{diff_html}"
    )


def _build_back(word: dict) -> str:
    roots = _build_roots_memory_block(word)
    senses = _senses_for_card(word)
    if not senses:
        if roots:
            return roots
        return f'<div style="font-size:{_FONT_BODY_PX}px;line-height:1.5;text-align:left">(no definitions)</div>'
    chunks: list[str] = []
    if roots:
        chunks.append(roots)
        chunks.append(HR_BETWEEN_SENSES)
    chunks.append(f'<div style="text-align:left">{_build_one_sense_inner(senses[0])}</div>')
    if len(senses) == 1:
        return "".join(chunks)
    chunks.append(HR_BETWEEN_SENSES)
    for i in range(1, len(senses)):
        if i > 1:
            chunks.append(HR_BETWEEN_SENSES)
        chunks.append(f'<div style="text-align:left">{_build_one_sense_inner(senses[i])}</div>')
    return "".join(chunks)


def add_cards_to_anki(words: list[dict]) -> int:
    """將單字清單新增為 Anki 卡片，回傳成功新增的張數。"""
    results = add_cards_to_anki_results(words)
    return sum(1 for r in results if r is not None)


def add_cards_to_anki_results(words: list[dict]) -> list[object]:
    """
    將單字清單新增為 Anki 卡片，回傳 addNotes 的逐筆結果。
    - 成功：note id（int）
    - 失敗（duplicate 等）：None（AnkiConnect 的行為）
    """
    import tempfile

    ensure_deck_exists(config.ANKI_DECK_NAME)
    target_field = config.ANKI_AUDIO_FIELD

    with tempfile.TemporaryDirectory(prefix="word_to_card_tts_") as tmpdir:
        notes = []
        for w in words:
            fields = {
                "Front": _build_front(w),
                "Back": _build_back(w),
            }

            audio = []
            try:
                mp3_path, filename = synthesize_word_mp3(w.get("word", ""), tmpdir, voice=config.TTS_VOICE)
                sound_tag = f"[sound:{filename}]"
                insert = f'<div style="margin-top:8px;text-align:center">{sound_tag}</div>'
                if W2C_AUDIO_MARKER in fields["Front"]:
                    fields["Front"] = fields["Front"].replace(W2C_AUDIO_MARKER, insert, 1)
                else:
                    fields["Front"] = fields["Front"] + insert
                if W2C_AUDIO_MARKER in fields["Back"]:
                    fields["Back"] = fields["Back"].replace(W2C_AUDIO_MARKER, "", 1)
                if target_field not in fields:
                    fields[target_field] = ""

                audio = [
                    {
                        "path": mp3_path,
                        "filename": filename,
                        "fields": [target_field],
                    }
                ]
            except Exception as e:
                log.warning("TTS 失敗（%r）：%s", w.get("word", ""), e)
                if W2C_AUDIO_MARKER in fields["Front"]:
                    fields["Front"] = fields["Front"].replace(W2C_AUDIO_MARKER, "", 1)
                if W2C_AUDIO_MARKER in fields["Back"]:
                    fields["Back"] = fields["Back"].replace(W2C_AUDIO_MARKER, "", 1)
                audio = []

            notes.append(
                {
                    "deckName": config.ANKI_DECK_NAME,
                    "modelName": config.ANKI_MODEL_NAME,
                    "fields": fields,
                    "options": {
                        "allowDuplicate": False,
                        "duplicateScope": "deck",
                    },
                    "tags": [
                        "word-to-card",
                        w.get("difficulty", "").lower(),
                        _primary_pos(w).lower().replace("/", "-").replace(" ", "_")[:40],
                    ],
                    "audio": audio,
                }
            )

        return _invoke("addNotes", notes=notes)
