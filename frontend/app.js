/* ═══════════════════════════════════════════════════════
   CO-PILOT — Procedural Pipeline Controller
   Steps: Upload → Match → Generate → Practice
═══════════════════════════════════════════════════════ */
'use strict';

const API = 'http://localhost:8000';

/* ── Pipeline state ──────────────────────────────── */
const state = {
    step: 1,               // current step (1-4)
    completed: new Set(),   // completed step numbers
    synthesis: null,        // synthesized startup data from brain
    matches: [],            // agentic match results
    selectedVCs: [],        // VCs selected for generation
    generatedContent: [],   // history of generated items
    interviewId: null,      // active interview session
};

/* ── DOM refs ────────────────────────────────────── */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const pipelineFill = $('#pipelineFill');
const pipDots = $$('.pip-dot');
const navLinks = $$('.pipe-step-link');
const stepSections = $$('.pipe-step');

/* ── Navigation ──────────────────────────────────── */
function goToStep(n) {
    if (n < 1 || n > 4) return;
    // Can only go to steps that are completed or the next one
    if (n > 1 && !state.completed.has(n - 1) && n !== state.step) return;
    state.step = n;
    updateUI();
}

function updateUI() {
    const n = state.step;
    // Show/hide sections
    stepSections.forEach(s => {
        const sn = +s.dataset.step;
        s.hidden = sn !== n;
    });
    // Progress bar
    pipelineFill.style.width = `${(n / 4) * 100}%`;
    // Pip dots
    pipDots.forEach(d => {
        const dn = +d.dataset.step;
        d.classList.toggle('active', dn === n);
        d.classList.toggle('done', state.completed.has(dn));
        d.disabled = dn > 1 && !state.completed.has(dn - 1) && dn !== n;
    });
    // Nav links
    navLinks.forEach(a => {
        const an = +a.dataset.step;
        a.classList.toggle('active', an === n);
        a.classList.toggle('done', state.completed.has(an));
    });
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Bind nav clicks
navLinks.forEach(a => a.addEventListener('click', e => { e.preventDefault(); goToStep(+a.dataset.step); }));
pipDots.forEach(d => d.addEventListener('click', () => goToStep(+d.dataset.step)));

// Hero Start button
const startStaticBtn = $('#startStaticBtn');
if (startStaticBtn) {
    startStaticBtn.addEventListener('click', () => {
        $('#step1').scrollIntoView({ behavior: 'smooth' });
    });
}

/* ── Utility ─────────────────────────────────────── */
function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* ═══════════════════════════════════════════════════════
   STEP 1 — UPLOAD & SYNTHESIZE
═══════════════════════════════════════════════════════ */
(function () {
    const dropzone = $('#brainDropzone');
    const fileInput = $('#brainFileInput');
    const filesBox = $('#brainFiles');
    const fileList = $('#brainFileList');
    const fileCount = $('#brainFileCount');
    const actionsBox = $('#brainActions');
    const synthBtn = $('#synthesizeBtn');
    const synthText = synthBtn.querySelector('.btn-text');
    const synthLoad = synthBtn.querySelector('.btn-loader');
    const resultBox = $('#brainResult');
    const errBox = $('#brainError');
    const errText = $('#brainErrorText');
    const toStep2 = $('#toStep2Btn');
    let uploaded = 0;

    // Drag & drop
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('brain-dropzone--hover'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('brain-dropzone--hover'));
    dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('brain-dropzone--hover'); handleFiles(e.dataTransfer.files); });
    fileInput.addEventListener('change', () => { handleFiles(fileInput.files); fileInput.value = ''; });

    async function handleFiles(files) {
        if (!files.length) return;
        filesBox.hidden = false;
        errBox.hidden = true;
        for (const file of files) {
            const row = document.createElement('div');
            row.className = 'brain-file-row';
            row.innerHTML = `<span class="brain-file-name">${escHtml(file.name)}</span><span class="brain-file-status brain-file-status--uploading">Uploading…</span>`;
            fileList.appendChild(row);
            try {
                const fd = new FormData();
                fd.append('file', file);
                const res = await fetch(`${API}/api/brain/upload`, { method: 'POST', body: fd });
                if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
                const data = await res.json();
                const st = row.querySelector('.brain-file-status');
                if (data.status === 'failed') { st.textContent = '✗ Failed'; st.className = 'brain-file-status brain-file-status--error'; }
                else { st.textContent = '✓ Indexed'; st.className = 'brain-file-status brain-file-status--done'; uploaded++; }
            } catch (err) {
                const st = row.querySelector('.brain-file-status');
                st.textContent = '✗ ' + err.message; st.className = 'brain-file-status brain-file-status--error';
            }
        }
        fileCount.textContent = `${uploaded} file(s)`;
        if (uploaded > 0) actionsBox.hidden = false;
    }

    // Synthesize
    synthBtn.addEventListener('click', async () => {
        synthText.hidden = true; synthLoad.hidden = false; synthBtn.disabled = true;
        errBox.hidden = true; resultBox.hidden = true;
        try {
            const res = await fetch(`${API}/api/brain/synthesize`, { method: 'POST' });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            state.synthesis = data.synthesis || data;
            const concept = state.synthesis?.pitchable_concept || {};
            const profile = state.synthesis?.startup_profile || {};
            const vc = state.synthesis?.vc_readiness || {};
            $('#brainConceptName').textContent = concept.startup_name || 'Your Startup';
            $('#brainConceptTagline').textContent = concept.tagline || '';
            $('#brainConceptPitch').textContent = concept.elevator_pitch || 'Pitch synthesized.';
            $('#brainSector').textContent = profile.sector ? `Sector: ${profile.sector}` : '';
            $('#brainStage').textContent = profile.stage ? `Stage: ${profile.stage}` : '';
            $('#brainReadiness').textContent = vc.score ? `VC Readiness: ${vc.score}/10` : '';
            resultBox.hidden = false;
        } catch (err) {
            errBox.hidden = false; errText.textContent = 'Synthesis failed: ' + err.message;
        } finally {
            synthText.hidden = false; synthLoad.hidden = true; synthBtn.disabled = false;
        }
    });

    // Advance to Step 2
    toStep2.addEventListener('click', () => {
        state.completed.add(1);
        // Pre-fill Step 2 context
        const concept = state.synthesis?.pitchable_concept || {};
        $('#matchContextPitch').textContent = concept.elevator_pitch || 'Your startup profile is loaded.';
        goToStep(2);
    });
})();

/* ═══════════════════════════════════════════════════════
   STEP 2 — MATCH
═══════════════════════════════════════════════════════ */
(function () {
    const matchBtn = $('#matchBtn');
    const btnText = matchBtn.querySelector('.btn-text');
    const btnLoad = matchBtn.querySelector('.btn-loader');
    const resultsEl = $('#matchResults');
    const listEl = $('#resultsList');
    const modeEl = $('#resultsMode');
    const errBox = $('#matchError');
    const errText = $('#matchErrorText');
    const toStep3 = $('#toStep3Btn');
    const loadingEl = $('#matchLoading');
    const loadingFill = $('#matchLoadingFill');
    const loadingStatus = $('#matchLoadingStatus');

    const LOADING_PHASES = [
        { pct: 10, text: 'Creating AI agents…', delay: 0 },
        { pct: 25, text: 'Agent 1: Analyzing your startup profile…', delay: 3000 },
        { pct: 40, text: 'Agent 2: Profiling VC investment theses…', delay: 8000 },
        { pct: 60, text: 'Agent 2: Still profiling VCs… (this is thorough)', delay: 15000 },
        { pct: 75, text: 'Agent 3: Running match reasoning…', delay: 25000 },
        { pct: 85, text: 'Agent 3: Generating detailed justifications…', delay: 35000 },
        { pct: 92, text: 'Ranking and finalizing results…', delay: 45000 },
    ];

    let loadingTimers = [];

    function startLoadingBar() {
        loadingEl.hidden = false;
        loadingFill.style.width = '0%';
        loadingStatus.textContent = 'Initializing AI agents…';
        loadingTimers.forEach(t => clearTimeout(t));
        loadingTimers = [];
        LOADING_PHASES.forEach(phase => {
            const t = setTimeout(() => {
                loadingFill.style.width = phase.pct + '%';
                loadingStatus.textContent = phase.text;
            }, phase.delay);
            loadingTimers.push(t);
        });
    }

    function stopLoadingBar(success) {
        loadingTimers.forEach(t => clearTimeout(t));
        loadingTimers = [];
        if (success) {
            loadingFill.style.width = '100%';
            loadingStatus.textContent = '✓ Matching complete!';
            setTimeout(() => { loadingEl.hidden = true; }, 1200);
        } else {
            loadingEl.hidden = true;
        }
    }

    matchBtn.addEventListener('click', async () => {
        btnText.hidden = true; btnLoad.hidden = false; matchBtn.disabled = true;
        errBox.hidden = true; resultsEl.hidden = true;
        startLoadingBar();

        const concept = state.synthesis?.pitchable_concept || {};
        const profile = state.synthesis?.startup_profile || {};
        const payload = {
            name: concept.startup_name || 'My Startup',
            sector: profile.sector || 'AI',
            stage: profile.stage || 'seed',
            description: concept.elevator_pitch || '',
            location: profile.location || 'Canada',
        };

        try {
            const res = await fetch(`${API}/api/match/agentic?top_n=5`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            state.matches = data.matches || [];
            modeEl.textContent = '🤖 Agentic AI (Backboard)';
            stopLoadingBar(true);
            renderMatches();
            resultsEl.hidden = false;
        } catch (err) {
            stopLoadingBar(false);
            errBox.hidden = false; errText.textContent = 'Match failed: ' + err.message;
        } finally {
            btnText.hidden = false; btnLoad.hidden = true; matchBtn.disabled = false;
        }
    });

    function renderMatches() {
        listEl.innerHTML = '';
        if (!state.matches.length) {
            listEl.innerHTML = '<p style="color:var(--text-muted)">No matches found.</p>';
            return;
        }
        state.matches.forEach((m, i) => {
            const vcName = m.fund_name || m.name || '—';
            const score = m.match_score ?? '';
            const verdict = m.verdict || '';
            const reasoning = m.reasoning || '';
            const approach = m.suggested_approach || '';
            const confidence = m.confidence || '';
            const website = m.fund_website || m.website || '';
            const nameHtml = website ? `<a class="result-link" href="${escHtml(website)}" target="_blank">${escHtml(vcName)}</a>` : escHtml(vcName);
            const vClass = verdict.toLowerCase().includes('strong') ? 'strong' : verdict.toLowerCase().includes('good') ? 'good' : verdict.toLowerCase().includes('weak') ? 'weak' : 'poor';

            const item = document.createElement('div');
            item.className = 'result-item';
            item.style.animationDelay = `${i * 0.08}s`;
            item.innerHTML = `
                <label class="result-check"><input type="checkbox" data-idx="${i}" checked /><span class="checkmark"></span></label>
                <div class="result-rank">${i + 1}</div>
                <div class="result-info">
                    <div class="result-name">${nameHtml}</div>
                    ${verdict ? `<span class="result-verdict result-verdict--${vClass}">${escHtml(verdict)}</span>` : ''}
                    ${reasoning ? `<div class="result-reasoning">${escHtml(reasoning)}</div>` : ''}
                    ${approach ? `<div class="result-approach">💡 ${escHtml(approach)}</div>` : ''}
                </div>
                <div class="result-score-area">
                    ${score !== '' ? `<div class="result-score">${escHtml(String(score))}<span class="score-unit">/100</span></div>` : ''}
                    ${confidence ? `<div class="result-confidence">${escHtml(confidence)} confidence</div>` : ''}
                </div>
            `;
            listEl.appendChild(item);
        });
        updateSelectedCount();
        listEl.addEventListener('change', updateSelectedCount);
    }

    function updateSelectedCount() {
        const checks = listEl.querySelectorAll('input[type="checkbox"]:checked');
        state.selectedVCs = Array.from(checks).map(c => state.matches[+c.dataset.idx]).filter(Boolean);
        toStep3.disabled = state.selectedVCs.length === 0;
        toStep3.textContent = state.selectedVCs.length
            ? `Generate Outreach for ${state.selectedVCs.length} VC${state.selectedVCs.length > 1 ? 's' : ''} →`
            : 'Select VCs to continue';
    }

    toStep3.addEventListener('click', () => {
        state.completed.add(2);
        // Populate Step 3 VC tabs
        buildGenTabs();
        goToStep(3);
    });
})();

/* ═══════════════════════════════════════════════════════
   STEP 3 — GENERATE OUTREACH
═══════════════════════════════════════════════════════ */
(function () {
    const tabsEl = $('#genVcTabs');
    const genBtn = $('#generateBtn');
    const btnText = genBtn.querySelector('.btn-text');
    const btnLoad = genBtn.querySelector('.btn-loader');
    const outputEl = $('#genOutput');
    const titleEl = $('#genOutputTitle');
    const bodyEl = $('#genOutputBody');
    const copyBtn = $('#genCopyBtn');
    const historyEl = $('#genHistory');
    const histList = $('#genHistoryList');
    const advanceEl = $('#genAdvance');
    const toStep4 = $('#toStep4Btn');
    const optBtns = $$('.gen-opt');

    let activeVcIdx = 0;
    let activeType = 'email';

    // Type selector
    const customBox = $('#genCustomBox');
    optBtns.forEach(b => b.addEventListener('click', () => {
        optBtns.forEach(o => o.classList.remove('active'));
        b.classList.add('active');
        activeType = b.dataset.type;
        if (customBox) customBox.hidden = activeType !== 'custom';
    }));

    // Depth slider
    const depthSlider = $('#ragDepth');
    const depthVal = $('#ragDepthVal');
    if (depthSlider && depthVal) {
        const labels = ['Brief', 'Standard', 'Exhaustive'];
        depthSlider.addEventListener('input', () => {
            depthVal.textContent = labels[depthSlider.value - 1];
        });
    }

    window.buildGenTabs = function () {
        tabsEl.innerHTML = '';
        state.selectedVCs.forEach((vc, i) => {
            const tab = document.createElement('button');
            tab.className = 'gen-vc-tab' + (i === 0 ? ' active' : '');
            tab.textContent = vc.fund_name || vc.name || `VC ${i + 1}`;
            tab.addEventListener('click', () => {
                tabsEl.querySelectorAll('.gen-vc-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                activeVcIdx = i;
            });
            tabsEl.appendChild(tab);
        });
    };

    genBtn.addEventListener('click', async () => {
        const vc = state.selectedVCs[activeVcIdx];
        if (!vc) return;

        btnText.hidden = true; btnLoad.hidden = false; genBtn.disabled = true;
        outputEl.hidden = true;

        const concept = state.synthesis?.pitchable_concept || {};
        const profile = state.synthesis?.startup_profile || {};
        const ip = state.synthesis?.ip_analysis || {};

        const typeLabels = { email: '✉️ Cold Email', pitch: '🎤 Pitch Script', linkedin: '💼 LinkedIn DM', summary: '📄 Exec Summary', custom: '✨ Custom Content' };
        let endpoint = '';
        let payload = {};
        const depth = depthSlider ? parseInt(depthSlider.value) : 2;

        // Include full synthesis data for deep generation
        const fullDescription = [
            concept.elevator_pitch || '',
            concept.problem ? `Problem: ${concept.problem}` : '',
            concept.solution ? `Solution: ${concept.solution}` : '',
            concept.secret_sauce ? `Secret sauce: ${concept.secret_sauce}` : '',
            ip.core_innovation ? `Core innovation: ${ip.core_innovation}` : '',
            ip.technical_moat ? `Technical moat: ${ip.technical_moat}` : '',
        ].filter(Boolean).join('. ');

        if (activeType === 'email') {
            endpoint = '/api/generate/email';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: fullDescription,
                startup_sector: profile.sector || 'Technology',
                vc_name: vc.fund_name || '',
                vc_mandate: vc.sector_mandate || vc.real_thesis || '',
                tone: 'professional',
                depth
            };
        } else if (activeType === 'pitch') {
            endpoint = '/api/generate/pitch';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: fullDescription,
                startup_sector: profile.sector || 'Technology',
                target_market: profile.target_market || '',
                funding_ask: profile.funding_ask || '',
                tech_stack: (profile.tech_stack || []).join(', '),
                depth
            };
        } else if (activeType === 'linkedin') {
            endpoint = '/api/generate/email';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: fullDescription,
                startup_sector: profile.sector || 'Technology',
                vc_name: vc.fund_name || '',
                vc_mandate: vc.sector_mandate || vc.real_thesis || '',
                vc_contact: 'Partner',
                tone: 'linkedin-dm-casual-short',
                depth
            };
        } else if (activeType === 'summary') {
            endpoint = '/api/generate/summary';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: fullDescription,
                startup_sector: profile.sector || 'Technology',
                target_market: profile.target_market || '',
                traction: profile.traction || '',
                tech_stack: (profile.tech_stack || []).join(', '),
                depth
            };
        } else if (activeType === 'custom') {
            endpoint = '/api/generate/custom';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: fullDescription,
                startup_sector: profile.sector || 'Technology',
                prompt: $('#genCustomPrompt').value || 'Generate something professional.',
                previous_content: bodyEl.textContent || '',
                depth
            };
        }

        try {
            const res = await fetch(`${API}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            const content = data.email || data.pitch || data.summary || data.content || JSON.stringify(data, null, 2);

            titleEl.textContent = `${typeLabels[activeType]} — ${vc.fund_name || 'VC'}`;
            bodyEl.textContent = content;
            outputEl.hidden = false;

            // Add to history
            state.generatedContent.push({ type: activeType, vc: vc.fund_name, content });
            renderHistory();
            advanceEl.hidden = false;
            state.completed.add(3);
        } catch (err) {
            titleEl.textContent = 'Error';
            bodyEl.textContent = err.message;
            outputEl.hidden = false;
        } finally {
            btnText.hidden = false; btnLoad.hidden = true; genBtn.disabled = false;
        }
    });

    function renderHistory() {
        if (!state.generatedContent.length) return;
        historyEl.hidden = false;
        histList.innerHTML = '';
        state.generatedContent.forEach((item, i) => {
            const row = document.createElement('div');
            row.className = 'gen-history-item';
            const typeIcons = { email: '✉️', pitch: '🎤', linkedin: '💼', summary: '📄' };
            row.innerHTML = `
                <span class="gen-hist-icon">${typeIcons[item.type] || '📝'}</span>
                <span class="gen-hist-label">${escHtml(item.vc || 'General')}</span>
                <button class="gen-hist-view" data-idx="${i}">View</button>
            `;
            row.querySelector('.gen-hist-view').addEventListener('click', () => {
                const typeLabels = { email: '✉️ Cold Email', pitch: '🎤 Pitch Script', linkedin: '💼 LinkedIn DM', summary: '📄 Exec Summary' };
                titleEl.textContent = `${typeLabels[item.type]} — ${item.vc}`;
                bodyEl.textContent = item.content;
                outputEl.hidden = false;
            });
            histList.appendChild(row);
        });
    }

    // Copy to clipboard
    copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(bodyEl.textContent).then(() => {
            copyBtn.textContent = '✓ Copied!';
            setTimeout(() => copyBtn.textContent = '📋 Copy', 2000);
        });
    });

    // Advance to Step 4
    toStep4.addEventListener('click', () => {
        state.completed.add(3);
        populateStep4();
        goToStep(4);
    });
})();

/* ═══════════════════════════════════════════════════════
   STEP 4 — PRACTICE (Preload VCs + Launch Live Interview)
═══════════════════════════════════════════════════════ */
function populateStep4() {
    const vcSelect = document.getElementById('vcSelect');
    const contextPitch = document.getElementById('contextPitch');
    if (!vcSelect) return;

    // Populate VC selector from matched VCs
    vcSelect.innerHTML = '<option value="" disabled selected>— Select a VC from your matches —</option>';
    state.selectedVCs.forEach((vc, i) => {
        const opt = document.createElement('option');
        opt.value = i;
        opt.textContent = `${vc.fund_name || vc.name || 'VC'} — ${vc.verdict || ''} (${vc.match_score || '?'}/100)`;
        vcSelect.appendChild(opt);
    });

    // If VCs exist, auto-select the first one
    if (state.selectedVCs.length > 0) {
        vcSelect.value = '0';
    }

    // Show startup context from synthesis
    const concept = state.synthesis?.pitchable_concept || {};
    if (contextPitch) {
        contextPitch.textContent = concept.elevator_pitch || 'Your startup profile is loaded from uploaded documents.';
    }
}

(function () {
    const setupForm = document.getElementById('interviewSetupForm');
    const startBtn = document.getElementById('startInterviewBtn');
    if (!setupForm || !startBtn) return;

    const styleSelect = document.getElementById('interviewStyle');
    const styleHint = document.getElementById('styleHint');
    const styleHints = {
        casual: 'Relaxed and conversational',
        standard: 'Balanced, covers all key areas',
        aggressive: 'Confrontational, rapid-fire challenges',
    };
    if (styleSelect && styleHint) {
        styleSelect.addEventListener('change', () => {
            styleHint.textContent = styleHints[styleSelect.value] || '';
        });
    }

    setupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const vcSelect = document.getElementById('vcSelect');
        const vcIdx = vcSelect ? parseInt(vcSelect.value) : -1;
        const vc = state.selectedVCs[vcIdx] || {};
        const concept = state.synthesis?.pitchable_concept || {};
        const profile = state.synthesis?.startup_profile || {};
        const ip = state.synthesis?.ip_analysis || {};

        const vcName = vc.fund_name || vc.name || 'Sequoia Capital';
        const vcMandate = vc.sector_mandate || vc.real_thesis || 'AI';
        const vcStyle = styleSelect?.value || 'standard';

        // Build a rich startup pitch from synthesis
        const pitch = [
            concept.elevator_pitch || '',
            concept.problem ? `Problem: ${concept.problem}` : '',
            concept.solution ? `Solution: ${concept.solution}` : '',
            concept.secret_sauce ? `Secret sauce: ${concept.secret_sauce}` : '',
            ip.core_innovation ? `Core innovation: ${ip.core_innovation}` : '',
            profile.target_market ? `Target market: ${profile.target_market}` : '',
            profile.business_model ? `Business model: ${profile.business_model}` : '',
        ].filter(Boolean).join('. ');

        // Open the interview page with full context as URL params
        const params = new URLSearchParams({
            vc: vcName,
            mandate: vcMandate,
            style: vcStyle,
            pitch: pitch || 'A startup.',
            reasoning: vc.reasoning || '',
            approach: vc.suggested_approach || '',
        });
        window.open(`interview.html?${params.toString()}`, '_blank');
    });
})();
