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
const $  = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const pipelineFill = $('#pipelineFill');
const pipDots      = $$('.pip-dot');
const navLinks     = $$('.pipe-step-link');
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

/* ── Utility ─────────────────────────────────────── */
function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* ═══════════════════════════════════════════════════════
   STEP 1 — UPLOAD & SYNTHESIZE
═══════════════════════════════════════════════════════ */
(function () {
    const dropzone   = $('#brainDropzone');
    const fileInput  = $('#brainFileInput');
    const filesBox   = $('#brainFiles');
    const fileList   = $('#brainFileList');
    const fileCount  = $('#brainFileCount');
    const actionsBox = $('#brainActions');
    const synthBtn   = $('#synthesizeBtn');
    const synthText  = synthBtn.querySelector('.btn-text');
    const synthLoad  = synthBtn.querySelector('.btn-loader');
    const resultBox  = $('#brainResult');
    const errBox     = $('#brainError');
    const errText    = $('#brainErrorText');
    const toStep2    = $('#toStep2Btn');
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
            const vc      = state.synthesis?.vc_readiness || {};
            $('#brainConceptName').textContent    = concept.startup_name || 'Your Startup';
            $('#brainConceptTagline').textContent  = concept.tagline || '';
            $('#brainConceptPitch').textContent    = concept.elevator_pitch || 'Pitch synthesized.';
            $('#brainSector').textContent          = profile.sector ? `Sector: ${profile.sector}` : '';
            $('#brainStage').textContent           = profile.stage ? `Stage: ${profile.stage}` : '';
            $('#brainReadiness').textContent       = vc.score ? `VC Readiness: ${vc.score}/10` : '';
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
    const matchBtn  = $('#matchBtn');
    const btnText   = matchBtn.querySelector('.btn-text');
    const btnLoad   = matchBtn.querySelector('.btn-loader');
    const resultsEl = $('#matchResults');
    const listEl    = $('#resultsList');
    const modeEl    = $('#resultsMode');
    const errBox    = $('#matchError');
    const errText   = $('#matchErrorText');
    const toStep3   = $('#toStep3Btn');

    matchBtn.addEventListener('click', async () => {
        btnText.hidden = true; btnLoad.hidden = false; matchBtn.disabled = true;
        errBox.hidden = true; resultsEl.hidden = true;

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
            renderMatches();
            resultsEl.hidden = false;
        } catch (err) {
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
            const vcName   = m.fund_name || m.name || '—';
            const score    = m.match_score ?? '';
            const verdict  = m.verdict || '';
            const reasoning = m.reasoning || '';
            const approach = m.suggested_approach || '';
            const confidence = m.confidence || '';
            const website  = m.fund_website || m.website || '';
            const nameHtml = website ? `<a class="result-link" href="${escHtml(website)}" target="_blank">${escHtml(vcName)}</a>` : escHtml(vcName);
            const vClass   = verdict.toLowerCase().includes('strong') ? 'strong' : verdict.toLowerCase().includes('good') ? 'good' : verdict.toLowerCase().includes('weak') ? 'weak' : 'poor';

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
    const tabsEl   = $('#genVcTabs');
    const genBtn   = $('#generateBtn');
    const btnText  = genBtn.querySelector('.btn-text');
    const btnLoad  = genBtn.querySelector('.btn-loader');
    const outputEl = $('#genOutput');
    const titleEl  = $('#genOutputTitle');
    const bodyEl   = $('#genOutputBody');
    const copyBtn  = $('#genCopyBtn');
    const historyEl= $('#genHistory');
    const histList = $('#genHistoryList');
    const advanceEl= $('#genAdvance');
    const toStep4  = $('#toStep4Btn');
    const optBtns  = $$('.gen-opt');

    let activeVcIdx = 0;
    let activeType = 'email';

    // Type selector
    optBtns.forEach(b => b.addEventListener('click', () => {
        optBtns.forEach(o => o.classList.remove('active'));
        b.classList.add('active');
        activeType = b.dataset.type;
    }));

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

        const typeLabels = { email: '✉️ Cold Email', pitch: '🎤 Pitch Script', linkedin: '💼 LinkedIn DM', summary: '📄 Exec Summary' };
        let endpoint = '';
        let payload = {};

        if (activeType === 'email') {
            endpoint = '/api/generate/email';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: concept.elevator_pitch || '',
                startup_sector: profile.sector || 'Technology',
                vc_name: vc.fund_name || '',
                vc_mandate: vc.sector_mandate || vc.real_thesis || '',
                tone: 'professional',
            };
        } else if (activeType === 'pitch') {
            endpoint = '/api/generate/pitch';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: concept.elevator_pitch || '',
                startup_sector: profile.sector || 'Technology',
                target_market: profile.target_market || '',
                funding_ask: profile.funding_ask || '',
            };
        } else if (activeType === 'linkedin') {
            // Reuse email endpoint with linkedin tone
            endpoint = '/api/generate/email';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: concept.elevator_pitch || '',
                startup_sector: profile.sector || 'Technology',
                vc_name: vc.fund_name || '',
                vc_mandate: vc.sector_mandate || vc.real_thesis || '',
                vc_contact: 'Partner',
                tone: 'linkedin-dm-casual-short',
            };
        } else if (activeType === 'summary') {
            endpoint = '/api/generate/summary';
            payload = {
                startup_name: concept.startup_name || 'My Startup',
                startup_description: concept.elevator_pitch || '',
                startup_sector: profile.sector || 'Technology',
                target_market: profile.target_market || '',
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
            const content = data.email || data.pitch || data.summary || JSON.stringify(data, null, 2);

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
        // Pre-fill interview with first selected VC
        const vc = state.selectedVCs[0];
        if (vc) {
            $('#vcFundName').value = vc.fund_name || '';
            $('#vcMandate').value = vc.sector_mandate || vc.real_thesis || '';
        }
        const concept = state.synthesis?.pitchable_concept || {};
        $('#contextPitch').textContent = concept.elevator_pitch || '';
        goToStep(4);
    });
})();

/* ═══════════════════════════════════════════════════════
   STEP 4 — PRACTICE (Mock Interview)
═══════════════════════════════════════════════════════ */
(function () {
    const setupEl     = $('#interviewSetup');
    const liveEl      = $('#interviewLive');
    const feedbackEl  = $('#interviewFeedback');
    const form        = $('#interviewSetupForm');
    const startBtn    = $('#startInterviewBtn');
    const stBtnText   = startBtn.querySelector('.btn-text');
    const stBtnLoad   = startBtn.querySelector('.btn-loader');
    const endBtn      = $('#endInterviewBtn');
    const recordBtn   = $('#recordBtn');
    const recText     = recordBtn.querySelector('.btn-text');
    const recLoad     = recordBtn.querySelector('.btn-loader');
    const sendBtn     = $('#sendAnswerBtn');
    const questionTxt = $('#questionText');
    const roundPill   = $('#roundPill');
    const lastScoreEl = $('#lastScore');
    const liveVcName  = $('#liveVcName');
    const transcriptBox = $('#transcriptBox');
    const transcriptTxt = $('#transcriptText');
    const restartBtn  = $('#restartInterviewBtn');
    const canvas      = $('#waveformCanvas');
    const styleSelect = $('#interviewStyle');
    const styleHint   = $('#styleHint');
    const hints = { casual: 'Friendly and conversational', standard: 'Balanced, covers all key areas', aggressive: 'Expect confrontational, rapid-fire challenges' };
    styleSelect.addEventListener('change', () => { styleHint.textContent = hints[styleSelect.value] || ''; });

    let recognition, mediaStream, analyser, animFrame;

    // Start interview
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        stBtnText.hidden = true; stBtnLoad.hidden = false; startBtn.disabled = true;
        const concept = state.synthesis?.pitchable_concept || {};
        const payload = {
            vc_fund_name: $('#vcFundName').value || 'Sequoia Capital',
            investment_mandate: $('#vcMandate').value || 'Technology',
            interview_style: styleSelect.value,
            startup_pitch: concept.elevator_pitch || '',
        };
        try {
            const res = await fetch(`${API}/api/simulator/interview/start`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            state.interviewId = data.session_id;
            liveVcName.textContent = payload.vc_fund_name;
            questionTxt.textContent = data.question || 'Tell me about your startup.';
            roundPill.textContent = 'Round 1 / 5';
            lastScoreEl.textContent = 'Last Score —';
            setupEl.hidden = true; liveEl.hidden = false; feedbackEl.hidden = true;
            // Play audio
            playQuestionAudio(state.interviewId);
        } catch (err) {
            alert('Failed to start: ' + err.message);
        } finally {
            stBtnText.hidden = false; stBtnLoad.hidden = true; startBtn.disabled = false;
        }
    });

    async function playQuestionAudio(sessionId) {
        try {
            const res = await fetch(`${API}/api/simulator/interview/${sessionId}/audio`, { method: 'POST' });
            if (!res.ok) return;
            const blob = await res.blob();
            const audio = new Audio(URL.createObjectURL(blob));
            audio.play().catch(() => {});
        } catch (_) {}
    }

    // Record answer
    let transcript = '';
    recordBtn.addEventListener('click', () => {
        if (recLoad.hidden === false) { stopRecording(); return; }
        transcript = '';
        transcriptTxt.textContent = '';
        transcriptBox.hidden = true;
        sendBtn.disabled = true;
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) { alert('Speech recognition not supported. Use Chrome or Edge.'); return; }
        recognition = new SR();
        recognition.continuous = true; recognition.interimResults = true; recognition.lang = 'en-US';
        recognition.onresult = (e) => {
            let interim = '', final = '';
            for (let i = 0; i < e.results.length; i++) {
                if (e.results[i].isFinal) final += e.results[i][0].transcript + ' ';
                else interim += e.results[i][0].transcript;
            }
            transcript = (final + interim).trim();
            transcriptTxt.textContent = transcript;
            transcriptBox.hidden = false;
        };
        recognition.onerror = () => stopRecording();
        recognition.onend = () => stopRecording();
        recognition.start();
        recText.hidden = true; recLoad.hidden = false;
        startWaveform();
    });

    function stopRecording() {
        try { recognition?.stop(); } catch (_) {}
        try { mediaStream?.getTracks().forEach(t => t.stop()); } catch (_) {}
        cancelAnimationFrame(animFrame);
        recText.hidden = false; recLoad.hidden = true;
        if (transcript.trim()) sendBtn.disabled = false;
    }

    function startWaveform() {
        navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
            mediaStream = stream;
            const ctx = new AudioContext(); const src = ctx.createMediaStreamSource(stream);
            analyser = ctx.createAnalyser(); analyser.fftSize = 256; src.connect(analyser);
            const buf = new Uint8Array(analyser.frequencyBinCount);
            const cCtx = canvas.getContext('2d');
            function draw() {
                animFrame = requestAnimationFrame(draw);
                analyser.getByteFrequencyData(buf);
                cCtx.fillStyle = '#0a0a0a'; cCtx.fillRect(0, 0, canvas.width, canvas.height);
                const barW = canvas.width / buf.length * 2.5;
                let x = 0;
                for (let i = 0; i < buf.length; i++) {
                    const h = (buf[i] / 255) * canvas.height;
                    cCtx.fillStyle = `hsl(${70 + i}, 90%, 60%)`; cCtx.fillRect(x, canvas.height - h, barW, h);
                    x += barW + 1;
                }
            }
            draw();
        }).catch(() => {});
    }

    // Send answer
    sendBtn.addEventListener('click', async () => {
        if (!transcript.trim() || !state.interviewId) return;
        sendBtn.disabled = true; sendBtn.textContent = 'Sending…';
        try {
            const res = await fetch(`${API}/api/simulator/interview/${state.interviewId}/respond`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answer: transcript }),
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            if (data.interview_complete) {
                showFeedback(data); return;
            }
            questionTxt.textContent = data.next_question || 'Next question…';
            roundPill.textContent = `Round ${data.round || '?'} / 5`;
            lastScoreEl.textContent = data.score != null ? `Last Score ${data.score}/10` : 'Last Score —';
            transcript = ''; transcriptTxt.textContent = ''; transcriptBox.hidden = true;
            playQuestionAudio(state.interviewId);
        } catch (err) {
            alert('Error: ' + err.message);
        } finally {
            sendBtn.disabled = false; sendBtn.textContent = 'Send Answer →';
        }
    });

    // End interview early
    endBtn.addEventListener('click', async () => {
        if (!state.interviewId) return;
        endBtn.disabled = true;
        try {
            const res = await fetch(`${API}/api/simulator/interview/${state.interviewId}/end`, { method: 'POST' });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            showFeedback(data);
        } catch (err) {
            alert('Error ending: ' + err.message);
        } finally {
            endBtn.disabled = false;
        }
    });

    function showFeedback(data) {
        liveEl.hidden = true; feedbackEl.hidden = false;
        const feedback = data.feedback || {};
        $('#feedbackPro').innerHTML = (feedback.strengths || 'No strengths feedback.').replace(/\n/g, '<br>');
        $('#feedbackCon').innerHTML = (feedback.improvements || 'No improvement feedback.').replace(/\n/g, '<br>');
        const txLog = data.transcript || [];
        if (txLog.length) {
            const html = txLog.map(t => `<div class="tx-turn"><strong>${escHtml(t.role || 'VC')}:</strong> ${escHtml(t.content || '')}</div>`).join('');
            $('#feedbackTranscript').innerHTML = `<h4>Full Transcript</h4>${html}`;
        }
        state.completed.add(4);
        updateUI();
    }

    // Restart
    restartBtn.addEventListener('click', () => {
        setupEl.hidden = false; liveEl.hidden = true; feedbackEl.hidden = true;
        state.interviewId = null;
    });
})();

/* ── Init ────────────────────────────────────────── */
updateUI();
