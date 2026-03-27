/**
 * code-vocabs: IT用語学習アプリ (日中ハイブリッド学習版)
 */

let dictionary = [];
let filteredList = [];
let currentIndex = -1;
let autoPlayTimeout = null;
let isFlipped = false;
let isFiltersPanelOpen = false;

const cardInner = document.getElementById('cardInner');
const autoPlayToggle = document.getElementById('autoPlayToggle');
const sourceContainer = document.getElementById('sourceFilters');
const categoryContainer = document.getElementById('categoryFilters');
const reviewModeToggle = document.getElementById('reviewModeToggle');
const userTypeSelect = document.getElementById('userType');
const filtersContent = document.getElementById('filtersContent');
const filtersToggle = document.getElementById('filtersToggle');
const wordProgress = document.getElementById('wordProgress');

// --- Stats helpers ---
function getTodayStr() {
    return new Date().toISOString().slice(0, 10);
}

function recordMarkingEvent() {
    const dates = JSON.parse(localStorage.getItem('markingDates') || '[]');
    dates.push(getTodayStr());
    localStorage.setItem('markingDates', JSON.stringify(dates));
}

function getMarkingCountsByDate() {
    const dates = JSON.parse(localStorage.getItem('markingDates') || '[]');
    const counts = {};
    dates.forEach(d => { counts[d] = (counts[d] || 0) + 1; });
    return counts;
}

function getLast7Days() {
    const days = [];
    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        days.push(d.toISOString().slice(0, 10));
    }
    return days;
}

function renderStats() {
    const marked = JSON.parse(localStorage.getItem('markedWords') || '[]');
    const total = dictionary.length;
    const markedCount = marked.length;
    const markedRatio = total > 0 ? Math.round((markedCount / total) * 100) : 0;

    // Category breakdown
    const categoryStats = {};
    dictionary.forEach(item => {
        if (!categoryStats[item.category]) {
            categoryStats[item.category] = { total: 0, marked: 0 };
        }
        categoryStats[item.category].total++;
        if (marked.includes(item.ja)) {
            categoryStats[item.category].marked++;
        }
    });

    // 7-day trend
    const countsByDate = getMarkingCountsByDate();
    const last7Days = getLast7Days();
    const maxCount = Math.max(...last7Days.map(d => countsByDate[d] || 0), 1);
    const BAR_MAX_PX = 48;

    // Overview section
    let html = `
        <div class="mb-6">
            <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">概览 (Overview)</h3>
            <div class="grid grid-cols-3 gap-3 mb-4">
                <div class="bg-indigo-50 rounded-xl p-3 text-center">
                    <div class="text-2xl font-black text-indigo-600">${total}</div>
                    <div class="text-[10px] font-bold text-slate-400 uppercase mt-1">总单词</div>
                </div>
                <div class="bg-orange-50 rounded-xl p-3 text-center">
                    <div class="text-2xl font-black text-orange-500">${markedCount}</div>
                    <div class="text-[10px] font-bold text-slate-400 uppercase mt-1">需复习</div>
                </div>
                <div class="bg-green-50 rounded-xl p-3 text-center">
                    <div class="text-2xl font-black text-green-600">${total - markedCount}</div>
                    <div class="text-[10px] font-bold text-slate-400 uppercase mt-1">待学习</div>
                </div>
            </div>
            <div class="flex justify-between text-[10px] font-bold mb-1">
                <span class="text-slate-500">复习进度</span>
                <span class="text-indigo-600">${markedRatio}%</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-3">
                <div class="bg-indigo-500 h-3 rounded-full transition-all" style="width: ${markedRatio}%"></div>
            </div>
        </div>
    `;

    // 7-day trend section
    html += `<div class="mb-6">
        <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">近7天标记活动</h3>
        <div class="flex gap-1" style="height: 72px; align-items: flex-end;">`;
    last7Days.forEach(day => {
        const count = countsByDate[day] || 0;
        const barH = count > 0 ? Math.max(4, Math.round((count / maxCount) * BAR_MAX_PX)) : 0;
        const dayLabel = day.slice(5); // MM-DD
        html += `
            <div style="flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:72px;">
                <div style="font-size:9px; font-weight:700; color:#6366f1; min-height:14px;">${count > 0 ? count : ''}</div>
                <div style="width:100%; height:${barH}px; background:#6366f1; border-radius:3px 3px 0 0;"></div>
                <div style="font-size:9px; color:#94a3b8; margin-top:2px;">${dayLabel}</div>
            </div>`;
    });
    html += `</div></div>`;

    // Category breakdown section
    html += `<div>
        <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">分类统计</h3>`;
    Object.entries(categoryStats)
        .sort((a, b) => b[1].marked - a[1].marked)
        .forEach(([cat, stats]) => {
            const ratio = stats.total > 0 ? Math.round((stats.marked / stats.total) * 100) : 0;
            html += `
                <div class="mb-3">
                    <div class="flex justify-between text-[10px] font-bold mb-1">
                        <span class="text-slate-600 truncate mr-2">${cat}</span>
                        <span class="text-orange-500 shrink-0">${stats.marked}/${stats.total}</span>
                    </div>
                    <div class="w-full bg-slate-100 rounded-full h-2">
                        <div class="bg-orange-400 h-2 rounded-full transition-all" style="width: ${ratio}%"></div>
                    </div>
                </div>`;
        });
    html += `</div>`;

    document.getElementById('statsContent').innerHTML = html;
}

function openStats() {
    renderStats();
    const modal = document.getElementById('statsModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeStats() {
    const modal = document.getElementById('statsModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

// --- localStorage helpers ---
function saveFilterState() {
    const selectedSrcs = Array.from(document.querySelectorAll('.src-filter:checked')).map(el => el.value);
    const selectedCats = Array.from(document.querySelectorAll('.cat-filter:checked')).map(el => el.value);
    localStorage.setItem('selectedSources', JSON.stringify(selectedSrcs));
    localStorage.setItem('selectedCategories', JSON.stringify(selectedCats));
}

function saveCurrentIndex() {
    localStorage.setItem('currentWordIndex', String(currentIndex));
}

function loadSelectedSources() {
    const saved = localStorage.getItem('selectedSources');
    return saved ? JSON.parse(saved) : null;
}

function loadSelectedCategories() {
    const saved = localStorage.getItem('selectedCategories');
    return saved ? JSON.parse(saved) : null;
}

function loadCurrentIndex() {
    const saved = localStorage.getItem('currentWordIndex');
    return saved !== null ? parseInt(saved, 10) : -1;
}

// --- Progress display ---
function updateWordProgress() {
    if (filteredList.length === 0 || currentIndex < 0) {
        wordProgress.innerText = '';
        return;
    }
    wordProgress.innerText = `单词 ${currentIndex + 1}/${filteredList.length}`;
}

// --- Filters panel toggle ---
function setFiltersPanelOpen(open) {
    isFiltersPanelOpen = open;
    if (open) {
        filtersContent.style.display = '';
        filtersToggle.innerText = '▲';
        wordProgress.style.display = 'none';
    } else {
        filtersContent.style.display = 'none';
        filtersToggle.innerText = '▼';
        wordProgress.style.display = '';
        updateWordProgress();
    }
}

async function init() {
    try {
        const res = await fetch('data/dictionary.json');
        if (!res.ok) throw new Error('Fetch failed');
        dictionary = await res.json();
        
        createFilters('source', sourceContainer, 'src-filter', loadSelectedSources());
        createFilters('category', categoryContainer, 'cat-filter', loadSelectedCategories());
        updateFilter();

        // Start collapsed by default
        setFiltersPanelOpen(false);

        // Restore last word index
        const savedIndex = loadCurrentIndex();
        if (savedIndex >= 0 && savedIndex < filteredList.length) {
            currentIndex = savedIndex;
            showCard(currentIndex);
        } else {
            showNext();
        }
    } catch (e) {
        console.error(e);
        document.getElementById('frontText').innerText = "DATA ERROR";
    }
}

// フィルタUIの動的作成用共通関数
function createFilters(key, container, className, savedSelection) {
    const values = [...new Set(dictionary.map(item => item[key]))];
    container.innerHTML = '';
    values.forEach(val => {
        const isChecked = savedSelection ? savedSelection.includes(val) : true;
        const label = document.createElement('label');
        label.className = "flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200 text-[10px] font-black cursor-pointer hover:bg-indigo-50 transition-all select-none";
        if (isChecked) label.classList.add('border-indigo-500', 'text-indigo-600');
        label.innerHTML = `<input type="checkbox" class="${className}" value="${val}" ${isChecked ? 'checked' : ''}> ${val.toUpperCase()}`;
        container.appendChild(label);
        
        label.querySelector('input').addEventListener('change', (e) => {
            const checked = e.target.checked;
            label.classList.toggle('border-indigo-500', checked);
            label.classList.toggle('text-indigo-600', checked);
            saveFilterState();
            updateFilter();
            currentIndex = -1;
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

function showCard(index) {
    if (filteredList.length === 0) {
        document.getElementById('frontText').innerText = "EMPTY";
        document.getElementById('frontRead').innerText = "";
        updateWordProgress();
        return;
    }

    isFlipped = false;
    cardInner.classList.remove('is-flipped');

    currentIndex = (index % filteredList.length + filteredList.length) % filteredList.length;
    saveCurrentIndex();

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
    updateWordProgress();
}

function showNext() {
    if (filteredList.length === 0) {
        showCard(0);
        return;
    }
    const nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % filteredList.length;
    showCard(nextIndex);
}

function showPrev() {
    if (filteredList.length === 0) {
        showCard(0);
        return;
    }
    const prevIndex = currentIndex < 0 ? 0 : (currentIndex - 1 + filteredList.length) % filteredList.length;
    showCard(prevIndex);
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
filtersToggle.addEventListener('click', () => {
    setFiltersPanelOpen(!isFiltersPanelOpen);
});

document.getElementById('nextBtn').addEventListener('click', () => {
    if (autoPlayToggle.innerText === "STOP") stopAutoPlay();
    showNext();
});

document.getElementById('prevBtn').addEventListener('click', () => {
    if (autoPlayToggle.innerText === "STOP") stopAutoPlay();
    showPrev();
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

reviewModeToggle.addEventListener('change', () => {
    updateFilter();
    currentIndex = -1;
    showNext();
});

userTypeSelect.addEventListener('change', () => { updateFilter(); showCard(Math.max(0, currentIndex)); });

document.getElementById('markBtn').addEventListener('click', () => {
    if (filteredList.length === 0) return;
    const item = filteredList[currentIndex];
    let marked = JSON.parse(localStorage.getItem('markedWords') || '[]');
    if (marked.includes(item.ja)) marked = marked.filter(w => w !== item.ja);
    else {
        marked.push(item.ja);
        recordMarkingEvent();
    }
    localStorage.setItem('markedWords', JSON.stringify(marked));
    updateMarkButton(item.ja);
    if (reviewModeToggle.checked) updateFilter();
});

document.getElementById('statsBtn').addEventListener('click', openStats);
document.getElementById('closeStatsBtn').addEventListener('click', closeStats);
document.getElementById('statsModal').addEventListener('click', (e) => {
    if (e.target === document.getElementById('statsModal')) closeStats();
});

// キーボードショートカット
document.addEventListener('keydown', (e) => {
    // フォーカスが入力要素にある場合はスキップ
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.key) {
        case 'ArrowRight':
        case ' ':
            e.preventDefault();
            if (autoPlayToggle.innerText === 'STOP') stopAutoPlay();
            showNext();
            break;
        case 'ArrowLeft':
            e.preventDefault();
            if (autoPlayToggle.innerText === 'STOP') stopAutoPlay();
            showPrev();
            break;
        case 'Enter':
            e.preventDefault();
            if (autoPlayToggle.innerText === 'STOP') stopAutoPlay();
            isFlipped = !isFlipped;
            cardInner.classList.toggle('is-flipped');
            if (filteredList.length > 0) {
                const item = filteredList[currentIndex];
                const mode = userTypeSelect.value;
                if (isFlipped) mode === 'ja-learner' ? speak(item.ja, 'ja-JP') : speak(item.zh, 'zh-CN');
                else mode === 'ja-learner' ? speak(item.zh, 'zh-CN') : speak(item.ja, 'ja-JP');
            }
            break;
        case 'm':
        case 'M':
            e.preventDefault();
            document.getElementById('markBtn').click();
            break;
        case 'a':
        case 'A':
            e.preventDefault();
            autoPlayToggle.innerText === 'STOP' ? stopAutoPlay() : startAutoPlay();
            break;
    }
});

init();