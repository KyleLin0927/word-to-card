"""
Gemini Vision 模組（google-genai 新版 SDK）
截圖 → Gemini → GRE/TOEFL 單字 JSON
"""

import json
import logging
import pathlib

from google import genai
from google.genai import types

import config

_client = genai.Client(api_key=config.GEMINI_API_KEY)
_resolved_model: str | None = None
log = logging.getLogger(__name__)

PROMPT = """你是一位專業英文老師，專門協助學生準備 GRE / TOEFL 考試。

請分析這張截圖，找出 1～5 個重要的英文學術單字（適合非母語人士加強記憶的程度）。
請優先辨識位於截圖畫面中心位置的單字。如果中心位置不明顯，則挑選畫面中最符合 GRE/TOEFL 難度的單字。

若圖片模糊、無英文文字或無法辨識，請僅回傳：{"error": "IMAGE_UNCLEAR"}

正常情況請回傳嚴格 JSON 陣列，每個物件包含以下欄位：
- "word": 單字原形（字串）
- "phonetic": IPA 發音（字串）
- "difficulty": "GRE"、"TOEFL" 或 "Academic"（字串；整張卡共用）
- "senses": **陣列（至少 1 筆、至多 4 筆）**，每一筆代表一個**可獨立學習**的義項／常用詞性用法：
  - "part_of_speech": 非動詞如 noun / adjective / proper noun（字串）。**動詞**（含 phrasal verb）**必須**標及物性，**不得**只寫 verb：格式為 "verb (vt)"、"verb (vi)" 或 "verb (vi/vt)"（兼及物與不及物時；括號內全小寫）。片語動詞為 "phrasal verb (vt)"、"phrasal verb (vi)"、"phrasal verb (vi/vt)"（擇一）
  - "definition": 英文定義，簡潔明確（字串）
  - "definition_zh": 中文定義（字串）。若該義在**書面／口語**或**正式／非正式**（含學術、商務、日常）上對「使用頻率或場景」有辨識幫助，可在**句末**括註簡短提示（例如「（書面較常）」「（口語常用）」「（正式場合較常）」）；無增益則不加
  - "synonyms": 0～3 個同義詞（字串陣列；無則 []）
  - "usage_patterns": 高訊號搭配（字串陣列，0～4 筆；不要硬湊；無則 []）
  - "example_sentence": **1～2 句**英文例句，**只許對應本義項**，用換行 \\n 分隔；勿把其他義項混進同一句。**每句**須以 **⟦** 與 **⟧**（U+27E6、U+27E7）包住該句中的**目標單字或連續片語**；括號內必須與句中**逐字連續**一致，且含**所有曲折**：過去式／分詞的 **-ed**、**-ing**、**-s** 等皆不可漏（例如句中是 accounted 就標 ⟦accounted⟧ 或與後續介詞連用則 ⟦accounted for⟧，勿只標 account）。**常用片語**（如 *account for*）須**整段**一併包在同一對 ⟦⟧ 內（例：These factors do not fully ⟦account for⟧ the phenomenon.）；過去式則 ⟦accounted for⟧ 等。**每句僅一處**一對 ⟦⟧。除 ⟦⟧ 外**不要**輸出任何 HTML 或 markdown
- **多義項規則（保守）**：**預設 senses 只有 1 筆**。「足夠重要」＝該分歧須足以在 **TOEFL／IELTS**、**商用英文**或 **CEFR C2** 讀聽寫情境中**各自獨立出現**，且考生／進階學習者**不拆開就容易混淆**；例如專有名詞「太平洋」vs 一般形容詞「溫和的」這類才拆成多筆。若對托福雅思、商用、C2 幾乎沒有分開記的價值，請合併為 1 筆。**不要**為細微語氣差、同一核心意的換說法、或一筆定義＋括註可說清者硬拆多區塊。
- **熟詞僻義（考試偏好）**：若該字除常見義外，另有 **GRE／TOEFL 讀寫常考的次要義**（表面是熟字、語義卻不同），且套進句子會**解錯或選錯義**，應拆成**多筆 senses**（各筆獨立例句，勿混義），勿只留日常義。**範例 *dispose***：一義「處置／清除」（如 *dispose of waste*）；另一義「使（某人）傾向於／使易於（某態度或行為）」（如 *dispose someone to sympathy*、*well-disposed* 相關用法）。兩義皆須能分辨時**分筆**（仍至多 4 筆，依截圖語境與考試重要度排序）。
- **捨棄極冷僻義**：若某義項**僅見於古典文學／詩歌**或**極罕見**現代語境，且**不屬於 TOEFL／GRE 常考或一般學術／現代英語常用範圍**，請**直接省略**，**不要**列入 `senses`，避免增加使用者記憶負擔。
- **順序**：`senses` 陣列**整體**須依 **TOEFL／IELTS、商用英文、C2** 的重要性與**實際使用頻率**嚴格**由高到低**排列。senses[0] 須為截圖／畫面最可能指涉、且對上述目標**最重要／最常用**者；其後遞減，勿將冷僻義置前。

只回傳 JSON，不要任何說明文字或 markdown。"""

TEXT_PROMPT = """你是一位專業英文老師，專門協助學生準備 GRE / TOEFL 考試。

使用者會提供一段從剪貼簿取得的文字（通常是一個英文單字，但可能包含前後空白或標點）。

請判斷這段文字是否是一個「單一英文單字」或可合理正規化為單一英文單字（例如去除前後空白、常見標點）。

若不是單字（例如空字串、過長片語/句子、無法判斷），請僅回傳：{"error":"NOT_A_WORD"}

若是單字，請回傳嚴格 JSON 物件，包含以下欄位：
- "word": 單字原形（字串）
- "phonetic": IPA 發音（字串）
- "difficulty": "GRE"、"TOEFL" 或 "Academic"（字串；整張卡共用）
- "senses": **陣列（至少 1 筆、至多 4 筆）**，每一筆代表一個**可獨立學習**的義項／常用詞性用法：
  - "part_of_speech"、 "definition"、 "definition_zh"（中文釋義；必要時句末可括註書面／口語／正式與否等，例如「（口語常用）」）。**動詞**（含 phrasal verb）之 part_of_speech 規則同 Vision：**verb (vt)** / **verb (vi)** / **verb (vi/vt)**，片語則 **phrasal verb (vt|vi|vi/vt)**，**不可**僅輸出 "verb"
  - "synonyms": 0～3（無則 []）
  - "usage_patterns": 0～4（無則 []）
  - "example_sentence": **1～2 句**，僅對應本義項，換行 \\n 分隔；**每句**須以 **⟦** 與 **⟧** 包住目標詞或**完整片語**（與句中字形一致，含 -ed/-ing/-s；片語如 account for、accounted for 須整段一對括號內標完；規則同 Vision），每句僅一處；勿輸出 HTML
- **多義項規則（保守）**：**預設 senses 只有 1 筆**。「足夠重要」＝須足以在 **TOEFL／IELTS**、**商用英文**或 **CEFR C2** 場景中各自獨立出現且**不拆開就容易混淆**（如專名 vs 一般義）；否則合併為 1 筆。細微差別請合併在同一義項內。
- **熟詞僻義**：與 Vision 提示相同——常見字若另有 GRE／TOEFL **常考僻義**且與日常義易混，應**分筆 senses** 並各附例句；例如 *dispose*「清除／處置」*dispose of …* vs「使（某人）傾向於」*dispose someone to …*／*disposed to* 一系，兩義皆重要時勿併成單筆而丟僻義（至多 4 筆，排序以使用者輸入與考試重要度為準）。
- **捨棄極冷僻義**：若某義項**僅見於古典文學／詩歌**或**極罕見**現代語境，且**不屬於 TOEFL／GRE 常考或一般學術／現代英語常用範圍**，請**直接省略**，**不要**列入 `senses`，避免增加使用者記憶負擔。
- **順序**：`senses` 須依 **TOEFL／IELTS、商用英文、C2** 的重要性與使用頻率**由高到低**排列；senses[0] 須最符合使用者反白／輸入語境且整體最重要／最常用。

只回傳 JSON，不要任何說明文字或 markdown。"""


def _extract_json_text(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return text.strip()


def _clip_for_log(text: str, max_len: int = 2000) -> str:
    text = str(text or "").strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]} ...<truncated {len(text) - max_len} chars>"


def _decode_words_response(response: object, *, error_key: str, context: str) -> list[dict]:
    raw_text = str(getattr(response, "text", "") or "")
    json_text = _extract_json_text(raw_text)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        log.error("Gemini %s 回傳 JSON 解析失敗：%s", context, exc)
        if raw_text.strip():
            log.error("Gemini %s 原始回應：%s", context, _clip_for_log(raw_text))
        if json_text.strip() and json_text != raw_text:
            log.error("Gemini %s 去除 code fence 後：%s", context, _clip_for_log(json_text))
        raise
    return _normalize_words_payload(parsed, error_key=error_key)


def _synonym_list(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()][:3]
    return []


def _usage_list_from_raw(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()][:4]
    if isinstance(raw, str) and raw.strip():
        return [s.strip() for s in raw.split("\n") if s.strip()][:4]
    return []


def _example_lines_from_raw(raw: object, max_n: int = 2) -> list[str]:
    return [ln.strip() for ln in str(raw or "").splitlines() if ln.strip()][:max_n]


def _normalize_other_senses_for_legacy(word_item: dict) -> None:
    """舊版 other_senses 正規化（無 senses 時與根欄位合併）。"""
    raw = word_item.get("other_senses")
    if not isinstance(raw, list):
        word_item["other_senses"] = []
        return
    cleaned: list[dict] = []
    for x in raw[:4]:
        if not isinstance(x, dict):
            continue
        pos = str(x.get("part_of_speech", "")).strip()
        def_en = str(x.get("definition", "")).strip()
        def_zh = str(x.get("definition_zh", "")).strip()
        if not pos and not def_en and not def_zh:
            continue
        cleaned.append(
            {
                "part_of_speech": pos,
                "definition": def_en,
                "definition_zh": def_zh,
                "synonyms": _synonym_list(x.get("synonyms")),
                "usage_patterns": _usage_list_from_raw(x.get("usage_patterns")),
                "example_sentence": "\n".join(_example_lines_from_raw(x.get("example_sentence"), 2)),
            }
        )
    word_item["other_senses"] = cleaned[:3]


def _normalize_sense_entry(raw: dict) -> dict | None:
    pos = str(raw.get("part_of_speech", "")).strip()
    def_en = str(raw.get("definition", "")).strip()
    def_zh = str(raw.get("definition_zh", "")).strip()
    if not pos and not def_en and not def_zh:
        return None
    lines = _example_lines_from_raw(raw.get("example_sentence"), 2)
    return {
        "part_of_speech": pos,
        "definition": def_en,
        "definition_zh": def_zh,
        "synonyms": _synonym_list(raw.get("synonyms")),
        "usage_patterns": _usage_list_from_raw(raw.get("usage_patterns")),
        "example_sentence": "\n".join(lines),
    }


def _sync_root_from_first_sense(word_item: dict) -> None:
    senses = word_item.get("senses") or []
    if not senses:
        return
    z0 = senses[0]
    word_item["part_of_speech"] = z0.get("part_of_speech", "")
    word_item["definition"] = z0.get("definition", "")
    word_item["definition_zh"] = z0.get("definition_zh", "")
    word_item["synonyms"] = list(z0.get("synonyms") or [])
    word_item["usage_patterns"] = list(z0.get("usage_patterns") or [])
    word_item["example_sentence"] = z0.get("example_sentence", "")


def _normalize_senses(word_item: dict) -> None:
    """建立 senses[]；相容舊版根欄位 + other_senses。"""
    raw_senses = word_item.get("senses")
    senses: list[dict] = []
    if isinstance(raw_senses, list):
        for x in raw_senses[:4]:
            if isinstance(x, dict):
                e = _normalize_sense_entry(x)
                if e:
                    senses.append(e)
    if senses:
        word_item["senses"] = senses
        _sync_root_from_first_sense(word_item)
        word_item["other_senses"] = []
        return

    _normalize_other_senses_for_legacy(word_item)
    primary = _normalize_sense_entry(
        {
            "part_of_speech": word_item.get("part_of_speech", ""),
            "definition": word_item.get("definition", ""),
            "definition_zh": word_item.get("definition_zh", ""),
            "synonyms": word_item.get("synonyms"),
            "usage_patterns": word_item.get("usage_patterns"),
            "example_sentence": word_item.get("example_sentence"),
        }
    )
    if not primary:
        word_item["senses"] = []
        return
    merged: list[dict] = [primary]
    for x in word_item.get("other_senses") or []:
        if isinstance(x, dict):
            e = _normalize_sense_entry(x)
            if e:
                merged.append(e)
    word_item["senses"] = merged[:4]
    _sync_root_from_first_sense(word_item)


def _normalize_words_payload(parsed: object, *, error_key: str) -> list[dict]:
    """
    將模型輸出正規化為 list[dict]，並只保留含有效 word 的項目。
    """
    if isinstance(parsed, dict) and parsed.get("error") == error_key:
        return []

    candidates: list[object] = []
    if isinstance(parsed, list):
        candidates = parsed
    elif isinstance(parsed, dict):
        if isinstance(parsed.get("words"), list):
            candidates = parsed["words"]
        elif parsed.get("word"):
            candidates = [parsed]
    else:
        return []

    normalized: list[dict] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        word = item.get("word")
        if isinstance(word, str) and word.strip():
            _normalize_senses(item)
            normalized.append(item)
    return normalized


def _normalize_model_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    # google-genai 支援 "models/xxx" 格式；也常見直接給 "gemini-2.0-flash"
    if "/" in name:
        return name
    return f"models/{name}"


def _model_error_allows_fallback(exc: Exception) -> bool:
    msg = str(exc)
    needles = [
        "404",
        "NOT_FOUND",
        "is not found for API version",
        "is not supported for generateContent",
        "Call ListModels",
    ]
    return any(n in msg for n in needles)


def _pick_working_model(preferred: str) -> str:
    """
    回傳可用且支援 generateContent 的模型名稱（盡可能使用 preferred）。
    會使用 ListModels 篩選；若 ListModels 失敗則回退到常見穩定型號。
    """
    preferred_norm = _normalize_model_name(preferred)

    try:
        models = list(_client.models.list())
        # google-genai Model 欄位是 supported_actions（包含 "generateContent"）
        supported = [
            m.name
            for m in models
            if getattr(m, "name", None)
            and "generateContent" in (getattr(m, "supported_actions", []) or [])
        ]
        supported_set = set(supported)

        # 先嘗試 preferred（若存在）
        if preferred_norm and preferred_norm in supported_set:
            return preferred_norm

        # 否則依偏好挑選常用 Gemini 型號
        preferred_order = [
            "models/gemini-2.5-flash",
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.5-pro",
            "models/gemini-2.0-flash",
            "models/gemini-2.0-flash-lite",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
        ]
        for name in preferred_order:
            if name in supported_set:
                return name

        # 最後：只要是 gemini* 且可 generateContent 就行（保持 deterministic）
        gemini_supported = sorted(n for n in supported if "/gemini" in n)
        if gemini_supported:
            return gemini_supported[0]
    except Exception:
        pass

    # ListModels 不可用時的保底策略（交給 API 自行解析）
    return preferred_norm or "models/gemini-2.5-flash"


def get_effective_model_name() -> str:
    """提供目前實際使用的模型（含降級後）。"""
    global _resolved_model
    if _resolved_model is None:
        _resolved_model = _pick_working_model(config.GEMINI_MODEL)
    return _resolved_model


def analyze_image(image_path: str) -> list[dict]:
    """
    傳入截圖路徑，回傳解析後的單字清單。
    若模型回傳 IMAGE_UNCLEAR 則回傳空清單。
    """
    image_bytes = pathlib.Path(image_path).read_bytes()

    global _resolved_model

    model_name = get_effective_model_name()
    try:
        response = _client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                types.Part.from_text(text=PROMPT),
            ],
        )
    except Exception as e:
        if not _model_error_allows_fallback(e):
            raise

        preferred = _normalize_model_name(config.GEMINI_MODEL) or config.GEMINI_MODEL
        fallback_candidates = [
            "models/gemini-2.5-flash",
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.5-pro",
            "models/gemini-2.0-flash",
            "models/gemini-2.0-flash-lite",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
        ]

        last_err: Exception = e
        for candidate in fallback_candidates:
            if candidate == preferred:
                continue
            try:
                _resolved_model = candidate
                print(f"[Gemini] 模型不可用，已自動改用：{preferred} -> {candidate}")
                response = _client.models.generate_content(
                    model=candidate,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        types.Part.from_text(text=PROMPT),
                    ],
                )
                break
            except Exception as e2:
                last_err = e2
        else:
            raise last_err
    return _decode_words_response(response, error_key="IMAGE_UNCLEAR", context="image")


def analyze_text(text_input: str) -> list[dict]:
    """
    傳入剪貼簿文字，回傳 0 或 1 筆單字卡資料（list[dict]）。
    若模型回傳 NOT_A_WORD 則回傳空清單。
    """
    global _resolved_model

    model_name = get_effective_model_name()
    try:
        response = _client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_text(text=TEXT_PROMPT),
                types.Part.from_text(text=f"Clipboard text:\n{text_input}"),
            ],
        )
    except Exception as e:
        if not _model_error_allows_fallback(e):
            raise

        preferred = _normalize_model_name(config.GEMINI_MODEL) or config.GEMINI_MODEL
        fallback_candidates = [
            "models/gemini-2.5-flash",
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.5-pro",
        ]

        last_err: Exception = e
        for candidate in fallback_candidates:
            if candidate == preferred:
                continue
            try:
                _resolved_model = candidate
                print(f"[Gemini] 模型不可用，已自動改用：{preferred} -> {candidate}")
                response = _client.models.generate_content(
                    model=candidate,
                    contents=[
                        types.Part.from_text(text=TEXT_PROMPT),
                        types.Part.from_text(text=f"Clipboard text:\n{text_input}"),
                    ],
                )
                break
            except Exception as e2:
                last_err = e2
        else:
            raise last_err

    return _decode_words_response(response, error_key="NOT_A_WORD", context="text")
