import glob
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
MAX_TERM_LENGTH = 24
MAX_SPACE_SEPARATED_WORDS = 6
EXCLUDED_KEY_TOKENS = (
    "color",
    "theme",
    "configuration",
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
ACTIONABLE_UI_PATH_PREFIXES = (
    "vs/platform/menubar/",
    "vs/workbench/browser/actions/helpActions",
    "vs/workbench/browser/actions/workspaceActions",
    "vs/workbench/contrib/preferences/browser/preferences.contribution",
    "vs/workbench/contrib/terminal/browser/terminal.contribution",
    "vs/workbench/contrib/terminal/browser/terminalMenus",
    "vs/workbench/contrib/externalTerminal/browser/externalTerminal.contribution",
    "vs/workbench/contrib/externalTerminal/electron-browser/externalTerminal.contribution",
    "vs/workbench/contrib/files/browser/fileActions",
    "vs/workbench/contrib/files/browser/views/explorerView",
    "vs/workbench/contrib/files/electron-browser/fileActions.contribution",
    "extensions/vscode.git/package",
    "extensions/vscode.git-base/package",
)
ACTIONABLE_UI_EXCLUDED_KEY_TOKENS = (
    "accessibility",
    "aria",
    "background",
    "badge",
    "border",
    "category",
    "color",
    "config",
    "configuration",
    "confirm",
    "count",
    "decorations",
    "description",
    "detail",
    "enabled",
    "error",
    "foreground",
    "icon",
    "metadata",
    "placeholder",
    "status",
    "titlebar",
    "tooltip",
    "visible",
    "warning",
)
EXPLORER_FILE_ACTION_KEYS = {
    "copyfile",
    "download",
    "newfile",
    "newfolder",
    "pastefile",
    "upload",
}
EXPLORER_CONTRIBUTION_KEYS = {
    "copypath",
    "copypathofactive",
    "copyrelativepath",
    "copyrelativepathofactive",
    "cut",
    "deletefile",
    "exploreropenwith",
    "misave",
    "misaveas",
    "newfile",
    "opentoside",
    "revert",
    "revertlocalchanges",
    "saveall",
    "savefiles",
}
EXPLORER_VIEW_KEYS = {
    "collapseexplorerfolders",
    "refreshexplorer",
}
EXPLORER_ELECTRON_KEYS = {
    "mishare",
    "opencontainer",
}
GIT_MENU_KEYS = {
    "command.addremote",
    "command.branch",
    "command.branchfrom",
    "command.checkout",
    "command.checkoutdetached",
    "command.cherrypick",
    "command.cherrypickabort",
    "command.clean",
    "command.cleanall",
    "command.cleanalltracked",
    "command.cleanalluntracked",
    "command.clone",
    "command.clonerecursive",
    "command.commit",
    "command.commitall",
    "command.commitallamend",
    "command.commitallamendnoverify",
    "command.commitallnoverify",
    "command.commitallsignednoverify",
    "command.commitamend",
    "command.commitamendnoverify",
    "command.commitempty",
    "command.commitemptynoverify",
    "command.commitnoverify",
    "command.commitsigned",
    "command.commitsignednoverify",
    "command.commitstaged",
    "command.commitstagedamend",
    "command.commitstagedamendnoverify",
    "command.commitstagednoverify",
    "command.commitstagedsigned",
    "command.createfrom",
    "command.createtag",
    "command.delete",
    "command.deletebranch",
    "command.deleteremotebranch",
    "command.deleteremotetag",
    "command.deletetag",
    "command.fetch",
    "command.fetchall",
    "command.init",
    "command.merge",
    "command.mergeabort",
    "command.openchange",
    "command.openfile",
    "command.publish",
    "command.pull",
    "command.pullfrom",
    "command.pullrebase",
    "command.push",
    "command.pushfollowtags",
    "command.pushfollowtagsforce",
    "command.pushforce",
    "command.pushtags",
    "command.pushto",
    "command.pushtoforce",
    "command.rebase",
    "command.rebase2",
    "command.rebaseabort",
    "command.refresh",
    "command.removeremote",
    "command.rename",
    "command.renamebranch",
    "command.revealinexplorer",
    "command.revertchange",
    "command.revertselectedranges",
    "command.stage",
    "command.stageall",
    "command.stageallmerge",
    "command.stagealltracked",
    "command.stagealluntracked",
    "command.stageblock",
    "command.stagechange",
    "command.stageselectedranges",
    "command.stageselection",
    "command.stash",
    "command.stashapply",
    "command.stashapplylatest",
    "command.stashdrop",
    "command.stashdropall",
    "command.stashincludeuntracked",
    "command.stashpop",
    "command.stashpoplatest",
    "command.stashstaged",
    "command.sync",
    "command.undocommit",
    "command.unstage",
    "command.unstageall",
    "command.unstagechange",
    "command.unstageselectedranges",
    "submenu.branch",
    "submenu.changes",
    "submenu.remote",
    "submenu.stash",
    "submenu.tags",
}
LOW_VALUE_STATE_WORDS = {
    "現在", "既定", "既定値", "既定の", "進行中", "完了", "無効", "有効", "表示中", "読み込み中",
    "ローカル", "メイン", "空", "標準", "既存", "最近", "詳細情報", "アクティブ", "プレビュー", "モード",
    "形式", "種類", "名前", "タイトル", "パス", "ビュー", "セクション", "グループ", "パネル", "メニュー",
    "エディター", "ターミナル", "拡張機能", "言語モデル", "ワークスペース", "プロファイル",
}

kks = pykakasi.kakasi()

LANGUAGE_PACK_ROOTS = (
    os.path.join(os.path.expanduser("~"), ".vscode", "extensions"),
    os.path.join(os.path.expanduser("~"), ".vscode-insiders", "extensions"),
)
GIT_LANGUAGE_PACK_EXTENSIONS = (
    "vscode.git",
    "vscode.git-base",
)

def load_core_contents(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return raw.get("contents", {})

def find_latest_language_pack_translation(locale, extension_name):
    matches = []
    for root in LANGUAGE_PACK_ROOTS:
        pattern = os.path.join(
            root,
            f"ms-ceintl.vscode-language-pack-{locale}-*",
            "translations",
            "extensions",
            f"{extension_name}.i18n.json",
        )
        matches.extend(glob.glob(pattern))

    if not matches:
        return None

    return sorted(matches)[-1]

def load_extension_contents(file_path, extension_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    contents = raw.get("contents", {})
    normalized = {}
    for section_name, items in contents.items():
        if isinstance(items, dict):
            normalized[f"extensions/{extension_name}/{section_name}"] = items

    return normalized

def load_optional_git_extension_contents():
    ja_contents = {}
    zh_contents = {}

    for extension_name in GIT_LANGUAGE_PACK_EXTENSIONS:
        ja_file = find_latest_language_pack_translation("ja", extension_name)
        zh_file = find_latest_language_pack_translation("zh-hans", extension_name)

        if not ja_file or not zh_file:
            continue

        ja_contents.update(load_extension_contents(ja_file, extension_name))
        zh_contents.update(load_extension_contents(zh_file, extension_name))

    return ja_contents, zh_contents

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

def strip_trailing_parenthetical_suffix(text):
    stripped = text.strip()

    while True:
        updated = re.sub(r'\s*[（(][^（）()]+[）)]\s*$', '', stripped).strip()
        if updated == stripped or not updated:
            break
        stripped = updated

    return stripped

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
    text = strip_trailing_parenthetical_suffix(text)
    return normalize_whitespace(text)

def normalize_for_dedupe(text):
    text = clean_text(text)
    text = re.sub(r'[\s、。,.:：;；!?！？…･・/／|｜\-−_"\'()（）\[\]【】]+', '', text)
    return text.lower()

def is_latin_only_term(text):
    return bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9 .+\-_/]*', text))

def contains_latin_letters(text):
    return bool(re.search(r'[A-Za-z]', text))

def is_actionable_ui_path(path):
    path_lower = path.lower()
    return any(path_lower.startswith(prefix.lower()) for prefix in ACTIONABLE_UI_PATH_PREFIXES)

def is_actionable_ui_key(path, key):
    key_lower = key.lower()
    path_lower = path.lower()

    if any(token in key_lower for token in ACTIONABLE_UI_EXCLUDED_KEY_TOKENS):
        return False

    if path_lower.startswith("vs/platform/menubar/"):
        return key.startswith(("m", "mi")) or key_lower in {
            "newwindow",
            "openrecent",
            "reloadwindow",
            "togglefullscreen",
        }

    if path_lower.startswith("vs/workbench/browser/actions/helpactions"):
        return key.startswith("mi")

    if path_lower.startswith("vs/workbench/browser/actions/workspaceactions"):
        return key.startswith("mi") or key_lower in {
            "closeworkspace",
            "duplicateworkspace",
            "duplicateworkspaceinnewwindow",
            "globalremovefolderfromworkspace",
            "openfile",
            "openfolder",
            "workspaces",
        }

    if path_lower.startswith("vs/workbench/contrib/preferences/browser/preferences.contribution"):
        return key_lower in {
            "settings",
            "mipreferences",
            "keyboardshortcuts",
            "miopenonlinesettings",
            "openfoldersettings",
            "openglobalkeybindings",
            "openglobalsettings",
            "openremotesettings",
            "openworkspacesettings",
        }

    if path_lower.startswith("vs/workbench/contrib/terminal/browser/terminal.contribution"):
        return key_lower in {"mitoggleintegratedterminal", "terminal"}

    if path_lower.startswith("vs/workbench/contrib/terminal/browser/terminalmenus"):
        return key.startswith("mi") or key.startswith("workbench.action.") or key_lower in {
            "defaultterminalprofile",
            "launchprofile",
            "split.profile",
        }

    if path_lower.startswith("vs/workbench/contrib/externalterminal/browser/externalterminal.contribution"):
        return key_lower in {"scopedconsoleaction.integrated", "scopedconsoleaction.external"}

    if path_lower.startswith("vs/workbench/contrib/externalterminal/electron-browser/externalterminal.contribution"):
        return key_lower in {"globalconsoleaction"}

    if path_lower.startswith(("extensions/vscode.git/package", "extensions/vscode.git-base/package")):
        return key_lower in GIT_MENU_KEYS

    if path_lower.startswith("vs/workbench/contrib/files/browser/fileactions"):
        return key_lower in EXPLORER_FILE_ACTION_KEYS

    if path_lower.startswith("vs/workbench/contrib/files/browser/views/explorerview"):
        return key_lower in EXPLORER_VIEW_KEYS

    if path_lower.startswith("vs/workbench/contrib/files/electron-browser/fileactions.contribution"):
        return key_lower in EXPLORER_ELECTRON_KEYS

    if path_lower.startswith("vs/workbench/contrib/files/browser/fileactions.contribution"):
        return key_lower in EXPLORER_CONTRIBUTION_KEYS

    return True

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

    if is_actionable_ui_path(full_key.rsplit('/', 1)[0]):
        return False

    if text in LOW_VALUE_STATE_WORDS:
        return True

    if any(ch in text for ch in '()（）'):
        return True

    if len(text) <= 3 and "通用 (General)" in get_location_hint(full_key):
        return True

    return False

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
    if "scm" in key_lower: return "源代码管理 (SCM)"
    if "explorer" in key_lower or "/files/" in key_lower: return "资源管理器操作 (Explorer)"
    if "menu" in key_lower: return "菜单 (Menu)"
    if "view" in key_lower or "sidebar" in key_lower: return "侧边栏 (Sidebar)"
    if "terminal" in key_lower: return "终端 (Terminal)"
    if "debug" in key_lower: return "调试 (Debug)"
    if "editor" in key_lower: return "编辑器 (Editor)"
    if "extension" in key_lower: return "扩展 (Extension)"
    return "通用 (General)"

def is_important_ui(path, key, value):
    """操作に直結するメニュー項目・コンテキストメニューを優先する"""
    if not is_actionable_ui_path(path):
        return False
    if not is_actionable_ui_key(path, key):
        return False
    if re.search(r'[\r\n]', value):
        return False
    if re.search(r'https?://|www\.|<[^>]+>|`', value):
        return False

    text = clean_text(value)
    if not text:
        return False
    if len(text) > MAX_TERM_LENGTH:
        return False
    if re.search(r'[。！？!?]', text):
        return False

    return True

def generate():
    if not os.path.exists(JA_FILE) or not os.path.exists(ZH_FILE):
        print("エラー: data/raw/ 内に ja.json と zh.json が見つかりません。")
        return

    print("データを読み込み中...")
    core_ja_contents = load_core_contents(JA_FILE)
    core_zh_contents = load_core_contents(ZH_FILE)

    datasets = [
        ("vscode", core_ja_contents, core_zh_contents),
    ]

    git_ja_contents, git_zh_contents = load_optional_git_extension_contents()
    if git_ja_contents and git_zh_contents:
        datasets.append(("vscode-git", git_ja_contents, git_zh_contents))
        print("Git 言語パックも読み込みました。")
    else:
        print("Git 言語パックは見つからなかったため、コア翻訳のみで生成します。")

    best_entries = {}
    skipped_long_or_noisy = 0
    duplicate_updates = 0
    skipped_low_learning_value = 0

    print("変換を開始します (強化クレンジング + 重複統合)...")

    for source_name, ja_contents, zh_contents in datasets:
        for path, ja_items in ja_contents.items():
            zh_items = zh_contents.get(path, {})
        
            for key, ja_val in ja_items.items():
                if key in zh_items:
                    zh_val = zh_items[key]

                    if not is_important_ui(path, key, ja_val):
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
                        "source": source_name,
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

    best_entries_by_zh = {}
    for item in best_entries.values():
        entry = item["entry"]
        canonical_zh = normalize_for_dedupe(entry["zh"])
        existing = best_entries_by_zh.get(canonical_zh)

        if existing is None or item["score"] < existing["score"]:
            if existing is not None:
                duplicate_updates += 1
            best_entries_by_zh[canonical_zh] = item

    dictionary = [item["entry"] for item in best_entries_by_zh.values()]

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