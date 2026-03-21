/**
 * code-vocabs: IT用語学習アプリ (日中ハイブリッド学習版)
 */

let dictionary = [];
let filteredList = [];
let currentIndex = -1;
let autoPlayTimeout = null;
let isFlipped = false;

const cardInner = document.getElementById('cardInner');
const autoPlayToggle = document.getElementById('autoPlayToggle');
const sourceContainer = document.getElementById('sourceFilters');
const categoryContainer = document.getElementById('categoryFilters');
const reviewModeToggle = document.getElementById('reviewModeToggle');
const userTypeSelect = document.getElementById('userType');

async function init() {
    try {
        const res = await fetch('../data/dictionary.json');
        if (!res.ok) throw new Error('Fetch failed');
        dictionary = await res.json();
        
        createFilters('source', sourceContainer, 'src-filter');
        createFilters('category', categoryContainer, 'cat-filter');
        updateFilter();
        showNext();
    } catch (e) {
        console.error(e);
        document.getElementById('frontText').innerText = "DATA ERROR";
    }
}

// フィルタUIの動的作成用共通関数
function createFilters(key, container, className) {
    const values = [...new Set(dictionary.map(item => item[key]))];
    container.innerHTML = '';
    values.forEach(val => {
        const label = document.createElement('label');
        label.className = "flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200 text-[10px] font-black cursor-pointer hover:bg-indigo-50 transition-all select-none border-indigo-500 text-indigo-600";
        label.innerHTML = `<input type="checkbox" class="${className}" value="${val}" checked> ${val.toUpperCase()}`;
        container.appendChild(label);
        
        label.querySelector('input').addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            label.classList.toggle('border-indigo-500', isChecked);
            label.classList.toggle('text-indigo-600', isChecked);
            updateFilter();
            showNext();
        });
    });
}

function updateFilter() {
    const selectedSrcs = Array.from(document.querySelectorAll('.src-filter:checked')).map(el => el.value);
    const selectedCats = Array.from(document.querySelectorAll('.cat-filter:checked')).map(el => el.value);
    const marked = JSON.parse(localStorage.getItem('markedWords') || '[]');
    const isReviewMode = reviewModeToggle.checked;

    filteredList = dictionary.filter(item => {
        const srcMatch = selectedSrcs.includes(item.source);
        const catMatch = selectedCats.includes(item.category);
        const baseMatch = srcMatch && catMatch;
        return isReviewMode ? (baseMatch && marked.includes(item.ja)) : baseMatch;
    });

    const statusEl = document.getElementById('status');
    if (statusEl) statusEl.innerText = (isReviewMode && filteredList.length === 0) ? "EMPTY" : `${filteredList.length} WORDS`;
}

function showNext() {
    if (filteredList.length === 0) {
        document.getElementById('frontText').innerText = "EMPTY";
        document.getElementById('frontRead').innerText = "";
        return;
    }
    
    isFlipped = false;
    cardInner.classList.remove('is-flipped');
    
    currentIndex = Math.floor(Math.random() * filteredList.length);
    const item = filteredList[currentIndex];
    const mode = userTypeSelect.value;

    document.getElementById('cardCategory').innerText = item.category;

    if (mode === 'ja-learner') {
        document.getElementById('frontRead').innerText = item.pinyin;
        document.getElementById('frontText').innerText = item.zh;
        document.getElementById('backRead').innerText = item.ja_read;
        document.getElementById('backText').innerText = item.ja;
        speak(item.zh, 'zh-CN');
    } else {
        document.getElementById('frontRead').innerText = item.ja_read;
        document.getElementById('frontText').innerText = item.ja;
        document.getElementById('backRead').innerText = item.pinyin;
        document.getElementById('backText').innerText = item.zh;
        speak(item.ja, 'ja-JP');
    }

    updateMarkButton(item.ja);
}

function updateMarkButton(jaWord) {
    const marked = JSON.parse(localStorage.getItem('markedWords') || '[]');
    const isMarked = marked.includes(jaWord);
    const markBtn = document.getElementById('markBtn');
    document.getElementById('markIcon').innerText = isMarked ? "✅" : "⚠️";
    document.getElementById('markText').innerText = isMarked ? "LEARNED" : "MARK";
    markBtn.classList.toggle('text-orange-500', isMarked);
    markBtn.classList.toggle('border-orange-200', isMarked);
}

function speak(text, lang) {
    return new Promise((resolve) => {
        window.speechSynthesis.cancel();
        const uttr = new SpeechSynthesisUtterance(text);
        uttr.lang = lang;
        uttr.rate = 0.85;
        uttr.onend = resolve;
        uttr.onerror = resolve;
        window.speechSynthesis.speak(uttr);
    });
}

async function startAutoPlay() {
    autoPlayToggle.innerText = "STOP";
    autoPlayToggle.classList.replace('bg-slate-800', 'bg-red-500');

    while (autoPlayToggle.innerText === "STOP") {
        if (filteredList.length === 0) break;
        const item = filteredList[currentIndex];
        const mode = userTypeSelect.value;

        // 1. 表面読み上げ
        const frontLang = mode === 'ja-learner' ? 'zh-CN' : 'ja-JP';
        const frontText = mode === 'ja-learner' ? item.zh : item.ja;
        await speak(frontText, frontLang);
        
        await new Promise(r => autoPlayTimeout = setTimeout(r, 1200));
        if (autoPlayToggle.innerText !== "STOP") break;

        // 2. 反転 & 裏面読み上げ
        isFlipped = true;
        cardInner.classList.add('is-flipped');
        const backLang = mode === 'ja-learner' ? 'ja-JP' : 'zh-CN';
        const backText = mode === 'ja-learner' ? item.ja : item.zh;
        await speak(backText, backLang);

        await new Promise(r => autoPlayTimeout = setTimeout(r, 2500));
        if (autoPlayToggle.innerText !== "STOP") break;

        showNext();
    }
}

function stopAutoPlay() {
    autoPlayToggle.innerText = "START";
    autoPlayToggle.classList.replace('bg-red-500', 'bg-slate-800');
    clearTimeout(autoPlayTimeout);
    window.speechSynthesis.cancel();
}

// イベントリスナー
document.getElementById('nextBtn').addEventListener('click', () => {
    if (autoPlayToggle.innerText === "STOP") stopAutoPlay();
    showNext();
});

cardInner.addEventListener('click', () => {
    if (autoPlayToggle.innerText === "STOP") stopAutoPlay();
    isFlipped = !isFlipped;
    cardInner.classList.toggle('is-flipped');
    const item = filteredList[currentIndex];
    const mode = userTypeSelect.value;
    if (isFlipped) mode === 'ja-learner' ? speak(item.ja, 'ja-JP') : speak(item.zh, 'zh-CN');
    else mode === 'ja-learner' ? speak(item.zh, 'zh-CN') : speak(item.ja, 'ja-JP');
});

autoPlayToggle.addEventListener('click', () => {
    autoPlayToggle.innerText === "STOP" ? stopAutoPlay() : startAutoPlay();
});

reviewModeToggle.addEventListener('change', () => { updateFilter(); showNext(); });
userTypeSelect.addEventListener('change', () => { updateFilter(); showNext(); });

document.getElementById('markBtn').addEventListener('click', () => {
    if (filteredList.length === 0) return;
    const item = filteredList[currentIndex];
    let marked = JSON.parse(localStorage.getItem('markedWords') || '[]');
    if (marked.includes(item.ja)) marked = marked.filter(w => w !== item.ja);
    else marked.push(item.ja);
    localStorage.setItem('markedWords', JSON.stringify(marked));
    updateMarkButton(item.ja);
    if (reviewModeToggle.checked) updateFilter();
});

init();