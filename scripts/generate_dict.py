import json
import os
from pypinyin import pinyin, Style
from pykakasi import kakasi

# ひらがな変換の初期化
kks = kakasi()

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def flatten_contents(data):
    flat_dict = {}
    contents = data.get("contents", {})
    for path, items in contents.items():
        for key, value in items.items():
            full_key = f"{path}.{key}"
            flat_dict[full_key] = value
    return flat_dict

def get_pinyin(text):
    res = pinyin(text, style=Style.TONE)
    return " ".join([item[0] for item in res])

def get_furigana(text):
    result = kks.convert(text)
    return "".join([item['hira'] for item in result])

def clean_text(text):
    """ VS Code特有の記号を除去 """
    return text.replace("&&", "").replace("&", "")

def get_metadata(full_key):
    """ パスから英語カテゴリと優先度を決定する """
    # 優先度1: Core UI / Editor Actions
    if any(p in full_key for p in ["ui/dialog", "ui/button", "editorExtensions", "clipboard", "actionbar"]):
        return 1, "Core UI"
    # 優先度2: Major Features
    elif "debug" in full_key:
        return 2, "Debug"
    elif "terminal" in full_key:
        return 2, "Terminal"
    elif "scm" in full_key:
        return 2, "Git / SCM"
    elif "chat" in full_key or "inlineChat" in full_key:
        return 2, "AI Chat"
    elif "search" in full_key:
        return 2, "Search"
    elif "notebook" in full_key:
        return 2, "Notebook"
    # 優先度3: System / Config
    elif "configuration" in full_key or "settings" in full_key:
        return 3, "Settings"
    elif "extensions" in full_key:
        return 3, "Extensions"
    else:
        return 3, "System"

def main():
    ja_path = 'data/raw/ja.json'
    ch_path = 'data/raw/ch.json'
    output_path = 'data/dictionary.json'

    if not os.path.exists(ja_path) or not os.path.exists(ch_path):
        print("Error: Please place ja.json and ch.json in data/raw/")
        return

    print("Processing files...")
    ja_flat = flatten_contents(load_json(ja_path))
    ch_flat = flatten_contents(load_json(ch_path))

    dictionary = []
    seen_pairs = set()

    for key, ja_raw in ja_flat.items():
        if key in ch_flat:
            ja_text = clean_text(ja_raw)
            ch_text = clean_text(ch_flat[key])
            
            # --- フィルタリング ---
            if "{" in ja_text or ja_text.lower() == ch_text.lower(): continue
            if len(ja_text) < 2 or len(ja_text) > 25: continue
            
            pair = (ja_text, ch_text)
            if pair in seen_pairs: continue
            seen_pairs.add(pair)
            
            # メタデータ取得
            priority, category = get_metadata(key)
            
            dictionary.append({
                "ja": ja_text,
                "ja_read": get_furigana(ja_text),
                "zh": ch_text,
                "pinyin": get_pinyin(ch_text),
                "priority": priority,
                "category": category,
                "source": "VS Code"
            })

    # 優先度順に並び替えて保存
    dictionary.sort(key=lambda x: x['priority'])

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)
    
    print(f"Success! {len(dictionary)} items saved to {output_path}")

if __name__ == "__main__":
    main()