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

kks = pykakasi.kakasi()

def clean_text(text):
    """ノイズ（ショートカットキー、プレースホルダー）を除去"""
    # 1. (&&T) や && を除去
    text = re.sub(r'\(&&.\)', '', text)
    text = text.replace('&&', '')
    # 2. {0} や {1} などのプレースホルダーを除去
    text = re.sub(r'\{\d+\}', '', text)
    # 3. 文頭・文末の句読点ノイズ（、や。）を掃除
    text = text.strip('、。,. ')
    return text

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
    # ショートカットキー指定があるものはUI確定
    if '&&' in value: return True
    # 短いラベル
    if len(value) <= 10 and not any(char in value for char in ["\n"]): return True
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

    dictionary = []
    seen_ja = set()

    print("変換を開始します (プレースホルダー除去 & ピンイン記号版)...")
    
    for path, ja_items in ja_contents.items():
        zh_items = zh_contents.get(path, {})
        
        for key, ja_val in ja_items.items():
            if key in zh_items:
                zh_val = zh_items[key]
                
                if not is_important_ui(key, ja_val) or len(ja_val) > 25:
                    continue

                # ノイズ（&&T や {0}）を除去
                ja_clean = clean_text(ja_val)
                zh_clean = clean_text(zh_val)

                # 空っぽになったり重複したりしたものはスキップ
                if not ja_clean or ja_clean in seen_ja:
                    continue

                # 漢字やひらがなを含まない記号のみのデータを除外
                if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', ja_clean):
                    continue

                full_key = f"{path}/{key}"
                dictionary.append({
                    "ja": ja_clean,
                    "ja_read": get_kana(ja_clean),
                    "zh": zh_clean,
                    "pinyin": get_pinyin(zh_clean),
                    "category": get_location_hint(full_key),
                    "source": "vscode",
                    "key": full_key
                })
                seen_ja.add(ja_clean)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)

    print(f"完了！ {len(dictionary)} 件の洗練された単語を抽出しました。")

if __name__ == "__main__":
    generate()