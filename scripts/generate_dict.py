import json
import os
import re
from pypinyin import pinyin, Style
import pykakasi

# --- 設定 ---
RAW_DATA_DIR = "data/raw"
OUTPUT_FILE = "data/dictionary.json"
JA_FILE = os.path.join(RAW_DATA_DIR, "ja.json")
ZH_FILE = os.path.join(RAW_DATA_DIR, "zh.json")
MAX_TERM_LENGTH = 10
MAX_SPACE_SEPARATED_WORDS = 5
EXCLUDED_KEY_TOKENS = (
    "color",
    "theme",
    "configuration",
    "setting",
    "icon",
    "telemetry",
    "accessibilitysignal",
    "snippetvariables",
    "date.fromnow",
    "duration.",
    "size",
    "keybindinglabels",
    "speechlanguage",
)
LOW_VALUE_STATE_WORDS = {
    "現在", "既定", "既定値", "既定の", "進行中", "完了", "無効", "有効", "表示中", "読み込み中",
    "ローカル", "メイン", "空", "標準", "既存", "最近", "詳細情報", "アクティブ", "プレビュー", "モード",
    "形式", "種類", "名前", "タイトル", "パス", "ビュー", "セクション", "グループ", "パネル", "メニュー",
    "エディター", "ターミナル", "拡張機能", "言語モデル", "ワークスペース", "プロファイル",
}
SHORT_ACTION_ALLOWLIST = {
    "開く", "閉じる", "保存", "コピー", "貼り付け", "切り取り", "元に戻す", "やり直し",
    "検索", "置換", "実行", "停止", "開始", "更新", "削除", "追加", "選択", "移動",
    "戻る", "進む", "承諾", "拒否", "共有", "表示", "非表示", "折りたたみ", "展開",
}
ACTION_PHRASE_PATTERNS = (
    r".+を.+(する|します|した|して)$",
    r".+(に|へ)移動$",
    r".+(を)?(表示|切り替え|選択|開く|閉じる|保存|実行|開始|停止|追加|削除|コピー|貼り付け|並べ替え|検索|折りたたみ|展開)$",
)

kks = pykakasi.kakasi()

def normalize_whitespace(text):
    text = text.replace('\u3000', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def strip_wrapping_brackets(text):
    pairs = [('(', ')'), ('（', '）'), ('[', ']'), ('【', '】')]
    stripped = text.strip()

    changed = True
    while changed:
        changed = False
        for open_bracket, close_bracket in pairs:
            if stripped.startswith(open_bracket) and stripped.endswith(close_bracket):
                inner = stripped[1:-1].strip()
                if inner:
                    stripped = inner
                    changed = True
                    break

    return stripped

def remove_unbalanced_brackets(text):
    pairs = [('(', ')'), ('（', '）'), ('[', ']'), ('【', '】')]

    for open_bracket, close_bracket in pairs:
        if text.count(open_bracket) != text.count(close_bracket):
            text = text.replace(open_bracket, ' ').replace(close_bracket, ' ')

    return normalize_whitespace(text)

def clean_text(text):
    """UI ラベルに不要なノイズを取り除き、比較しやすい形に整える"""
    if not text:
        return ""

    text = re.sub(r'[\r\n\t]+', ' ', text.strip())
    text = re.sub(r'\s*\(&{1,2}.\)\s*', '', text)
    text = re.sub(r'\s*（&{1,2}.）\s*', '', text)
    text = text.replace('&&', '').replace('&', '')
    text = re.sub(r'\{\d+\}', '', text)
    text = re.sub(r'%\d+', '', text)
    text = re.sub(r'\$\{?\d+\}?', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[[^\]]*\]\([^)]+\)', '', text)
    text = normalize_whitespace(text)
    text = strip_wrapping_brackets(text)
    text = re.sub(r'\(([%$\d\s]+)\)', '', text)
    text = re.sub(r'（([%$\d\s]+)）', '', text)
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'（\s*）', '', text)
    text = remove_unbalanced_brackets(text)
    text = re.sub(r'\s*[:：]\s*$', '', text)
    text = text.strip('、。,.:：;；!?！？…･・/／|｜-−_"\' ')
    text = strip_wrapping_brackets(text)
    return normalize_whitespace(text)

def normalize_for_dedupe(text):
    text = clean_text(text)
    text = re.sub(r'[\s、。,.:：;；!?！？…･・/／|｜\-−_"\'()（）\[\]【】]+', '', text)
    return text.lower()

def is_latin_only_term(text):
    return bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9 .+\-_/]*', text))

def contains_latin_letters(text):
    return bool(re.search(r'[A-Za-z]', text))

def is_learning_term(text, original_text):
    """単語学習向けに短く意味のあるラベルだけを残す"""
    has_placeholder = bool(re.search(r'\{\d+\}|%\d+|\$\{?\d+\}?', original_text))

    if not text:
        return False
    if len(text) > MAX_TERM_LENGTH:
        return False
    if len(text.split()) > MAX_SPACE_SEPARATED_WORDS:
        return False
    if re.search(r'[\r\n]', original_text):
        return False
    if re.search(r'https?://|www\.|<[^>]+>|`', original_text):
        return False
    if re.search(r'[。！？!?]', text):
        return False
    if re.search(r'[%$&]', text):
        return False
    if contains_latin_letters(text):
        return False
    if is_latin_only_term(text):
        return False
    if not re.search(r'[A-Za-z0-9\u3040-\u30FF\u4E00-\u9FFF]', text):
        return False
    if has_placeholder and re.search(r'[()（）\[\]【】]', text):
        return False
    if has_placeholder and re.search(r'(合計|件中|個のうち|表示中|平均|第)', text):
        return False
    if has_placeholder and (
        text.startswith(('の', 'を', 'に', 'へ', 'と', 'で', 'が', 'は', '件', '個', '第', '个', '页'))
        or text.endswith(('の', 'を', 'に', 'へ', 'と', 'で', 'が', 'は', '件', '個', '个', '页'))
    ):
        return False
    return True

def is_low_learning_value(full_key, text):
    key_lower = full_key.lower()

    if any(token in key_lower for token in EXCLUDED_KEY_TOKENS):
        return True

    if text in LOW_VALUE_STATE_WORDS:
        return True

    if any(ch in text for ch in '()（）'):
        return True

    if len(text) <= 3 and "通用 (General)" in get_location_hint(full_key):
        return True

    if text in SHORT_ACTION_ALLOWLIST:
        return False

    return any(re.fullmatch(pattern, text) for pattern in ACTION_PHRASE_PATTERNS)

def score_entry(entry):
    return (
        entry["category"] == "通用 (General)",
        len(entry["ja"]),
        len(entry["zh"]),
        len(entry["key"]),
    )

def get_pinyin(text):
    """中国語のピンイン（記号付き）を取得"""
    # Style.TONE を使用して記号付き (例: nǐ hǎo) に変更
    res = pinyin(text, style=Style.TONE)
    return " ".join([item[0] for item in res])

def get_kana(text):
    """日本語の読み仮名を取得"""
    result = kks.convert(text)
    return "".join([item['kana'] for item in result])

def get_location_hint(key):
    """キー名からUI上の場所を推測"""
    key_lower = key.lower()
    if "menu" in key_lower: return "菜单 (Menu)"
    if "view" in key_lower or "sidebar" in key_lower: return "侧边栏 (Sidebar)"
    if "terminal" in key_lower: return "终端 (Terminal)"
    if "debug" in key_lower: return "调试 (Debug)"
    if "editor" in key_lower: return "编辑器 (Editor)"
    if "extension" in key_lower: return "扩展 (Extension)"
    return "通用 (General)"

def is_important_ui(key, value):
    """一軍の単語かどうかを判定"""
    if re.search(r'[\r\n]', value):
        return False
    if re.search(r'https?://|www\.|<[^>]+>|`', value):
        return False
    # ショートカットキー指定があるものはUI確定
    if '&&' in value: return True
    # 短いラベル
    if len(clean_text(value)) <= 10: return True
    # 特定のキーワード
    important_suffixes = ('.label', '.title', '.name', '.caption', 'Label', 'Title', 'Name')
    if any(key.endswith(s) for s in important_suffixes): return True
    if "menu" in key.lower(): return True
    return False

def generate():
    if not os.path.exists(JA_FILE) or not os.path.exists(ZH_FILE):
        print("エラー: data/raw/ 内に ja.json と zh.json が見つかりません。")
        return

    print("データを読み込み中...")
    with open(JA_FILE, 'r', encoding='utf-8') as f:
        ja_raw = json.load(f)
    with open(ZH_FILE, 'r', encoding='utf-8') as f:
        zh_raw = json.load(f)

    ja_contents = ja_raw.get("contents", {})
    zh_contents = zh_raw.get("contents", {})

    best_entries = {}
    skipped_long_or_noisy = 0
    duplicate_updates = 0
    skipped_low_learning_value = 0

    print("変換を開始します (強化クレンジング + 重複統合)...")
    
    for path, ja_items in ja_contents.items():
        zh_items = zh_contents.get(path, {})
        
        for key, ja_val in ja_items.items():
            if key in zh_items:
                zh_val = zh_items[key]
                
                if not is_important_ui(key, ja_val):
                    continue

                ja_clean = clean_text(ja_val)
                zh_clean = clean_text(zh_val)

                if not is_learning_term(ja_clean, ja_val) or not is_learning_term(zh_clean, zh_val):
                    skipped_long_or_noisy += 1
                    continue

                canonical_ja = normalize_for_dedupe(ja_clean)
                canonical_zh = normalize_for_dedupe(zh_clean)

                if not canonical_ja or not canonical_zh:
                    continue

                full_key = f"{path}/{key}"

                if is_low_learning_value(full_key, ja_clean):
                    skipped_low_learning_value += 1
                    continue

                entry = {
                    "ja": ja_clean,
                    "ja_read": get_kana(ja_clean),
                    "zh": zh_clean,
                    "pinyin": get_pinyin(zh_clean),
                    "category": get_location_hint(full_key),
                    "source": "vscode",
                    "key": full_key
                }
                candidate_score = score_entry(entry)
                existing = best_entries.get(canonical_ja)

                if existing is None or candidate_score < existing["score"]:
                    if existing is not None:
                        duplicate_updates += 1
                    best_entries[canonical_ja] = {
                        "entry": entry,
                        "score": candidate_score,
                    }

    dictionary = [item["entry"] for item in best_entries.values()]

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)

    print(
        f"完了！ {len(dictionary)} 件の単語を抽出しました。"
        f" 除外: {skipped_long_or_noisy} 件 / 学習優先度で除外: {skipped_low_learning_value} 件"
        f" / 重複統合で更新: {duplicate_updates} 件"
    )

if __name__ == "__main__":
    generate()