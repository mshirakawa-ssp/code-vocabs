/**
 * code-vocabs: IT用語学習アプリ (日中ハイブリッド学習版)
 */

let dictionary = [];
let filteredList = [];
let currentIndex = -1;
let autoPlayTimeout = null;
let isFlipped = false;
let isFiltersPanelOpen = false;

// タッチジェスチャー状態
let touchStartX = 0;
let touchStartY = 0;
let touchStartTime = 0;
let longPressTimer = null;
let isTouchSwiping = false;
const SWIPE_THRESHOLD = 50;
const TOUCH_MOVE_THRESHOLD = 10;
const LONG_PRESS_DURATION = 600;

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
    const today = getTodayStr();
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 90);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    const dates = JSON.parse(localStorage.getItem('markingDates') || '[]')
        .filter(d => d >= cutoffStr);
    dates.push(today);
    localStorage.setItem('markingDates', JSON.stringify(dates));
}

function recordLearningEvent() {
    const today = getTodayStr();
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 90);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    const dates = JSON.parse(localStorage.getItem('learningDates') || '[]')
        .filter(d => d >= cutoffStr);
    dates.push(today);
    localStorage.setItem('learningDates', JSON.stringify(dates));
}

function getMarkingCountsByDate() {
    const dates = JSON.parse(localStorage.getItem('markingDates') || '[]');
    const counts = {};
    dates.forEach(d => { counts[d] = (counts[d] || 0) + 1; });
    return counts;
}

function getLearningCountsByDate() {
    const dates = JSON.parse(localStorage.getItem('learningDates') || '[]');
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
    const learned = JSON.parse(localStorage.getItem('learnedWords') || '[]');
    const total = dictionary.length;
    const markedCount = marked.length;
    const learnedCount = learned.length;
    const pendingCount = total - markedCount - learnedCount;
    const learnedRatio = total > 0 ? Math.round((learnedCount / total) * 100) : 0;

    // Category breakdown
    const categoryStats = {};
    dictionary.forEach(item => {
        if (!categoryStats[item.category]) {
            categoryStats[item.category] = { total: 0, marked: 0, learned: 0 };
        }
        categoryStats[item.category].total++;
        if (marked.includes(item.ja)) categoryStats[item.category].marked++;
        if (learned.includes(item.ja)) categoryStats[item.category].learned++;
    });

    // 7-day trend
    const markCountsByDate = getMarkingCountsByDate();
    const learnCountsByDate = getLearningCountsByDate();
    const last7Days = getLast7Days();
    const maxCount = Math.max(
        ...last7Days.map(d => (markCountsByDate[d] || 0) + (learnCountsByDate[d] || 0)),
        1
    );
    const BAR_MAX_PX = 48;

    // Overview section
    let html = `
        <div class="mb-6">
            <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">概览 (Overview)</h3>
            <div class="grid grid-cols-4 gap-2 mb-4">
                <div class="bg-indigo-50 rounded-xl p-2 text-center">
                    <div class="text-xl font-black text-indigo-600">${total}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase mt-1">总单词</div>
                </div>
                <div class="bg-orange-50 rounded-xl p-2 text-center">
                    <div class="text-xl font-black text-orange-500">${markedCount}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase mt-1">需复习</div>
                </div>
                <div class="bg-green-50 rounded-xl p-2 text-center">
                    <div class="text-xl font-black text-green-600">${learnedCount}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase mt-1">已掌握</div>
                </div>
                <div class="bg-slate-50 rounded-xl p-2 text-center">
                    <div class="text-xl font-black text-slate-500">${pendingCount}</div>
                    <div class="text-[9px] font-bold text-slate-400 uppercase mt-1">待学习</div>
                </div>
            </div>
            <div class="flex justify-between text-[10px] font-bold mb-1">
                <span class="text-slate-500">掌握进度</span>
                <span class="text-green-600">${learnedRatio}%</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-3">
                <div class="bg-green-500 h-3 rounded-full transition-all" style="width: ${learnedRatio}%"></div>
            </div>
        </div>
    `;

    // 7-day trend section (side-by-side bars: orange=需复习, green=已掌握)
    html += `<div class="mb-6">
        <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">近7天标记活动</h3>
        <div class="flex gap-3 mb-2">
            <span class="text-[9px] text-orange-500 font-bold">⚠️ 需复习</span>
            <span class="text-[9px] text-green-500 font-bold">✅ 已掌握</span>
        </div>
        <div class="flex gap-1" style="height: 72px; align-items: flex-end;">`;
    last7Days.forEach(day => {
        const mc = markCountsByDate[day] || 0;
        const lc = learnCountsByDate[day] || 0;
        const mBarH = mc > 0 ? Math.max(4, Math.round((mc / maxCount) * BAR_MAX_PX)) : 0;
        const lBarH = lc > 0 ? Math.max(4, Math.round((lc / maxCount) * BAR_MAX_PX)) : 0;
        const dayLabel = day.slice(5); // MM-DD
        html += `
            <div style="flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:72px;">
                <div style="width:100%; display:flex; gap:1px; align-items:flex-end; justify-content:center;">
                    ${mBarH > 0 ? `<div class="bg-orange-400 flex-1 rounded-t-sm" style="height:${mBarH}px;"></div>` : '<div class="flex-1"></div>'}
                    ${lBarH > 0 ? `<div class="bg-green-500 flex-1 rounded-t-sm" style="height:${lBarH}px;"></div>` : '<div class="flex-1"></div>'}
                </div>
                <div style="font-size:9px; color:#94a3b8; margin-top:2px;">${dayLabel}</div>
            </div>`;
    });
    html += `</div></div>`;

    // Category breakdown section
    html += `<div>
        <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">分类统计</h3>`;
    Object.entries(categoryStats)
        .sort((a, b) => (b[1].marked + b[1].learned) - (a[1].marked + a[1].learned))
        .forEach(([cat, stats]) => {
            const learnedRatioBar = stats.total > 0 ? Math.round((stats.learned / stats.total) * 100) : 0;
            const markedRatioBar = stats.total > 0 ? Math.round((stats.marked / stats.total) * 100) : 0;
            html += `
                <div class="mb-3">
                    <div class="flex justify-between text-[10px] font-bold mb-1">
                        <span class="text-slate-600 truncate mr-2">${cat}</span>
                        <span class="shrink-0">
                            <span class="text-orange-500">⚠️${stats.marked}</span>
                            <span class="text-slate-300 mx-1">|</span>
                            <span class="text-green-600">✅${stats.learned}</span>
                            <span class="text-slate-300 mx-1">|</span>
                            <span class="text-slate-400">${stats.total}</span>
                        </span>
                    </div>
                    <div class="w-full bg-slate-100 rounded-full h-2 flex overflow-hidden">
                        <div class="bg-orange-400 h-2 transition-all" style="width: ${markedRatioBar}%;"></div>
                        <div class="bg-green-500 h-2 transition-all" style="width: ${learnedRatioBar}%;"></div>
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

    updateWordButtons(item.ja);
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

function updateWordButtons(jaWord) {
    const marked = JSON.parse(localStorage.getItem('markedWords') || '[]');
    const learned = JSON.parse(localStorage.getItem('learnedWords') || '[]');
    const isMarked = marked.includes(jaWord);
    const isLearned = learned.includes(jaWord);

    const markBtn = document.getElementById('markBtn');
    document.getElementById('markIcon').innerText = "⚠️";
    document.getElementById('markText').innerText = isMarked ? "需复习 ✓" : "需复习";
    markBtn.classList.toggle('text-orange-500', isMarked);
    markBtn.classList.toggle('border-orange-400', isMarked);
    markBtn.classList.toggle('bg-orange-50', isMarked);

    const learnBtn = document.getElementById('learnBtn');
    document.getElementById('learnIcon').innerText = "✅";
    document.getElementById('learnText').innerText = isLearned ? "已掌握 ✓" : "已掌握";
    learnBtn.classList.toggle('text-green-600', isLearned);
    learnBtn.classList.toggle('border-green-400', isLearned);
    learnBtn.classList.toggle('bg-green-50', isLearned);
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
    if (isTouchSwiping) return;
    if (autoPlayToggle.innerText === "STOP") stopAutoPlay();
    isFlipped = !isFlipped;
    cardInner.classList.toggle('is-flipped');
    const item = filteredList[currentIndex];
    const mode = userTypeSelect.value;
    if (isFlipped) mode === 'ja-learner' ? speak(item.ja, 'ja-JP') : speak(item.zh, 'zh-CN');
    else mode === 'ja-learner' ? speak(item.zh, 'zh-CN') : speak(item.ja, 'ja-JP');
});

// タッチジェスチャー（スワイプ・長押し）
cardInner.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    touchStartTime = Date.now();
    isTouchSwiping = false;
    longPressTimer = setTimeout(() => {
        document.getElementById('markBtn').click();
    }, LONG_PRESS_DURATION);
}, { passive: true });

cardInner.addEventListener('touchmove', (e) => {
    const dx = e.touches[0].clientX - touchStartX;
    const dy = e.touches[0].clientY - touchStartY;
    if (Math.abs(dx) > TOUCH_MOVE_THRESHOLD || Math.abs(dy) > TOUCH_MOVE_THRESHOLD) {
        isTouchSwiping = true;
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }
}, { passive: true });

cardInner.addEventListener('touchend', (e) => {
    clearTimeout(longPressTimer);
    longPressTimer = null;
    if (!isTouchSwiping) return;
    const dx = e.changedTouches[0].clientX - touchStartX;
    const dy = e.changedTouches[0].clientY - touchStartY;
    if (Math.abs(dx) > SWIPE_THRESHOLD && Math.abs(dx) > Math.abs(dy)) {
        if (autoPlayToggle.innerText === 'STOP') stopAutoPlay();
        if (dx > 0) showPrev();
        else showNext();
    }
    isTouchSwiping = false;
}, { passive: true });

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
    let learned = JSON.parse(localStorage.getItem('learnedWords') || '[]');
    if (marked.includes(item.ja)) {
        marked = marked.filter(w => w !== item.ja);
    } else {
        marked.push(item.ja);
        // 互斥：从已掌握中移除
        learned = learned.filter(w => w !== item.ja);
        recordMarkingEvent();
    }
    localStorage.setItem('markedWords', JSON.stringify(marked));
    localStorage.setItem('learnedWords', JSON.stringify(learned));
    updateWordButtons(item.ja);
    if (reviewModeToggle.checked) updateFilter();
});

document.getElementById('learnBtn').addEventListener('click', () => {
    if (filteredList.length === 0) return;
    const item = filteredList[currentIndex];
    let marked = JSON.parse(localStorage.getItem('markedWords') || '[]');
    let learned = JSON.parse(localStorage.getItem('learnedWords') || '[]');
    if (learned.includes(item.ja)) {
        learned = learned.filter(w => w !== item.ja);
    } else {
        learned.push(item.ja);
        // 互斥：从需复习中移除
        marked = marked.filter(w => w !== item.ja);
        recordLearningEvent();
    }
    localStorage.setItem('markedWords', JSON.stringify(marked));
    localStorage.setItem('learnedWords', JSON.stringify(learned));
    updateWordButtons(item.ja);
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
        case 'l':
        case 'L':
            e.preventDefault();
            document.getElementById('learnBtn').click();
            break;
        case 'a':
        case 'A':
            e.preventDefault();
            autoPlayToggle.innerText === 'STOP' ? stopAutoPlay() : startAutoPlay();
            break;
    }
});

init();