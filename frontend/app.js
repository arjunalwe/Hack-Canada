/* ── Scroll-reveal observer ── */
const observer = new IntersectionObserver(
    (entries) => {
        entries.forEach((entry, i) => {
            if (entry.isIntersecting) {
                setTimeout(() => entry.target.classList.add('visible'), i * 80);
                observer.unobserve(entry.target);
            }
        });
    },
    { threshold: 0.12 }
);

document.querySelectorAll('.step, .feature-card').forEach(el => observer.observe(el));

/* ── Staggered delay for step cards ── */
document.querySelectorAll('.step').forEach((el, i) => {
    el.style.transitionDelay = `${i * 0.07}s`;
});
document.querySelectorAll('.feature-card').forEach((el, i) => {
    el.style.transitionDelay = `${i * 0.06}s`;
});

/* ── Nav scroll style ── */
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
    nav.style.borderBottomColor = window.scrollY > 20
        ? 'rgba(255,255,255,0.10)'
        : 'rgba(255,255,255,0.07)';
}, { passive: true });

/* ── Demo form ── */
const form = document.getElementById('demoForm');
const matchBtn = document.getElementById('matchBtn');
const btnText = matchBtn.querySelector('.btn-text');
const btnLoader = matchBtn.querySelector('.btn-loader');
const results = document.getElementById('demoResults');
const resultsList = document.getElementById('resultsList');
const resultsMode = document.getElementById('resultsMode');
const errorBox = document.getElementById('demoError');
const errorDetail = document.getElementById('errorDetail');

const API_BASE = 'http://localhost:8000';

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Gather values
    const name = document.getElementById('startupName').value.trim() || 'My Startup';
    const sector = document.getElementById('sector').value;
    const stage = document.getElementById('stage').value;
    const description = document.getElementById('description').value.trim() || 'An AI-powered platform.';
    const location = document.getElementById('location').value.trim() || 'Canada';
    const fundingAsk = parseFloat(document.getElementById('fundingAsk').value) || null;

    // Loading state
    btnText.hidden = true;
    btnLoader.hidden = false;
    matchBtn.disabled = true;
    results.hidden = true;
    errorBox.hidden = true;

    const payload = {
        name,
        sector,
        stage,
        description,
        location,
        ...(fundingAsk && { funding_ask: fundingAsk }),
    };

    try {
        const res = await fetch(`${API_BASE}/api/match/?top_n=8`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // No auth token needed for local dev — backend uses open CORS
            },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`${res.status} ${res.statusText}: ${errText.slice(0, 200)}`);
        }

        const data = await res.json();
        renderResults(data);
    } catch (err) {
        errorBox.hidden = false;
        errorDetail.textContent = err.message;
    } finally {
        btnText.hidden = false;
        btnLoader.hidden = true;
        matchBtn.disabled = false;
    }
});

function renderResults(data) {
    const matches = data.matches ?? [];
    const mode = data.mode ?? 'fast';

    resultsMode.textContent = mode === 'agentic' ? 'Agentic AI' : 'Fast Match';

    resultsList.innerHTML = '';

    if (matches.length === 0) {
        resultsList.innerHTML = '<p style="color:var(--text-muted);font-size:.875rem">No matches found. Try broadening your description or scraping fresh VCs first.</p>';
    } else {
        matches.forEach((m, i) => {
            const item = document.createElement('div');
            item.className = 'result-item';
            item.style.animationDelay = `${i * 0.06}s`;

            // fund_name is the key in seed_data.json; match_score is already 0–100
            const vcName = m.fund_name ?? m.name ?? m.vc_name ?? '—';
            const vcSectors = m.sector_mandate ?? (Array.isArray(m.sectors) ? m.sectors.join(', ') : (m.sector ?? ''));
            const vcStage = m.investment_stage ?? m.stage ?? m.preferred_stage ?? '';
            const score = m.match_score ?? m.score ?? null;
            const scoreStr = score !== null ? `${score.toFixed(1)}%` : '';
            const website = m.website ?? null;
            const nameHtml = website
                ? `<a class="result-link" href="${escHtml(website)}" target="_blank" rel="noopener">${escHtml(vcName)}</a>`
                : escHtml(vcName);

            item.innerHTML = `
        <div class="result-rank">${i + 1}</div>
        <div class="result-info">
          <div class="result-name">${nameHtml}</div>
          <div class="result-detail">${[vcSectors, vcStage].filter(Boolean).join(' · ')}</div>
        </div>
        ${scoreStr ? `<div class="result-score">${escHtml(scoreStr)}</div>` : ''}
        ${website ? `<a class="result-visit" href="${escHtml(website)}" target="_blank" rel="noopener" title="Visit website">↗</a>` : ''}
      `;
            resultsList.appendChild(item);
        });
    }

    results.hidden = false;
    results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/* ── Elevator Pitch Generator ── */
const pitchForm = document.getElementById('pitchForm');
const pitchBtn = document.getElementById('pitchBtn');
const pitchBtnText = pitchBtn.querySelector('.btn-text');
const pitchBtnLoader = pitchBtn.querySelector('.btn-loader');
const pitchOutput = document.getElementById('pitchOutput');
const pitchText = document.getElementById('pitchText');
const pitchError = document.getElementById('pitchError');
const pitchErrorDetail = document.getElementById('pitchErrorDetail');
const pitchCopyBtn = document.getElementById('pitchCopyBtn');

pitchForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const payload = {
        startup_name: document.getElementById('pitchName').value.trim() || 'My Startup',
        startup_description: document.getElementById('pitchDescription').value.trim() || 'An innovative platform.',
        startup_sector: document.getElementById('pitchSector').value,
        tech_stack: document.getElementById('pitchTechStack').value.trim(),
        target_market: document.getElementById('pitchMarket').value.trim(),
        funding_ask: document.getElementById('pitchFunding').value.trim(),
    };

    // Loading state
    pitchBtnText.hidden = true;
    pitchBtnLoader.hidden = false;
    pitchBtn.disabled = true;
    pitchOutput.hidden = true;
    pitchError.hidden = true;

    try {
        const res = await fetch(`${API_BASE}/api/generate/pitch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`${res.status} ${res.statusText}: ${errText.slice(0, 200)}`);
        }

        const data = await res.json();
        pitchText.textContent = data.pitch ?? 'No pitch returned.';
        pitchOutput.hidden = false;
        pitchOutput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        pitchCopyBtn.textContent = 'Copy';
    } catch (err) {
        pitchError.hidden = false;
        pitchErrorDetail.textContent = err.message;
    } finally {
        pitchBtnText.hidden = false;
        pitchBtnLoader.hidden = true;
        pitchBtn.disabled = false;
    }
});

pitchCopyBtn.addEventListener('click', async () => {
    const text = pitchText.textContent;
    if (!text) return;
    try {
        await navigator.clipboard.writeText(text);
        pitchCopyBtn.textContent = 'Copied!';
        setTimeout(() => { pitchCopyBtn.textContent = 'Copy'; }, 2000);
    } catch {
        pitchCopyBtn.textContent = 'Copy failed';
    }
});

