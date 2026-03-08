/* ──────────────────────────────────────────────────────
   Mock Interview — LIVE Conversation Controller
   Auto-starts speech recognition after VC speaks.
   Auto-submits after 2s of silence.
   Phases: Setup → Live Conversation → Feedback
────────────────────────────────────────────────────── */

const API = 'http://localhost:8000';
const SILENCE_TIMEOUT_MS = 2500; // Auto-submit after 2.5s of silence

/* ── DOM refs ──────────────────────────────────────── */
const setupPhase     = document.getElementById('setupPhase');
const livePhase      = document.getElementById('livePhase');
const feedbackPhase  = document.getElementById('feedbackPhase');
const setupForm      = document.getElementById('setupForm');
const startBtn       = document.getElementById('startBtn');
const startText      = startBtn.querySelector('.btn-text');
const startLoader    = startBtn.querySelector('.btn-loader');

const liveVcName     = document.getElementById('liveVcName');
const liveRound      = document.getElementById('liveRound');
const transcript     = document.getElementById('transcript');
const interviewStatus= document.getElementById('interviewStatus');
const micArea        = document.getElementById('micArea');
const micBtn         = document.getElementById('micBtn');
const micHint        = document.getElementById('micHint');
const waveformCanvas = document.getElementById('waveform');
const liveTranscript = document.getElementById('liveTranscript');
const liveText       = document.getElementById('liveText');
const scorePill      = document.getElementById('scorePill');
const lastScoreEl    = document.getElementById('lastScore');
const endInterviewBtn= document.getElementById('endInterviewBtn');

const fbRounds       = document.getElementById('fbRounds');
const fbAvgScore     = document.getElementById('fbAvgScore');
const fbEndReason    = document.getElementById('fbEndReason');
const prosBody       = document.getElementById('prosBody');
const consBody       = document.getElementById('consBody');
const feedbackTranscript = document.getElementById('feedbackTranscript');
const restartBtn     = document.getElementById('restartBtn');

/* ── State ─────────────────────────────────────────── */
let sessionId     = null;
let currentRound  = 0;
let isListening   = false;
let recognition   = null;
let audioContext  = null;
let analyser      = null;
let animFrameId   = null;
let userResponseText = '';
let silenceTimer  = null;
let lastSpeechTime = 0;

/* ── Auto-populate from URL params ────────────────── */
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('vc'))      document.getElementById('vcName').value = urlParams.get('vc');
if (urlParams.get('mandate'))  document.getElementById('vcMandate').value = urlParams.get('mandate');
if (urlParams.get('style'))    document.getElementById('vcStyle').value = urlParams.get('style');
if (urlParams.get('pitch'))    document.getElementById('startupPitch').value = urlParams.get('pitch');

/* ── Style hint updater ────────────────────────────── */
const styleHints = {
    aggressive:  'Expect confrontational, rapid-fire challenges',
    analytical:  'Expect deep dives into numbers and unit economics',
    friendly:    'Friendly tone, but probing follow-up questions',
    skeptical:   'Every claim will be questioned and doubted',
    casual:      'Relaxed and conversational',
    standard:    'Balanced, covers all key areas',
};
document.getElementById('vcStyle').addEventListener('change', (e) => {
    document.getElementById('styleHint').textContent = styleHints[e.target.value] || '';
});


/* ═══════════════════════════════════════════════════════
   PHASE 1 → START INTERVIEW
═══════════════════════════════════════════════════════ */
setupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    startText.hidden = true;
    startLoader.hidden = false;
    startBtn.disabled = true;

    const payload = {
        vc_name:      document.getElementById('vcName').value.trim()    || 'Sequoia Capital',
        vc_mandate:   document.getElementById('vcMandate').value.trim() || 'AI',
        vc_style:     document.getElementById('vcStyle').value,
        startup_pitch: document.getElementById('startupPitch').value.trim() || 'A startup.',
    };

    try {
        const res = await fetch(`${API}/api/simulator/interview/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();

        sessionId    = data.session_id;
        currentRound = data.round;

        // Switch phase
        setupPhase.hidden  = true;
        livePhase.hidden   = false;
        liveVcName.textContent = payload.vc_name;
        updateRoundBadge();

        // Add VC question to transcript
        addBubble('vc', data.question_text);
        interviewStatus.textContent = 'Playing question audio…';

        // Fetch and play audio, then auto-start listening
        await playQuestionAudio();

    } catch (err) {
        alert('Failed to start interview: ' + err.message);
    } finally {
        startText.hidden = false;
        startLoader.hidden = true;
        startBtn.disabled = false;
    }
});


/* ═══════════════════════════════════════════════════════
   TRANSCRIPT BUBBLES
═══════════════════════════════════════════════════════ */
function addBubble(role, text, score) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble chat-bubble--${role}`;

    const label = role === 'vc' ? `🤵 ${liveVcName.textContent}` : '🧑 You';
    let scoreHtml = '';
    if (role === 'user' && score !== undefined && score !== null) {
        const cls = score >= 7 ? 'good' : score >= 4 ? 'ok' : 'bad';
        scoreHtml = `<span class="bubble-score bubble-score--${cls}">${score}/10</span>`;
    }

    bubble.innerHTML = `
        <div class="bubble-header">
            <span class="bubble-label">${label}</span>
            ${scoreHtml}
        </div>
        <div class="bubble-text">${escHtml(text)}</div>
    `;
    transcript.appendChild(bubble);
    transcript.scrollTop = transcript.scrollHeight;
}


/* ═══════════════════════════════════════════════════════
   AUDIO PLAYBACK (ElevenLabs TTS)
═══════════════════════════════════════════════════════ */
async function playQuestionAudio() {
    try {
        const res = await fetch(`${API}/api/simulator/interview/${sessionId}/audio`, {
            method: 'POST',
        });
        if (!res.ok) throw new Error('Audio fetch failed');

        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        const audio = new Audio(url);

        await new Promise((resolve, reject) => {
            audio.onended  = resolve;
            audio.onerror  = reject;
            audio.play().catch(reject);
        });

        URL.revokeObjectURL(url);
    } catch (err) {
        console.warn('Audio playback failed, continuing without audio:', err);
    }

    // AUTO-START LISTENING after audio finishes
    interviewStatus.textContent = '🎤 Listening — speak your answer…';
    startListening();
}


/* ═══════════════════════════════════════════════════════
   LIVE SPEECH RECOGNITION (Auto-start, Auto-submit)
═══════════════════════════════════════════════════════ */
function startListening() {
    userResponseText = '';
    isListening = true;
    lastSpeechTime = Date.now();

    // Show listening UI
    micArea.hidden = false;
    micBtn.classList.add('mic-btn--recording');
    micHint.textContent = 'Listening — speak naturally, pause when done';
    liveTranscript.hidden = false;
    liveText.textContent = '';

    // ── Speech Recognition ──
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        micHint.textContent = '⚠ Speech Recognition not supported — type below and press Enter';
        liveText.contentEditable = true;
        liveText.focus();
        liveText.addEventListener('keydown', handleTypedResponse);
        return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
        let interim = '';
        let final_  = '';
        for (let i = 0; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                final_ += event.results[i][0].transcript;
            } else {
                interim += event.results[i][0].transcript;
            }
        }
        userResponseText = final_;
        liveText.textContent = final_ + (interim ? ' ' + interim : '');
        lastSpeechTime = Date.now();

        // Reset silence timer every time we get speech
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(onSilenceDetected, SILENCE_TIMEOUT_MS);
    };

    recognition.onerror = (e) => {
        console.warn('Speech recognition error:', e.error);
        if (e.error === 'not-allowed') {
            micHint.textContent = '⚠ Microphone blocked — check browser permissions';
        }
    };

    recognition.onend = () => {
        // Auto-restart if still listening (browser stops after silence)
        if (isListening && recognition) {
            try { recognition.start(); } catch (e) { /* ignore */ }
        }
    };

    recognition.start();

    // Start silence timer
    silenceTimer = setTimeout(onSilenceDetected, SILENCE_TIMEOUT_MS * 2); // Give extra time for first words

    // ── Waveform visualizer ──
    setupWaveform();
}

function handleTypedResponse(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        userResponseText = liveText.textContent.trim();
        if (userResponseText) submitResponse();
    }
}

function onSilenceDetected() {
    // Only auto-submit if we have some text
    if (userResponseText.trim().length > 10) {
        stopListening();
        submitResponse();
    } else {
        // Not enough text yet — keep listening, extend timeout
        silenceTimer = setTimeout(onSilenceDetected, SILENCE_TIMEOUT_MS);
    }
}

function stopListening() {
    isListening = false;
    clearTimeout(silenceTimer);
    micBtn.classList.remove('mic-btn--recording');

    if (recognition) {
        recognition.onend = null;
        recognition.stop();
        recognition = null;
    }

    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
    }

    micArea.hidden = true;
    liveTranscript.hidden = true;
}

async function setupWaveform() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new AudioContext();
        analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        analyser.fftSize = 256;
        waveformCanvas.hidden = false;
        drawWaveform();
    } catch (err) {
        console.warn('Waveform setup failed:', err);
    }
}

// Allow mic button click as a manual stop
micBtn.addEventListener('click', () => {
    if (isListening && userResponseText.trim()) {
        stopListening();
        submitResponse();
    }
});


/* ── Waveform drawing ────────────────────────────── */
function drawWaveform() {
    if (!analyser) return;
    const ctx = waveformCanvas.getContext('2d');
    const bufLen = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufLen);
    const W = waveformCanvas.width;
    const H = waveformCanvas.height;

    function draw() {
        animFrameId = requestAnimationFrame(draw);
        analyser.getByteTimeDomainData(dataArray);

        ctx.fillStyle = '#111114';
        ctx.fillRect(0, 0, W, H);

        ctx.lineWidth = 2;
        ctx.strokeStyle = '#d4ff5c';
        ctx.beginPath();

        const sliceW = W / bufLen;
        let x = 0;
        for (let i = 0; i < bufLen; i++) {
            const v = dataArray[i] / 128.0;
            const y = v * H / 2;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
            x += sliceW;
        }
        ctx.lineTo(W, H / 2);
        ctx.stroke();
    }
    draw();
}


/* ═══════════════════════════════════════════════════════
   SUBMIT RESPONSE (Auto-triggered by silence)
═══════════════════════════════════════════════════════ */
async function submitResponse() {
    if (!userResponseText.trim()) return;

    micArea.hidden = true;
    liveTranscript.hidden = true;
    interviewStatus.textContent = 'Evaluating your response…';

    try {
        const res = await fetch(`${API}/api/simulator/interview/${sessionId}/respond`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response_text: userResponseText.trim() }),
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();

        // Show user bubble with score
        addBubble('user', userResponseText.trim(), data.response_score);

        // Update score pill
        scorePill.hidden = false;
        lastScoreEl.textContent = data.response_score + '/10';
        lastScoreEl.className = 'score-value score-value--' +
            (data.response_score >= 7 ? 'good' : data.response_score >= 4 ? 'ok' : 'bad');

        if (data.should_end) {
            interviewStatus.textContent = 'Interview ended — generating feedback…';
            await loadFeedback(data.end_reason);
        } else {
            currentRound = data.round;
            updateRoundBadge();
            addBubble('vc', data.question_text);
            interviewStatus.textContent = 'Playing question audio…';
            // Play audio then auto-start listening again
            await playQuestionAudio();
        }

    } catch (err) {
        interviewStatus.textContent = '⚠ Error: ' + err.message;
        micArea.hidden = false;
    }
}


/* ═══════════════════════════════════════════════════════
   END INTERVIEW
═══════════════════════════════════════════════════════ */
endInterviewBtn.addEventListener('click', async () => {
    if (!sessionId) return;
    endInterviewBtn.disabled = true;
    stopListening();
    interviewStatus.textContent = 'Ending interview…';
    await loadFeedback('user_ended');
});


/* ═══════════════════════════════════════════════════════
   PHASE 3 → FEEDBACK
═══════════════════════════════════════════════════════ */
async function loadFeedback(endReason) {
    try {
        const res = await fetch(`${API}/api/simulator/interview/${sessionId}/end`, {
            method: 'POST',
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();

        // Switch phase
        livePhase.hidden     = true;
        feedbackPhase.hidden = false;

        // Stats
        fbRounds.textContent    = data.total_rounds;
        fbAvgScore.textContent  = data.average_score + '/10';
        fbEndReason.textContent = formatEndReason(data.end_reason);

        // Pros card
        const pros = data.pros_feedback || {};
        prosBody.innerHTML = renderFeedbackCard(pros, 'pros');

        // Cons card
        const cons = data.cons_feedback || {};
        consBody.innerHTML = renderFeedbackCard(cons, 'cons');

        // Transcript
        feedbackTranscript.innerHTML = '';
        (data.transcript || []).forEach((entry) => {
            const div = document.createElement('div');
            div.className = `fb-entry fb-entry--${entry.role}`;
            const label = entry.role === 'vc' ? '🤵 VC' : '🧑 You';
            const scoreTag = entry.score != null ? `<span class="fb-score">${entry.score}/10</span>` : '';
            div.innerHTML = `<strong>${label}</strong> ${scoreTag}<br/>${escHtml(entry.text)}`;
            feedbackTranscript.appendChild(div);
        });

    } catch (err) {
        feedbackPhase.hidden = false;
        livePhase.hidden = true;
        prosBody.innerHTML = `<p class="feedback-error">Error loading feedback: ${escHtml(err.message)}</p>`;
        consBody.innerHTML = prosBody.innerHTML;
    }
}

function renderFeedbackCard(data, type) {
    if (data.error) return `<p class="feedback-error">${escHtml(data.raw || data.error)}</p>`;

    const items = type === 'pros' ? (data.strengths || []) : (data.weaknesses || []);
    const bestWorst = type === 'pros' ? data.best_moment : data.worst_moment;
    const overall = data.overall || '';

    let html = '<ul class="feedback-list">';
    items.forEach(item => {
        html += `<li>${escHtml(item)}</li>`;
    });
    html += '</ul>';

    if (bestWorst) {
        const label = type === 'pros' ? '⭐ Best moment' : '⚠ Worst moment';
        html += `<div class="feedback-highlight"><strong>${label}:</strong> ${escHtml(bestWorst)}</div>`;
    }
    if (overall) {
        html += `<p class="feedback-overall">${escHtml(overall)}</p>`;
    }
    return html;
}

function formatEndReason(reason) {
    const map = {
        complete: 'All rounds done',
        low_performance: 'Low scores',
        user_ended: 'You ended it',
    };
    return map[reason] || reason || '—';
}


/* ═══════════════════════════════════════════════════════
   RESTART
═══════════════════════════════════════════════════════ */
restartBtn.addEventListener('click', () => {
    sessionId = null;
    currentRound = 0;
    feedbackPhase.hidden = true;
    setupPhase.hidden    = false;
    transcript.innerHTML = '';
    scorePill.hidden = true;
    endInterviewBtn.disabled = false;
});


/* ═══════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════ */
function updateRoundBadge() {
    liveRound.textContent = `Round ${currentRound} / 5`;
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
