window.ACTIVE_QUIZ_DATA = [];
window.USER_SELECTIONS = {};
window.ACTIVE_LOADED_RECORD_ID = null;

document.addEventListener("DOMContentLoaded", () => { loadSidebarHistory(); });

async function loadSidebarHistory() {
    try {
        const response = await fetch('/api/history');
        const result = await response.json();
        const c = document.getElementById("historyList");
        if (!c) return;
        c.innerHTML = "";
        if (result.success && result.history.length > 0) {
            result.history.forEach(item => {
                const row = document.createElement("div");
                row.className = `history-item d-flex align-items-center justify-content-between ${window.ACTIVE_LOADED_RECORD_ID === item.id ? "active" : ""}`;
                row.id = `history_node_${item.id}`;
                row.innerHTML = `
                    <div class="history-item-main flex-1 min-w-0 mr-2" onclick="openHistoricalAnalysis(${item.id})">
                        <span class="history-title-text block">${escapeHtml(item.title)}</span>
                    </div>
                    <button class="p-1 text-gray-500 hover:text-amber-400 transition-colors" onclick="toggleFavoriteNode(event,${item.id})">
                        <i class="${item.favorite ? 'fas' : 'far'} fa-star"></i>
                    </button>`;
                c.appendChild(row);
            });
        } else {
            c.innerHTML = '<div class="text-center text-gray-500 text-xs py-12 px-4 font-medium">No previous summaries</div>';
        }
    } catch (err) { console.error("History load failed:", err); }
}

async function openHistoricalAnalysis(entryId) {
    window.ACTIVE_LOADED_RECORD_ID = entryId;
    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
    const node = document.getElementById(`history_node_${entryId}`);
    if (node) node.classList.add('active');
    try {
        const res = await fetch(`/api/history/${entryId}`);
        const result = await res.json();
        if (result.success) populateDashboardWorkspace(result.data);
        else alert("Error: " + result.error);
    } catch (err) { console.error(err); }
}

function populateDashboardWorkspace(data) {
    window.ACTIVE_LOADED_RECORD_ID = data.id;
    document.getElementById("workspaceTitleHeader").innerText = data.title;
    document.getElementById("summaryTextCard").innerText = data.summary;
    const iw = document.getElementById("keyInsightsList");
    iw.innerHTML = "";
    (data.key_points || []).forEach(point => {
        const li = document.createElement("li");
        li.className = "text-xs font-semibold text-gray-600 bg-gray-100/70 p-2.5 rounded-xl border border-gray-100 flex items-start gap-2";
        li.innerHTML = `<i class="fas fa-chevron-right text-indigo-500 mt-0.5 text-[10px]"></i><span>${escapeHtml(point)}</span>`;
        iw.appendChild(li);
    });
    if (!data.key_points || !data.key_points.length)
        iw.innerHTML = '<li class="text-xs text-gray-400 italic">No insights compiled.</li>';
    document.getElementById("transcriptRawTextArea").value = data.transcript;
    document.getElementById("quizDifficultyBadge").innerText = `${data.metadata?.category || "Evaluation"} Mode`;
    renderInteractiveQuiz(data.quiz);
}

function renderInteractiveQuiz(quizArray) {
    window.ACTIVE_QUIZ_DATA = quizArray || [];
    window.USER_SELECTIONS = {};
    const qc = document.getElementById("quizPanelContainer");
    qc.innerHTML = "";
    if (!quizArray || !quizArray.length) {
        qc.innerHTML = "<p class='text-sm text-gray-400 italic text-center py-6'>No quiz generated yet.</p>";
        return;
    }
    quizArray.forEach((item, qi) => {
        const card = document.createElement("div");
        card.className = "p-5 border border-gray-200 rounded-2xl bg-gray-50/50 space-y-3";
        card.innerHTML = `
            <h4 class="text-sm font-bold text-gray-900 flex items-center gap-2">
                <span class="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-md">Q${qi+1}</span>
                ${escapeHtml(item.question)}
            </h4>
            <div class="grid gap-2 mt-2" id="options_block_q_${qi}"></div>
            <div class="hidden mt-3 p-3.5 rounded-xl border text-xs font-medium" id="feedback_panel_q_${qi}"></div>`;
        qc.appendChild(card);
        const ob = document.getElementById(`options_block_q_${qi}`);
        item.options.forEach(opt => {
            const lbl = document.createElement("label");
            lbl.className = "custom-clickable-row flex items-center p-3 rounded-xl cursor-pointer text-xs font-semibold text-gray-700";
            lbl.innerHTML = `<input type="radio" name="rg_${qi}" class="w-4 h-4 mr-3" onclick="saveClientChoiceValue(${qi},'${opt.replace(/'/g,"\\'")}')"><span>${escapeHtml(opt)}</span>`;
            ob.appendChild(lbl);
        });
    });
    const ep = document.createElement("div");
    ep.className = "flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-gray-100";
    ep.innerHTML = `
        <div class="flex gap-2">
            <button class="bg-gray-900 hover:bg-gray-800 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition-all" onclick="checkClientQuizAnswers()">Check Answers</button>
            <button class="bg-white border border-gray-300 text-gray-700 text-xs font-bold px-4 py-2.5 rounded-xl" onclick="resetActiveQuizFormState()">Reset</button>
        </div>
        <div id="quizProgressBarContainer" class="hidden w-full sm:w-64 sm:ml-auto space-y-1">
            <div class="flex justify-between text-[11px] font-bold text-gray-500">
                <span>Score</span><span id="progressBarMetricLabel">0%</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2.5">
                <div id="progressBarFillBar" class="bg-emerald-500 h-2.5 rounded-full transition-all duration-500" style="width:0%"></div>
            </div>
        </div>`;
    qc.appendChild(ep);
}

function saveClientChoiceValue(qi, val) { window.USER_SELECTIONS[qi] = val; }

function checkClientQuizAnswers() {
    let correct = 0;
    const total = window.ACTIVE_QUIZ_DATA.length;
    window.ACTIVE_QUIZ_DATA.forEach((item, qi) => {
        const pane = document.getElementById(`feedback_panel_q_${qi}`);
        const choice = window.USER_SELECTIONS[qi];
        pane.classList.remove("hidden","bg-success-light","text-success-dark","border-emerald-200","bg-danger-light","text-danger-dark","border-red-200");
        const marker = s => (s && s.includes(")")) ? s.split(")")[0].trim() : s;
        if (choice === item.answer) {
            correct++;
            pane.className = "mt-3 p-3.5 rounded-xl border text-xs font-medium bg-success-light text-success-dark border-emerald-200";
            pane.innerHTML = `<div class="flex gap-2"><i class="fas fa-check-circle text-emerald-600 mt-0.5"></i><div><strong>Correct: Option ${marker(item.answer)}</strong><p class="mt-1 text-gray-500 text-[11px] italic">${escapeHtml(item.explanation)}</p></div></div>`;
        } else {
            pane.className = "mt-3 p-3.5 rounded-xl border text-xs font-medium bg-danger-light text-danger-dark border-red-200";
            pane.innerHTML = `<div class="flex gap-2"><i class="fas fa-times-circle text-red-600 mt-0.5"></i><div><strong>Incorrect</strong><br><span class="text-[11px]">Correct: ${escapeHtml(item.answer)}</span><p class="mt-1 text-gray-500 text-[11px] italic">${escapeHtml(item.explanation)}</p></div></div>`;
        }
    });
    const ratio = Math.round((correct/total)*100);
    document.getElementById("quizProgressBarContainer").classList.remove("hidden");
    document.getElementById("progressBarFillBar").style.width = `${ratio}%`;
    document.getElementById("progressBarMetricLabel").innerText = `${correct}/${total} (${ratio}%)`;
}

function resetActiveQuizFormState() { if (window.ACTIVE_QUIZ_DATA.length) renderInteractiveQuiz(window.ACTIVE_QUIZ_DATA); }

async function triggerVideoAnalysisPipeline() {
    const url = document.getElementById("urlInput").value.trim();
    const fileInput = document.getElementById("videoFileInput");
    const file = fileInput && fileInput.files[0];
    if (!url && !file) { alert("Please paste a YouTube link or upload a video file first."); return; }

    setLoaderUIState(true);
    updateLoadingStepMarker("download", file ? "Reading uploaded video..." : "Downloading video...");
    try {
        setTimeout(() => updateLoadingStepMarker("transcribe", "Transcribing via Groq Whisper..."), 4000);
        setTimeout(() => updateLoadingStepMarker("summarize", "Generating study notes..."), 9000);
        setTimeout(() => updateLoadingStepMarker("quiz", "Building quiz..."), 13000);

        const fd = new FormData();
        fd.append("lang", document.getElementById("langSelect").value);
        fd.append("questions", document.getElementById("questionCountSelect").value);
        if (file) { fd.append("video", file); } else { fd.append("url", url); }

        const res = await fetch('/api/analyze', { method: 'POST', body: fd });
        const result = await res.json();
        if (result.success) { populateDashboardWorkspace(result.data); await loadSidebarHistory(); }
        else alert("Error: " + result.error);
    } catch (err) { alert("Network error: " + err.message); }
    finally { setLoaderUIState(false); }
}

function setLoaderUIState(on) {
    const loader = document.getElementById("processingLoaderScreen");
    const btn = document.getElementById("analyzeButton");
    if (on) { loader.classList.remove("hidden"); btn.disabled=true; btn.style.opacity="0.5"; }
    else { loader.classList.add("hidden"); btn.disabled=false; btn.style.opacity="1"; }
}

function updateLoadingStepMarker(id, msg) {
    document.getElementById("loaderStateMessage").innerText = msg;
    document.querySelectorAll("#pipelineVisualStepper .step-node").forEach(el => el.classList.remove("active"));
    const n = document.getElementById(`step_${id}`);
    if (n) n.classList.add("active");
}

function switchWorkspaceTab(event, tabId) {
    document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".tab-link").forEach(el => el.classList.remove("active"));
    document.getElementById(tabId).classList.remove("hidden");
    event.target.classList.add("active");
}

async function toggleFavoriteNode(event, entryId) {
    event.stopPropagation();
    try {
        const res = await fetch(`/api/history/${entryId}/favorite`, { method: 'POST' });
        const result = await res.json();
        if (result.success) {
            if (window.ACTIVE_LOADED_RECORD_ID === entryId) {
                const star = document.querySelector("#favoriteActiveRowButton i");
                if (star) star.className = result.favorite ? "fas fa-star text-amber-500" : "far fa-star text-gray-400";
            }
            await loadSidebarHistory();
        }
    } catch (err) { console.error(err); }
}

function handleVideoFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    const label = document.getElementById('uploadLabel');
    label.textContent = file.name.length > 18 ? file.name.substring(0,15)+'...' : file.name;
    document.getElementById('urlInput').value = '';
}

function escapeHtml(s) {
    if (!s || typeof s !== 'string') return '';
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}
