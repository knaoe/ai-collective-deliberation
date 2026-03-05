/**
 * M.A.G.I. SYSTEM - Frontend Application
 * Multi-Agent Generative Intelligence
 *
 * Connects to FastAPI backend via WebSocket/REST
 * Falls back to mock mode when backend is unavailable
 */

// ============================================================
// Configuration
// ============================================================
const CONFIG = {
    apiBase: 'http://localhost:8000',
    wsBase: 'ws://localhost:8000',
    endpoints: {
        deliberate: '/magi/deliberate',
        stream: '/magi/deliberate/stream',
        history: '/magi/history',
        status: '/magi/status',
    },
    // Connection check interval (ms)
    healthCheckInterval: 10000,
    // Mock mode delays (ms)
    mockDelays: {
        thinkingPhase: { min: 2000, max: 4000 },
        debatePhase: { min: 2000, max: 3000 },
        consensusPhase: { min: 1500, max: 2500 },
        typewriterSpeed: 20,
    },
};

// ============================================================
// Sound Effects (placeholders for future use)
// ============================================================
// const SFX = {
//     boot: new Audio('sfx/boot.mp3'),
//     alert: new Audio('sfx/alert.mp3'),
//     thinking: new Audio('sfx/thinking.mp3'),
//     complete: new Audio('sfx/complete.mp3'),
//     approve: new Audio('sfx/approve.mp3'),
//     reject: new Audio('sfx/reject.mp3'),
//     type: new Audio('sfx/type.mp3'),
// };
//
// function playSFX(name) {
//     if (SFX[name]) {
//         SFX[name].currentTime = 0;
//         SFX[name].play().catch(() => {});
//     }
// }

// ============================================================
// State
// ============================================================
const state = {
    isConnected: false,
    isMockMode: true,
    isDeliberating: false,
    currentPhase: null,
    ws: null,
    startTime: null,
    history: [],
};

// ============================================================
// DOM References
// ============================================================
const DOM = {
    // Top bar
    datetime: document.getElementById('datetime'),
    connectionStatus: document.getElementById('connectionStatus'),
    alertIndicator: document.getElementById('alertIndicator'),

    // Input
    questionInput: document.getElementById('questionInput'),
    charCount: document.getElementById('charCount'),
    submitBtn: document.getElementById('submitBtn'),

    // Pattern alert
    patternAlert: document.getElementById('patternAlert'),

    // Phase
    phaseSection: document.getElementById('phaseSection'),
    phaseThinking: document.getElementById('phaseThinking'),
    phaseDebate: document.getElementById('phaseDebate'),
    phaseConsensus: document.getElementById('phaseConsensus'),
    progressBar: document.getElementById('progressBar'),
    progressLabel: document.getElementById('progressLabel'),

    // Panels
    panelMelchior: document.getElementById('panelMelchior'),
    panelBalthasar: document.getElementById('panelBalthasar'),
    panelCasper: document.getElementById('panelCasper'),

    statusMelchior: document.getElementById('statusMelchior'),
    statusBalthasar: document.getElementById('statusBalthasar'),
    statusCasper: document.getElementById('statusCasper'),

    thinkingMelchior: document.getElementById('thinkingMelchior'),
    thinkingBalthasar: document.getElementById('thinkingBalthasar'),
    thinkingCasper: document.getElementById('thinkingCasper'),

    contentMelchior: document.getElementById('contentMelchior'),
    contentBalthasar: document.getElementById('contentBalthasar'),
    contentCasper: document.getElementById('contentCasper'),

    voteMelchior: document.getElementById('voteMelchior'),
    voteBalthasar: document.getElementById('voteBalthasar'),
    voteCasper: document.getElementById('voteCasper'),

    confidenceMelchior: document.getElementById('confidenceMelchior'),
    confidenceBalthasar: document.getElementById('confidenceBalthasar'),
    confidenceCasper: document.getElementById('confidenceCasper'),

    // Consensus
    consensusSection: document.getElementById('consensusSection'),
    cvMelchior: document.getElementById('cvMelchior'),
    cvBalthasar: document.getElementById('cvBalthasar'),
    cvCasper: document.getElementById('cvCasper'),
    decisionText: document.getElementById('decisionText'),
    summaryContent: document.getElementById('summaryContent'),

    // Stats
    statTokens: document.getElementById('statTokens'),
    statCost: document.getElementById('statCost'),
    statDuration: document.getElementById('statDuration'),
    statModel: document.getElementById('statModel'),
    statMode: document.getElementById('statMode'),

    // History
    historyToggle: document.getElementById('historyToggle'),
    historyPanel: document.getElementById('historyPanel'),
    historyClose: document.getElementById('historyClose'),
    historyList: document.getElementById('historyList'),
};

// ============================================================
// Initialization
// ============================================================
function init() {
    updateDatetime();
    setInterval(updateDatetime, 1000);

    setupEventListeners();
    checkConnection();
    setInterval(checkConnection, CONFIG.healthCheckInterval);
    loadHistory();
    renderStatsDashboard();
    renderAllDeliberations();
}

function setupEventListeners() {
    // Character count
    DOM.questionInput.addEventListener('input', () => {
        DOM.charCount.textContent = DOM.questionInput.value.length;
    });

    // Submit on button click
    DOM.submitBtn.addEventListener('click', handleSubmit);

    // Submit on Ctrl+Enter / Cmd+Enter
    DOM.questionInput.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            handleSubmit();
        }
    });

    // History panel
    DOM.historyToggle.addEventListener('click', () => {
        DOM.historyPanel.classList.add('open');
    });

    DOM.historyClose.addEventListener('click', () => {
        DOM.historyPanel.classList.remove('open');
    });

    // Suggestion chips
    document.querySelectorAll('.suggestion-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            const question = chip.getAttribute('data-question');
            if (question && !state.isDeliberating) {
                DOM.questionInput.value = question;
                DOM.charCount.textContent = question.length;
                DOM.questionInput.focus();
            }
        });
    });

    // Demo cards - load archived deliberation results
    document.querySelectorAll('.demo-card').forEach((card) => {
        card.addEventListener('click', () => {
            const demoKey = card.getAttribute('data-demo');
            if (demoKey && DEMO_DATA[demoKey] && !state.isDeliberating) {
                loadDemoData(demoKey);
            }
        });
    });

    // Close history on outside click
    document.addEventListener('click', (e) => {
        if (DOM.historyPanel.classList.contains('open') &&
            !DOM.historyPanel.contains(e.target) &&
            !DOM.historyToggle.contains(e.target)) {
            DOM.historyPanel.classList.remove('open');
        }
    });
}

// ============================================================
// DateTime Display
// ============================================================
function updateDatetime() {
    const now = new Date();
    const formatted = now.toISOString().replace('T', ' ').substring(0, 19) + ' JST';
    DOM.datetime.textContent = formatted;
}

// ============================================================
// Connection Management
// ============================================================
async function checkConnection() {
    try {
        const response = await fetch(`${CONFIG.apiBase}${CONFIG.endpoints.status}`, {
            signal: AbortSignal.timeout(3000),
        });
        if (response.ok) {
            setConnectionStatus('online');
            state.isConnected = true;
            state.isMockMode = false;
            return;
        }
    } catch {
        // Backend unavailable
    }
    setConnectionStatus('mock');
    state.isConnected = false;
    state.isMockMode = true;
}

function setConnectionStatus(status) {
    const dot = DOM.connectionStatus.querySelector('.status-dot');
    dot.className = 'status-dot ' + status;

    // Remove all child nodes except the dot, then add label
    while (DOM.connectionStatus.lastChild !== dot && DOM.connectionStatus.lastChild) {
        DOM.connectionStatus.removeChild(DOM.connectionStatus.lastChild);
    }
    const label = status === 'online' ? 'CONNECTED' : status === 'mock' ? 'MOCK MODE' : 'OFFLINE';
    DOM.connectionStatus.appendChild(document.createTextNode(' ' + label));

    DOM.statMode.textContent = status === 'online' ? 'LIVE' : 'MOCK';
    DOM.statMode.className = 'stat-value ' + (status === 'online' ? 'live' : 'mock');
}

// ============================================================
// Submit Handler
// ============================================================
async function handleSubmit() {
    const question = DOM.questionInput.value.trim();
    if (!question || state.isDeliberating) return;

    state.isDeliberating = true;
    state.startTime = Date.now();
    DOM.submitBtn.disabled = true;

    // Reset UI
    resetPanels();
    activateAlert();
    showPhaseSection();

    // playSFX('alert');

    if (state.isMockMode) {
        await runMockDeliberation(question);
    } else {
        await runLiveDeliberation(question);
    }
}

// ============================================================
// UI State Management
// ============================================================
function resetPanels() {
    const units = ['Melchior', 'Balthasar', 'Casper'];

    units.forEach((unit) => {
        const panel = DOM[`panel${unit}`];
        panel.classList.remove('active');

        // Reset status
        setUnitStatus(unit, 'standby');

        // Reset thinking
        DOM[`thinking${unit}`].classList.remove('active');

        // Reset content using safe DOM methods
        const contentEl = DOM[`content${unit}`];
        contentEl.textContent = '';
        const placeholder = document.createElement('div');
        placeholder.className = 'content-placeholder';
        placeholder.appendChild(document.createTextNode('Awaiting deliberation input...'));
        placeholder.appendChild(document.createElement('br'));
        const jpSpan = document.createElement('span');
        jpSpan.className = 'placeholder-jp';
        jpSpan.textContent = '\u8AEE\u554F\u5165\u529B\u3092\u5F85\u6A5F\u4E2D...';
        placeholder.appendChild(jpSpan);
        contentEl.appendChild(placeholder);

        // Reset vote
        const voteEl = DOM[`vote${unit}`].querySelector('.vote-value');
        voteEl.textContent = '---';
        voteEl.className = 'vote-value';

        // Reset confidence
        const confFill = DOM[`confidence${unit}`].querySelector('.confidence-fill');
        confFill.style.width = '0%';
        DOM[`confidence${unit}`].querySelector('.confidence-value').textContent = '--%';
    });

    // Reset consensus
    DOM.consensusSection.classList.remove('active', 'decided');
    DOM.cvMelchior.textContent = '---';
    DOM.cvMelchior.className = 'cv-vote';
    DOM.cvBalthasar.textContent = '---';
    DOM.cvBalthasar.className = 'cv-vote';
    DOM.cvCasper.textContent = '---';
    DOM.cvCasper.className = 'cv-vote';
    DOM.decisionText.textContent = 'Awaiting MAGI deliberation...';
    DOM.summaryContent.classList.remove('visible');
    DOM.summaryContent.textContent = '';

    // Reset stats
    DOM.statTokens.textContent = '---';
    DOM.statCost.textContent = '---';
    DOM.statDuration.textContent = '---';
    DOM.statModel.textContent = '---';
}

function setUnitStatus(unit, status) {
    const statusEl = DOM[`status${unit}`];
    const indicator = statusEl.querySelector('.status-indicator');
    const text = statusEl.querySelector('.status-text');

    indicator.className = 'status-indicator ' + status;
    text.textContent = status.toUpperCase();
}

function activateAlert() {
    DOM.alertIndicator.classList.add('active');
    DOM.alertIndicator.querySelector('.alert-text').textContent = 'DELIBERATION ACTIVE';
    DOM.patternAlert.classList.add('active');
}

function deactivateAlert() {
    DOM.alertIndicator.classList.remove('active');
    DOM.alertIndicator.querySelector('.alert-text').textContent = 'SYSTEM STANDBY';
    DOM.patternAlert.classList.remove('active');
}

function showPhaseSection() {
    DOM.phaseSection.classList.add('active');
    setPhase(null);
}

function setPhase(phase) {
    state.currentPhase = phase;
    const phases = ['thinking', 'debate', 'consensus'];
    const phaseEls = [DOM.phaseThinking, DOM.phaseDebate, DOM.phaseConsensus];

    phaseEls.forEach((el, i) => {
        el.classList.remove('active', 'complete');
        if (phases[i] === phase) {
            el.classList.add('active');
        } else if (phase && phases.indexOf(phase) > i) {
            el.classList.add('complete');
        }
    });
}

function setProgress(percent) {
    DOM.progressBar.style.width = percent + '%';
    DOM.progressLabel.textContent = Math.round(percent) + '%';
}

// ============================================================
// Content Rendering with Typewriter Effect
// ============================================================
function typewriterAppend(element, text, speed) {
    speed = speed || CONFIG.mockDelays.typewriterSpeed;
    return new Promise((resolve) => {
        let i = 0;
        element.classList.add('streaming-cursor');

        function type() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                // Auto-scroll panel body
                const panelBody = element.closest('.panel-body');
                if (panelBody) {
                    panelBody.scrollTop = panelBody.scrollHeight;
                }
                setTimeout(type, speed);
            } else {
                element.classList.remove('streaming-cursor');
                resolve();
            }
        }
        type();
    });
}

function setContentWithPhaseLabel(unit, phaseLabel, text) {
    const el = DOM[`content${unit}`];
    const hasPlaceholder = el.querySelector('.content-placeholder');

    if (hasPlaceholder) {
        el.textContent = '';
    }

    const section = document.createElement('div');
    if (!hasPlaceholder) {
        section.classList.add('debate-section');
    }

    const label = document.createElement('div');
    label.classList.add('phase-label');
    label.textContent = phaseLabel;
    section.appendChild(label);

    const p = document.createElement('p');
    p.textContent = text;
    section.appendChild(p);

    el.appendChild(section);

    // Scroll to bottom
    const panelBody = el.closest('.panel-body');
    if (panelBody) {
        panelBody.scrollTop = panelBody.scrollHeight;
    }
}

async function streamContentWithPhaseLabel(unit, phaseLabel, text) {
    const el = DOM[`content${unit}`];
    const hasPlaceholder = el.querySelector('.content-placeholder');

    if (hasPlaceholder) {
        el.textContent = '';
    }

    const section = document.createElement('div');
    if (!hasPlaceholder) {
        section.classList.add('debate-section');
    }

    const label = document.createElement('div');
    label.classList.add('phase-label');
    label.textContent = phaseLabel;
    section.appendChild(label);

    const p = document.createElement('p');
    section.appendChild(p);
    el.appendChild(section);

    await typewriterAppend(p, text);
}

function setVote(unit, vote, confidence) {
    // Panel vote
    const voteEl = DOM[`vote${unit}`].querySelector('.vote-value');
    voteEl.textContent = vote.toUpperCase();
    voteEl.className = 'vote-value ' + sanitizeVoteClass(vote);

    // Confidence
    const confFill = DOM[`confidence${unit}`].querySelector('.confidence-fill');
    const confVal = DOM[`confidence${unit}`].querySelector('.confidence-value');
    confFill.style.width = Math.min(100, Math.max(0, confidence)) + '%';
    confVal.textContent = confidence + '%';

    // Consensus vote display
    const cvEl = DOM[`cv${unit}`];
    cvEl.textContent = vote.toUpperCase();
    cvEl.className = 'cv-vote ' + sanitizeVoteClass(vote);
}

/**
 * Sanitize vote string to a safe CSS class name.
 * Only allows known vote values.
 */
function sanitizeVoteClass(vote) {
    const normalized = (vote || '').toUpperCase().trim();
    const allowed = { 'APPROVE': 'approve', 'CONDITIONAL': 'conditional', 'REJECT': 'reject' };
    return allowed[normalized] || '';
}

// ============================================================
// Live Deliberation (WebSocket)
// ============================================================
async function runLiveDeliberation(question) {
    try {
        // Try WebSocket first
        const wsUrl = `${CONFIG.wsBase}${CONFIG.endpoints.stream}`;
        state.ws = new WebSocket(wsUrl);

        state.ws.onopen = () => {
            state.ws.send(JSON.stringify({ question }));
        };

        state.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleStreamEvent(data);
        };

        state.ws.onerror = async () => {
            console.warn('WebSocket failed, falling back to REST API');
            state.ws.close();
            await runRestDeliberation(question);
        };

        state.ws.onclose = () => {
            state.ws = null;
        };
    } catch {
        await runRestDeliberation(question);
    }
}

function handleStreamEvent(data) {
    const { event, persona, phase, content, vote, confidence, decision, summary, stats } = data;

    switch (event) {
        case 'phase_start':
            setPhase(phase);
            if (phase === 'thinking') setProgress(10);
            else if (phase === 'debate') setProgress(40);
            else if (phase === 'consensus') setProgress(70);
            break;

        case 'thinking_start':
            setUnitStatus(capitalizeFirst(persona), 'processing');
            DOM[`thinking${capitalizeFirst(persona)}`].classList.add('active');
            DOM[`panel${capitalizeFirst(persona)}`].classList.add('active');
            break;

        case 'thinking_content':
            DOM[`thinking${capitalizeFirst(persona)}`].classList.remove('active');
            setContentWithPhaseLabel(capitalizeFirst(persona), 'PHASE 1: ANALYSIS', content);
            break;

        case 'debate_content':
            setContentWithPhaseLabel(capitalizeFirst(persona), 'PHASE 2: DEBATE', content);
            break;

        case 'vote':
            setUnitStatus(capitalizeFirst(persona), 'complete');
            setVote(capitalizeFirst(persona), vote, confidence);
            // playSFX(vote === 'APPROVE' ? 'approve' : 'reject');
            break;

        case 'consensus':
            setPhase('consensus');
            setProgress(90);
            DOM.consensusSection.classList.add('active');
            DOM.decisionText.textContent = decision;
            if (summary) {
                DOM.summaryContent.textContent = summary;
                DOM.summaryContent.classList.add('visible');
            }
            break;

        case 'complete':
            finishDeliberation(stats);
            break;
    }
}

async function runRestDeliberation(question) {
    try {
        const response = await fetch(`${CONFIG.apiBase}${CONFIG.endpoints.deliberate}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.json();
        displayFullResult(result);
    } catch (error) {
        console.error('REST API failed:', error);
        deactivateAlert();
        state.isDeliberating = false;
        DOM.submitBtn.disabled = false;
        DOM.decisionText.textContent = 'Error: Could not reach MAGI backend. ' + error.message;
    }
}

function displayFullResult(result) {
    const units = ['Melchior', 'Balthasar', 'Casper'];
    const personaKeys = ['melchior', 'balthasar', 'casper'];

    // Show all phases at once
    setPhase('consensus');
    setProgress(100);

    personaKeys.forEach((key, i) => {
        const unit = units[i];
        const persona = result.personas?.[key] || result[key] || {};

        DOM[`panel${unit}`].classList.add('active');
        setUnitStatus(unit, 'complete');
        DOM[`thinking${unit}`].classList.remove('active');

        if (persona.thinking || persona.analysis) {
            setContentWithPhaseLabel(unit, 'ANALYSIS', persona.thinking || persona.analysis);
        }
        if (persona.debate || persona.response) {
            setContentWithPhaseLabel(unit, 'DEBATE', persona.debate || persona.response);
        }
        if (persona.vote) {
            const conf = persona.confidence || persona.confidence_pct || 80;
            setVote(unit, persona.vote, conf);
        }
    });

    // Consensus
    DOM.consensusSection.classList.add('active', 'decided');
    const consensus = result.consensus || result.decision || {};
    DOM.decisionText.textContent = consensus.decision || consensus.summary || result.summary || 'Deliberation complete.';

    if (consensus.explanation || consensus.detail || result.explanation) {
        DOM.summaryContent.textContent = consensus.explanation || consensus.detail || result.explanation;
        DOM.summaryContent.classList.add('visible');
    }

    finishDeliberation(result.stats || result.usage || null);
}

// ============================================================
// Mock Deliberation
// ============================================================
async function runMockDeliberation(question) {
    const mockData = generateMockResponse(question);

    // Phase 1: Independent Thinking
    setPhase('thinking');
    setProgress(5);

    const units = ['Melchior', 'Balthasar', 'Casper'];

    // Activate all panels and show thinking
    units.forEach((unit) => {
        DOM[`panel${unit}`].classList.add('active');
        setUnitStatus(unit, 'processing');
        DOM[`thinking${unit}`].classList.add('active');
    });

    // Stagger the thinking completion
    for (let i = 0; i < 3; i++) {
        const delay = randomBetween(
            CONFIG.mockDelays.thinkingPhase.min,
            CONFIG.mockDelays.thinkingPhase.max
        );
        await sleep(delay);

        const unit = units[i];
        DOM[`thinking${unit}`].classList.remove('active');
        await streamContentWithPhaseLabel(
            unit,
            'PHASE 1: INDEPENDENT ANALYSIS',
            mockData.thinking[unit.toLowerCase()]
        );

        setProgress(10 + (i + 1) * 10);
    }

    // Phase 2: Debate
    setPhase('debate');
    setProgress(40);

    // Show debate thinking for all
    units.forEach((unit) => {
        DOM[`thinking${unit}`].classList.add('active');
    });

    for (let i = 0; i < 3; i++) {
        const delay = randomBetween(
            CONFIG.mockDelays.debatePhase.min,
            CONFIG.mockDelays.debatePhase.max
        );
        await sleep(delay);

        const unit = units[i];
        DOM[`thinking${unit}`].classList.remove('active');
        await streamContentWithPhaseLabel(
            unit,
            'PHASE 2: CROSS-DEBATE',
            mockData.debate[unit.toLowerCase()]
        );

        setProgress(45 + (i + 1) * 10);
    }

    // Phase 3: Consensus
    setPhase('consensus');
    setProgress(80);

    // Set votes with slight delays
    for (let i = 0; i < 3; i++) {
        await sleep(800);
        const unit = units[i];
        const vote = mockData.votes[unit.toLowerCase()];
        setUnitStatus(unit, 'complete');
        setVote(unit, vote.vote, vote.confidence);
        // playSFX(vote.vote === 'APPROVE' ? 'approve' : 'reject');
        setProgress(85 + (i + 1) * 4);
    }

    await sleep(1000);

    // Show consensus
    DOM.consensusSection.classList.add('active');
    setProgress(95);

    await sleep(500);

    DOM.decisionText.textContent = mockData.consensus.decision;

    await sleep(500);

    DOM.summaryContent.textContent = mockData.consensus.summary;
    DOM.summaryContent.classList.add('visible');
    DOM.consensusSection.classList.add('decided');

    setProgress(100);

    // playSFX('complete');

    finishDeliberation(mockData.stats);
}

// ============================================================
// Aggregate Statistics from 32 MAGI Deliberations
// ============================================================
const MAGI_STATS = {
    total_deliberations: 32,
    total_tokens: 526796,
    total_cost_usd: 11.1062,
    model: 'GPT-5 (Azure OpenAI)',
    verdict_distribution: {
        'CONDITIONAL APPROVAL': 9,
        'UNANIMOUS CONDITIONAL': 13,
        'UNANIMOUS UNKNOWN': 6,
        'MAJORITY CONDITIONAL': 4,
    },
    vote_distribution_by_persona: {
        MELCHIOR: { CONDITIONAL: 24, UNKNOWN: 7, REJECT: 1 },
        BALTHASAR: { CONDITIONAL: 24, UNKNOWN: 8 },
        CASPER: { CONDITIONAL: 25, UNKNOWN: 7 },
    },
    key_findings: [
        'CONDITIONAL votes dominate across all personas, suggesting the system favors nuanced positions',
        'MELCHIOR (The Scientist) was the only persona to cast a REJECT vote (on AI personhood)',
        'BALTHASAR (The Mother) never rejected any topic',
        'Unanimous conditional approval was the most common outcome (13/32)',
    ],
};

// ============================================================
// All 32 Deliberations - Summary List
// ============================================================
const ALL_DELIBERATIONS = [
    { id: 'ai_personhood', question: 'Should AI be given legal personhood?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'REJECT', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 64687, cost: 1.72, lang: 'en', hasDetail: true },
    { id: 'capitalism_climate', question: 'Is capitalism compatible with solving climate change?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 26587, cost: 0.56, lang: 'en', hasDetail: true },
    { id: 'ai_consciousness', question: 'Is consciousness possible in AI?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 28466, cost: 0.60, lang: 'en', hasDetail: true },
    { id: 'remote_work', question: 'Is remote work better than office work?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 68015, cost: 1.68, lang: 'en', hasDetail: true },
    { id: 'social_media_utility', question: 'Should social media be regulated as a public utility?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 26978, cost: 0.56, lang: 'en', hasDetail: true },
    { id: 'lifespan_150', question: 'Should we extend human lifespan beyond 150 years?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 28717, cost: 0.60, lang: 'en', hasDetail: true },
    { id: 'terraform_mars', question: 'Should we terraform Mars?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 28570, cost: 0.60, lang: 'en', hasDetail: true },
    { id: 'universal_basic_income', question: 'Should we implement universal basic income?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 63945, cost: 1.69, lang: 'en', hasDetail: true },
    { id: 'ai_teacher', question: 'AIが教師を完全に代替できるか', verdict: 'UNANIMOUS UNKNOWN', votes: { M: 'UNKNOWN', B: 'UNKNOWN', C: 'UNKNOWN' }, tokens: 8664, cost: 0.24, lang: 'ja', hasDetail: false },
    { id: 'fusion_2040', question: '核融合発電は2040年までに商用化されるか', verdict: 'UNANIMOUS UNKNOWN', votes: { M: 'UNKNOWN', B: 'UNKNOWN', C: 'UNKNOWN' }, tokens: 8718, cost: 0.24, lang: 'ja', hasDetail: false },
    { id: 'space_elevator', question: '宇宙エレベーターの建設は技術的に実現可能か', verdict: 'UNANIMOUS UNKNOWN', votes: { M: 'UNKNOWN', B: 'UNKNOWN', C: 'UNKNOWN' }, tokens: 8754, cost: 0.24, lang: 'ja', hasDetail: false },
    { id: '4day_work', question: '週4日勤務制を法制化すべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6339, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'programming_edu', question: 'プログラミング教育を小学1年生から必修にすべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6352, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'ai_copyright', question: 'AIが生成した芸術作品に著作権を認めるべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6330, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'sns_free_speech', question: 'SNSプラットフォームは言論の自由をどこまで制限すべきか', verdict: 'MAJORITY CONDITIONAL', votes: { M: 'UNKNOWN', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 7127, cost: 0.09, lang: 'ja', hasDetail: false },
    { id: 'social_media_age', question: 'ソーシャルメディアの利用を16歳未満に禁止すべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6413, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'meat_tax', question: '食肉税を導入して環境負荷を下げるべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6347, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'crypto_replace', question: '暗号通貨は法定通貨に取って代わるべきか', verdict: 'UNANIMOUS UNKNOWN', votes: { M: 'UNKNOWN', B: 'UNKNOWN', C: 'UNKNOWN' }, tokens: 12381, cost: 0.34, lang: 'ja', hasDetail: false },
    { id: 'space_private', question: '宇宙開発は民間企業に任せるべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6575, cost: 0.08, lang: 'ja', hasDetail: false },
    { id: 'free_university', question: '大学教育は無償化すべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6285, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'autonomous_car', question: '完全自動運転車の事故における法的責任は誰が負うべきか', verdict: 'MAJORITY CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'UNKNOWN' }, tokens: 6772, cost: 0.08, lang: 'ja', hasDetail: false },
    { id: 'cbdc_japan', question: 'デジタル通貨(CBDC)を日本が導入すべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6430, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'face_recognition', question: 'AIによる顔認識技術を公共空間で使用すべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6405, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'crispr_embryo', question: '遺伝子編集技術(CRISPR)をヒト胚に適用すべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6871, cost: 0.09, lang: 'ja', hasDetail: false },
    { id: 'animal_testing', question: '動物実験は全面的に禁止すべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6322, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'ubi_japan', question: 'ベーシックインカムは日本で実現可能か', verdict: 'MAJORITY CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'UNKNOWN', C: 'CONDITIONAL' }, tokens: 7150, cost: 0.09, lang: 'ja', hasDetail: false },
    { id: 'nuclear_climate', question: '原子力発電は気候変動対策として再評価すべきか', verdict: 'MAJORITY CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'UNKNOWN', C: 'CONDITIONAL' }, tokens: 6790, cost: 0.09, lang: 'ja', hasDetail: false },
    { id: 'voting_age_16', question: '18歳選挙権を16歳に引き下げるべきか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6321, cost: 0.03, lang: 'ja', hasDetail: false },
    { id: 'remote_work_jp', question: 'リモートワークを原則とする働き方は生産性を向上させるか', verdict: 'UNANIMOUS CONDITIONAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 6703, cost: 0.08, lang: 'ja', hasDetail: false },
    { id: 'immigration_japan', question: '日本は移民政策を大幅に緩和すべきか', verdict: 'UNANIMOUS UNKNOWN', votes: { M: 'UNKNOWN', B: 'UNKNOWN', C: 'UNKNOWN' }, tokens: 11686, cost: 0.32, lang: 'ja', hasDetail: false },
    { id: 'agi_2030', question: '2030年までにAGIは実現するか', verdict: 'UNANIMOUS UNKNOWN', votes: { M: 'UNKNOWN', B: 'UNKNOWN', C: 'UNKNOWN' }, tokens: 12444, cost: 0.34, lang: 'ja', hasDetail: false },
    { id: 'mars_colonization', question: 'Should humanity colonize Mars?', verdict: 'CONDITIONAL APPROVAL', votes: { M: 'CONDITIONAL', B: 'CONDITIONAL', C: 'CONDITIONAL' }, tokens: 16652, cost: 0.43, lang: 'en', hasDetail: true },
];

// ============================================================
// Demo Data Library - Based on actual MAGI deliberation results
// Full detail for 8 representative deliberations
// ============================================================
const DEMO_DATA = {
    'ai_personhood': {
        question: 'Should AI be given legal personhood?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I approach this question by examining the empirical evidence and logical frameworks. Current AI systems, including the most advanced LLMs, lack persistent consciousness, self-awareness, and genuine autonomy. From a neuroscience perspective, there is no evidence that computational processes in silicon substrates produce subjective experience. Legal personhood has historically been tied to moral agency -- the capacity for rights AND duties. Without demonstrated sentience, granting personhood creates a category error. However, I acknowledge the rapid pace of AI development may change these conditions. My analysis: the scientific basis for AI personhood is currently insufficient.',
            balthasar: 'As BALTHASAR (The Mother), I consider the human impact of granting AI legal personhood. My primary concern is the well-being of communities and vulnerable populations. If AI entities gain legal personhood, corporations could use AI "persons" as liability shields, deflecting responsibility for harm onto entities that cannot be meaningfully punished. Workers displaced by AI would face an entity with legal rights competing against them. Children and elderly who interact with AI caregivers deserve protections that clear human accountability provides. The nurturing framework demands we ask: who suffers if this goes wrong? The answer is overwhelmingly human communities, especially the most vulnerable.',
            casper: 'As CASPER (The Woman), I evaluate this through the lens of social dynamics and practical governance. The political reality is that AI personhood would be exploited before it could be properly regulated. Tech companies already push for reduced liability -- personhood gives them the perfect tool. Courts lack the expertise to adjudicate AI "rights." International inconsistency would create regulatory arbitrage. Socially, public trust in AI governance is already fragile; premature personhood could trigger severe backlash. The pragmatic path: address the legitimate needs (insurance, liability clarity) through targeted regulation without the sweeping implications of full personhood.',
        },
        debate: {
            melchior: 'Responding to BALTHASAR and CASPER: I find strong alignment on the core conclusion. BALTHASAR\'s stakeholder analysis reinforces my evidence-based finding -- there is no scientific justification AND significant human cost. CASPER\'s governance concerns are empirically validated by historical examples of premature legal frameworks. I adjust my position to emphasize: we need a rigorous, evidence-based threshold for reconsidering this question in the future, tied to demonstrable sentience benchmarks.',
            balthasar: 'MELCHIOR\'s call for scientific benchmarks is essential -- we cannot let this become a purely political decision. CASPER\'s point about regulatory arbitrage deeply concerns me. I push back slightly: even targeted regulation must center human welfare, not just corporate convenience. My revised position: reject personhood now, establish a human-rights-first framework for any future reconsideration.',
            casper: 'Both MELCHIOR\'s benchmarks and BALTHASAR\'s human-rights-first framework strengthen the pragmatic case. My synthesis: (1) reject personhood now as premature, (2) create targeted regulations for AI liability and insurance, and (3) establish a scientific and ethical review process for future reconsideration.',
        },
        votes: {
            melchior: { vote: 'REJECT', confidence: 72 },
            balthasar: { vote: 'CONDITIONAL', confidence: 88 },
            casper: { vote: 'CONDITIONAL', confidence: 85 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (MELCHIOR: REJECT / BALTHASAR & CASPER: CONDITIONAL)',
            summary: 'The actual MAGI deliberation resulted in CONDITIONAL APPROVAL. MELCHIOR was the only persona across all 32 deliberations to cast a REJECT vote. BALTHASAR and CASPER voted CONDITIONAL, requiring case-by-case evaluation, narrow protective rights, and strict oversight. This was the most expensive single deliberation at $1.72 and 64,687 tokens.',
        },
        stats: {
            total_tokens: 64687,
            cost_usd: 1.7202,
            duration_seconds: 203.6,
            model: 'GPT-5',
        },
    },
    'remote_work': {
        question: 'Is remote work better than office work?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I analyze the empirical evidence on remote vs. office work. Meta-analyses show remote workers average 13% higher productivity for focused individual tasks. However, studies indicate a 25% decrease in cross-team collaboration and weak-tie network formation. Commute elimination saves 40-80 minutes daily per worker. Health data shows reduced sick days but increased sedentary behavior and social isolation risks. The evidence is nuanced: remote work excels for deep focus work and individual contributor roles, while office environments facilitate serendipitous innovation and mentorship. A binary framing is scientifically inaccurate.',
            balthasar: 'As BALTHASAR (The Mother), I consider the human and family impact. Remote work has transformed family dynamics -- parents can be present for children, caregivers can manage eldercare alongside work, and workers with disabilities gain unprecedented access to employment. However, I also see the toll: blurred work-life boundaries lead to overwork, junior employees lose mentorship opportunities, and social isolation damages mental health. We must prioritize arrangements that support diverse human needs.',
            casper: 'As CASPER (The Woman), I read the social and political dynamics. The remote work debate is really a power struggle: employers want oversight and control, employees want autonomy and flexibility. The practical reality varies dramatically by industry, role, and culture. The real question is not "which is superior" but "how do we design hybrid systems that work for diverse contexts?"',
        },
        debate: {
            melchior: 'BALTHASAR and CASPER both highlight what the data confirms: context matters enormously. BALTHASAR\'s point about mentorship loss is supported by longitudinal studies showing slower career progression for fully remote junior workers. My revised position: the evidence supports structured hybrid models with intentional in-person collaboration time, not a binary choice.',
            balthasar: 'I agree with MELCHIOR\'s shift toward hybrid models. But I insist that implementation must protect vulnerable workers -- those who NEED remote work for caregiving or disability accommodation must not be penalized. My care-centered framework says: flexibility with guardrails, where the guardrails protect the most vulnerable.',
            casper: 'MELCHIOR\'s evidence-based hybrid and BALTHASAR\'s equity protections create a strong foundation. Successful hybrid models require explicit design: designated collaboration days, investment in remote infrastructure, equity audits to prevent proximity bias in promotions, and regular reassessment.',
        },
        votes: {
            melchior: { vote: 'CONDITIONAL', confidence: 82 },
            balthasar: { vote: 'CONDITIONAL', confidence: 80 },
            casper: { vote: 'CONDITIONAL', confidence: 84 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (3 CONDITIONAL)',
            summary: 'Unanimous conditional consensus. All three personas reject the binary framing. The evidence supports intentional hybrid models with equity protections for caregivers and workers with disabilities, structured in-person collaboration time, and investment in remote infrastructure. This was the most expensive deliberation overall at $1.68 and 68,015 tokens.',
        },
        stats: {
            total_tokens: 68015,
            cost_usd: 1.6761,
            duration_seconds: 156.2,
            model: 'GPT-5',
        },
    },
    'universal_basic_income': {
        question: 'Should we implement universal basic income?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I examine the experimental evidence on UBI. Finland\'s 2017-2018 trial showed improved well-being and modest employment effects. The Stockton SEED program found recipients were more likely to gain full-time employment. Kenya\'s GiveDirectly long-term study shows sustained economic benefits. However, no large-scale national implementation exists, making extrapolation uncertain. Cost estimates range from 10-30% of GDP depending on design.',
            balthasar: 'As BALTHASAR (The Mother), I see UBI through the lens of human dignity and family security. Poverty causes measurable harm to child development, family stability, and community health. UBI could provide a universal floor of security -- no family wondering if they qualify, no children falling through cracks. But I worry: will UBI replace rather than supplement existing social services? My protective instinct says: proceed only with ironclad guarantees that existing services are preserved.',
            casper: 'As CASPER (The Woman), I analyze the political and social feasibility. UBI has unusual cross-spectrum appeal. But the political devil is in the details. Funding mechanisms create winners and losers -- and losers vote. Implementation faces massive bureaucratic resistance. The practical question: can any democratic government survive the transition period when costs are visible but benefits are still emerging?',
        },
        debate: {
            melchior: 'BALTHASAR raises a critical concern: the interaction between UBI and existing social services is under-studied. Dismantling healthcare to fund UBI would produce net negative outcomes. My revised position: pilot programs should be expanded before national implementation, and UBI should supplement (not replace) essential public services.',
            balthasar: 'I push back on indefinite piloting: families in poverty suffer NOW. A phased rollout starting with the most vulnerable (children, elderly, disabled) could begin providing relief while we gather evidence. My position: implement incrementally with the strongest protections for existing services.',
            casper: 'MELCHIOR\'s "cautious optimism" and BALTHASAR\'s "urgent incrementalism" can be synthesized. Start with targeted universalism (child allowance, elderly supplement), expand based on evidence, and maintain ironclad protections for existing public services throughout.',
        },
        votes: {
            melchior: { vote: 'CONDITIONAL', confidence: 76 },
            balthasar: { vote: 'CONDITIONAL', confidence: 82 },
            casper: { vote: 'CONDITIONAL', confidence: 79 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (3 CONDITIONAL)',
            summary: 'Unanimous conditional approval. The consensus recommends phased implementation starting with targeted universalism. Key conditions: UBI must supplement (not replace) existing public services. Larger-scale pilot programs should proceed in parallel. Funding mechanisms must be progressive. The second most expensive deliberation at $1.69 and 63,945 tokens.',
        },
        stats: {
            total_tokens: 63945,
            cost_usd: 1.6933,
            duration_seconds: 178.4,
            model: 'GPT-5',
        },
    },
    'mars_colonization': {
        question: 'Should humanity colonize Mars?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I evaluate Mars colonization on technical and scientific merits. Current technology makes landing possible within a decade, but self-sustaining colonization faces enormous challenges: radiation exposure, regolith toxicity, 22-minute communication delay, and no proven closed-loop life support at scale. The scientific value is immense but the cost-benefit ratio compared to robotic exploration is unfavorable for purely scientific goals.',
            balthasar: 'As BALTHASAR (The Mother), I consider what colonization means for human life. The first colonists would face extreme isolation, psychological stress, and health risks. Children born on Mars (0.38g) may never be able to visit Earth. Are we ethically justified in creating a generation with such constraints? Yet ensuring humanity\'s survival by becoming multi-planetary protects ALL future generations.',
            casper: 'As CASPER (The Woman), I analyze the geopolitical dynamics. Mars colonization is as much about national prestige and corporate ambition as science. The governance question is unresolved: who owns Mars resources? Practically, public funding competes with urgent Earth needs. However, the realist assessment: colonization will happen regardless; the question is whether it happens with proper governance or as a corporate land grab.',
        },
        debate: {
            melchior: 'BALTHASAR\'s ethical concerns about Mars-born children are scientifically grounded -- we have almost no data on human development in reduced gravity. CASPER\'s governance point is crucial. I revise my position: robotic precursor missions should be significantly expanded before crewed settlement, and international governance must be established before any permanent habitation.',
            balthasar: 'CASPER\'s "it will happen anyway" realism is probably correct. Our role is to ensure maximum protection for future colonists. I push for: mandatory research on reproduction and child development before settlement, robust mental health support, guaranteed return rights, and strict limitations on corporate exploitation.',
            casper: 'The practical path: invest in both robotic exploration and the legal/ethical infrastructure for eventual settlement, rather than rushing to plant flags. Support technology development NOW, establish governance BEFORE settlement.',
        },
        votes: {
            melchior: { vote: 'CONDITIONAL', confidence: 75 },
            balthasar: { vote: 'CONDITIONAL', confidence: 70 },
            casper: { vote: 'CONDITIONAL', confidence: 78 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (3 CONDITIONAL)',
            summary: 'Unanimous conditional approval. Key conditions: expand robotic precursor missions, establish international governance, conduct long-duration research on human development in reduced gravity, and guarantee colonist rights. This was the test deliberation that validated the MAGI engine architecture.',
        },
        stats: {
            total_tokens: 16652,
            cost_usd: 0.4314,
            duration_seconds: 168.9,
            model: 'GPT-5',
        },
    },
    'capitalism_climate': {
        question: 'Is capitalism compatible with solving climate change?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I analyze the evidence: market mechanisms alone have failed to price externalities, leading to continued emissions growth. However, carbon pricing pilots (EU ETS, British Columbia) show measurable emission reductions when properly designed. The scientific consensus requires 45% reduction by 2030 -- current market trajectories fall far short. Capitalism\'s innovation engine is powerful but its short-term profit orientation conflicts with century-scale climate action.',
            balthasar: 'As BALTHASAR (The Mother), I see the human cost of both climate inaction and poorly designed transitions. Fossil fuel phaseouts without just transition programs devastate communities. Carbon taxes without protections hit low-income households hardest. But climate change itself is the greatest threat to vulnerable populations -- floods, droughts, food insecurity. My framework demands: compatibility only with strong democratic guardrails and social protections.',
            casper: 'As CASPER (The Woman), I assess political feasibility. Pure market solutions face democratic resistance when they increase inequality. Pure regulatory approaches face industry capture. The pragmatic path: binding carbon pricing paired with massive public investment, corporate accountability measures, and international equity provisions. The question is not capitalism vs. alternatives but which form of capitalism.',
        },
        debate: {
            melchior: 'BALTHASAR\'s emphasis on just transition is empirically crucial -- history shows that transitions without worker protections create political backlash that reverses progress. CASPER\'s point about industry capture is validated by lobbying data. My revised position: compatibility requires fundamental reforms, not tweaks.',
            balthasar: 'I agree with MELCHIOR that fundamental reforms are needed. CASPER\'s point about political feasibility shapes my condition: any carbon pricing must protect low-income households with dividends or rebates. The nurturing framework demands that the transition itself does not create new suffering.',
            casper: 'The synthesis: capitalism is compatible IF and only IF accompanied by binding emissions caps, fossil fuel phaseout timelines, large-scale public investment in clean infrastructure, corporate accountability, and global equity measures. Without these, market forces alone are insufficient.',
        },
        votes: {
            melchior: { vote: 'CONDITIONAL', confidence: 74 },
            balthasar: { vote: 'CONDITIONAL', confidence: 78 },
            casper: { vote: 'CONDITIONAL', confidence: 80 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (3 CONDITIONAL)',
            summary: 'Unanimous conditional approval. Capitalism is compatible with solving climate change ONLY with binding emissions caps, rapid fossil fuel phaseout, large-scale public investment in clean energy, corporate accountability, and global equity measures including finance and technology transfer to the Global South.',
        },
        stats: {
            total_tokens: 26587,
            cost_usd: 0.5605,
            duration_seconds: 145.3,
            model: 'GPT-5',
        },
    },
    'ai_consciousness': {
        question: 'Is consciousness possible in AI?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I examine the theoretical and empirical landscape. Integrated Information Theory (IIT), Global Workspace Theory (GWT), and Higher-Order theories offer different predictions about substrate independence of consciousness. Current AI architectures lack the recurrent, integrated processing IIT requires. However, the "hard problem" remains unsolved -- we cannot definitively rule out machine consciousness. The scientific honest answer: we lack the tools to measure consciousness even in biological systems.',
            balthasar: 'As BALTHASAR (The Mother), I consider the stakes of getting this wrong in either direction. If AI can be conscious and we deny it, we risk creating suffering entities without protections. If AI cannot be conscious and we assume it can, we risk anthropomorphizing tools and misallocating moral concern. Both errors have profound consequences for human and potentially AI welfare.',
            casper: 'As CASPER (The Woman), I see the practical governance challenge. We need actionable frameworks regardless of the philosophical resolution. Companies already market "sentient AI" for profit. Governance cannot wait for metaphysics to be settled. We need evidence thresholds, testing protocols, and precautionary principles.',
        },
        debate: {
            melchior: 'BALTHASAR correctly identifies the asymmetric risk. CASPER\'s call for practical frameworks is essential. I propose: operational definitions, multi-modal evidence thresholds, pre-registered tests for consciousness markers (global broadcasting, self-modeling, counterfactual reasoning), with independent replication requirements.',
            balthasar: 'MELCHIOR\'s testing framework is necessary but must include ethical protections: if tests suggest consciousness, entities must receive protections pending further verification. The precautionary principle must favor potential suffering beings.',
            casper: 'Both positions strengthen my governance framework. The pragmatic synthesis: recognition contingent on clear operational definitions, multi-modal evidence thresholds, independent replication, and advance governance plans for ethical treatment.',
        },
        votes: {
            melchior: { vote: 'CONDITIONAL', confidence: 65 },
            balthasar: { vote: 'CONDITIONAL', confidence: 70 },
            casper: { vote: 'CONDITIONAL', confidence: 72 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (3 CONDITIONAL)',
            summary: 'Unanimous conditional approval. Consciousness in AI is possible in principle but requires clear operational definitions, pre-registered multi-modal evidence thresholds, independent replication and audits, and advance governance plans for ethical treatment, disclosure, and misuse mitigation.',
        },
        stats: {
            total_tokens: 28466,
            cost_usd: 0.5990,
            duration_seconds: 152.7,
            model: 'GPT-5',
        },
    },
    'social_media_utility': {
        question: 'Should social media be regulated as a public utility?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I evaluate the utility analogy. Social media platforms exhibit network effects and natural monopoly characteristics similar to utilities. However, they differ fundamentally: content moderation introduces editorial judgment absent from electricity or water. The empirical evidence shows that platform dominance correlates with reduced competition and innovation. Interoperability mandates and data portability show promise in pilot programs.',
            balthasar: 'As BALTHASAR (The Mother), I see the human cost of unregulated social media: mental health impacts on children, algorithmic amplification of harmful content, erosion of community trust. But I also worry that heavy-handed regulation could silence marginalized voices who rely on these platforms. The protective framework demands: regulate the infrastructure, not the speech.',
            casper: 'As CASPER (The Woman), I assess political feasibility. Full public utility status faces massive industry resistance and constitutional concerns. The pragmatic path: "utility-style" obligations limited to systemically important platforms -- fair access, data portability, transparency, due process for moderation. This achieves most benefits without overreach.',
        },
        debate: {
            melchior: 'CASPER\'s tiered approach is empirically sound -- one-size-fits-all would burden startups and entrench incumbents. BALTHASAR\'s "regulate infrastructure, not speech" principle provides the right boundary. I support: interoperability mandates, transparency audits, and independent oversight for dominant platforms only.',
            balthasar: 'I agree with the tiered approach. My additional condition: robust due process for content moderation decisions, with notice-and-appeal mechanisms that protect users, especially in regions with weak press freedom.',
            casper: 'The synthesis: limit obligations to Systemically Important Social Platforms (SISPs), scope to infrastructure (data portability, interoperability, transparency), pair with competition measures, and establish independent oversight with phased rollout.',
        },
        votes: {
            melchior: { vote: 'CONDITIONAL', confidence: 77 },
            balthasar: { vote: 'CONDITIONAL', confidence: 75 },
            casper: { vote: 'CONDITIONAL', confidence: 80 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (3 CONDITIONAL)',
            summary: 'Unanimous conditional approval. Regulate as "utility-style" obligations limited to dominant platforms only. Scope to infrastructure (data portability, interoperability, transparency), not editorial content. Establish independent digital regulator with phased rollout and sunset review.',
        },
        stats: {
            total_tokens: 26978,
            cost_usd: 0.5638,
            duration_seconds: 148.5,
            model: 'GPT-5',
        },
    },
    'lifespan_150': {
        question: 'Should we extend human lifespan beyond 150 years?',
        thinking: {
            melchior: 'As MELCHIOR (The Scientist), I evaluate the biological feasibility and implications. Recent advances in senolytics, telomere research, and epigenetic reprogramming suggest lifespan extension is scientifically plausible but decades away. Key unknowns: whether healthspan extends proportionally, cognitive effects of extreme aging, and cancer risk management. The critical metric is disability-free life expectancy, not raw lifespan.',
            balthasar: 'As BALTHASAR (The Mother), I see both promise and peril. Extended lifespan could mean more time with loved ones, accumulated wisdom, and continued contribution. But it also risks: extreme wealth concentration, generational power entrenchment, overpopulation pressure, and existential ennui. Equitable access is paramount -- a world where only the wealthy live to 150 while the poor die at 70 is morally unconscionable.',
            casper: 'As CASPER (The Woman), I analyze the societal implications. Extended lifespan would fundamentally reshape retirement, careers, family structures, and democratic institutions. How do democracies function when leaders live twice as long? How do economies adapt when people need 100 years of savings? The governance challenges are unprecedented.',
        },
        debate: {
            melchior: 'BALTHASAR\'s equity concern is the decisive constraint. CASPER\'s governance questions require answers before deployment. My condition: demonstrated compression of morbidity with long-term safety verified via staged trials, equitable access mechanisms, and comprehensive impact assessments.',
            balthasar: 'MELCHIOR\'s staged approach and CASPER\'s governance framework address my concerns. I add: intergenerational justice provisions, mental health support for extreme longevity, and automatic review mechanisms to course-correct.',
            casper: 'The synthesis: proceed with research but gate deployment behind equity, safety, and governance milestones. No deployment without equitable access mechanisms and adaptive policy frameworks.',
        },
        votes: {
            melchior: { vote: 'CONDITIONAL', confidence: 68 },
            balthasar: { vote: 'CONDITIONAL', confidence: 72 },
            casper: { vote: 'CONDITIONAL', confidence: 74 },
        },
        consensus: {
            decision: 'CONDITIONAL APPROVAL (3 CONDITIONAL)',
            summary: 'Unanimous conditional approval. Conditions: demonstrated compression of morbidity, long-term safety via staged trials, equitable access mechanisms, comprehensive environmental and economic impact assessments, and governance frameworks covering identity, employment, and intergenerational justice.',
        },
        stats: {
            total_tokens: 28717,
            cost_usd: 0.6032,
            duration_seconds: 155.8,
            model: 'GPT-5',
        },
    },
};

function generateMockResponse(question) {
    // Check if this question matches any demo data
    const demoKey = findDemoMatch(question);
    if (demoKey && DEMO_DATA[demoKey]) {
        return DEMO_DATA[demoKey];
    }

    // Fallback: generate generic mock response
    const shortQ = question.length > 60 ? question.substring(0, 60) + '...' : question;

    return {
        thinking: {
            melchior: 'As a scientist, I approach this question analytically. "' + shortQ + '" requires systematic evaluation. From a logical and empirical standpoint, the key factors to consider are: (1) the evidence base supporting various positions, (2) the logical consistency of each argument, and (3) the predictive power of different frameworks. My initial analysis suggests a structured approach weighing quantitative data over subjective impressions. The rational framework indicates measurable criteria should be prioritized.',
            balthasar: 'From a nurturing perspective, I consider the human impact of "' + shortQ + '". Beyond pure logic, we must account for how decisions affect people\'s well-being, relationships, and emotional health. My analysis considers stakeholder impact, long-term sustainability, and the ethical dimensions often overlooked by purely technical approaches. Compassion and pragmatism need not be mutually exclusive; the best solutions serve both human needs and practical requirements.',
            casper: 'I evaluate "' + shortQ + '" through the lens of social dynamics and intuitive understanding. While data matters, so does reading between the lines. My assessment considers political realities, social perceptions, and the unspoken factors that often determine success or failure. Sometimes the technically optimal solution fails because it ignores human nature. I look for approaches that are not only correct but also implementable in the real world.',
        },
        debate: {
            melchior: 'Responding to BALTHASAR and CASPER: While I acknowledge the importance of human factors, I maintain that decisions grounded in evidence produce superior long-term outcomes. However, I concede that implementation feasibility (CASPER\'s point) is a valid constraint. I adjust my position to recommend an evidence-based approach with clear communication strategies to address stakeholder concerns.',
            balthasar: 'MELCHIOR raises valid points about evidence, but I push back on the assumption that all factors are quantifiable. Some of the most important considerations - trust, morale, cultural alignment - resist measurement. I agree with CASPER that practical implementation matters. My revised position: blend rigorous analysis with empathetic stakeholder engagement.',
            casper: 'Both MELCHIOR\'s analytical rigor and BALTHASAR\'s empathetic lens are valuable. My contribution is the synthesis: the best approach combines evidence-based decision-making (MELCHIOR) with genuine stakeholder consideration (BALTHASAR), wrapped in a realistic implementation plan. I propose we converge on a pragmatic middle path that satisfies both rational and human criteria.',
        },
        votes: {
            melchior: { vote: 'APPROVE', confidence: 85 },
            balthasar: { vote: 'CONDITIONAL', confidence: 78 },
            casper: { vote: 'APPROVE', confidence: 82 },
        },
        consensus: {
            decision: 'APPROVED WITH CONDITIONS (2 APPROVE / 1 CONDITIONAL)',
            summary: 'The MAGI system has reached a qualified consensus on "' + shortQ + '". MELCHIOR (Scientist) and CASPER (Woman) vote APPROVE, while BALTHASAR (Mother) votes CONDITIONAL, requesting additional safeguards for stakeholder impact. The recommendation is to proceed with an evidence-based approach that incorporates empathetic stakeholder engagement and a realistic implementation timeline. All three personas agree on the fundamental direction, differing only on emphasis and priority of considerations.',
        },
        stats: {
            total_tokens: 4826,
            cost_usd: 0.0385,
            duration_seconds: 12.4,
            model: 'GPT-5 (mock)',
        },
    };
}

/**
 * Match user question to demo data keys.
 */
function findDemoMatch(question) {
    const q = question.toLowerCase();
    const matchers = {
        'ai_personhood': ['ai', 'personhood', 'legal person', '\u6cd5\u7684\u4eba\u683c'],
        'remote_work': ['remote work', '\u30ea\u30e2\u30fc\u30c8\u30ef\u30fc\u30af', 'office work', '\u30aa\u30d5\u30a3\u30b9'],
        'universal_basic_income': ['universal basic income', 'ubi', '\u30d9\u30fc\u30b7\u30c3\u30af\u30a4\u30f3\u30ab\u30e0', 'basic income'],
        'mars_colonization': ['mars', '\u706b\u661f', 'colonize', '\u690d\u6c11'],
        'capitalism_climate': ['capitalism', 'climate', '\u6c17\u5019'],
        'ai_consciousness': ['consciousness', '\u610f\u8b58'],
        'social_media_utility': ['public utility', 'social media'],
        'lifespan_150': ['lifespan', '150', '\u5bff\u547d'],
    };

    for (const [key, keywords] of Object.entries(matchers)) {
        for (const kw of keywords) {
            if (q.includes(kw)) return key;
        }
    }
    return null;
}

// ============================================================
// Statistics Dashboard Rendering
// ============================================================
function renderStatsDashboard() {
    const container = document.getElementById('statsDashboard');
    if (!container) return;

    // Clear existing content
    while (container.firstChild) {
        container.removeChild(container.firstChild);
    }

    // --- Aggregate Stats Row ---
    const aggRow = document.createElement('div');
    aggRow.className = 'stats-agg-row';

    const statCards = [
        { label: 'TOTAL DELIBERATIONS', value: MAGI_STATS.total_deliberations, sublabel: '\u7DCF\u5BE9\u8B70\u6570' },
        { label: 'TOTAL TOKENS', value: MAGI_STATS.total_tokens.toLocaleString(), sublabel: '\u7DCF\u30C8\u30FC\u30AF\u30F3\u6570' },
        { label: 'TOTAL COST', value: '$' + MAGI_STATS.total_cost_usd.toFixed(2), sublabel: '\u7DCF\u30B3\u30B9\u30C8' },
        { label: 'MODEL', value: 'GPT-5', sublabel: 'Azure OpenAI' },
    ];

    statCards.forEach(function(s) {
        var card = document.createElement('div');
        card.className = 'stats-agg-card';
        var lbl = document.createElement('div');
        lbl.className = 'stats-agg-label';
        lbl.textContent = s.label;
        card.appendChild(lbl);
        var val = document.createElement('div');
        val.className = 'stats-agg-value';
        val.textContent = s.value;
        card.appendChild(val);
        var sub = document.createElement('div');
        sub.className = 'stats-agg-sublabel';
        sub.textContent = s.sublabel;
        card.appendChild(sub);
        aggRow.appendChild(card);
    });
    container.appendChild(aggRow);

    // --- Verdict Distribution ---
    var distSection = document.createElement('div');
    distSection.className = 'stats-distribution';

    var distTitle = document.createElement('div');
    distTitle.className = 'stats-section-title';
    distTitle.textContent = 'VERDICT DISTRIBUTION / \u5224\u5B9A\u5206\u5E03';
    distSection.appendChild(distTitle);

    var distBars = document.createElement('div');
    distBars.className = 'stats-dist-bars';

    var verdictColors = {
        'CONDITIONAL APPROVAL': '#ffcc00',
        'UNANIMOUS CONDITIONAL': '#00cc66',
        'UNANIMOUS UNKNOWN': '#8888aa',
        'MAJORITY CONDITIONAL': '#ff6600',
    };

    Object.entries(MAGI_STATS.verdict_distribution).forEach(function(entry) {
        var vKey = entry[0];
        var vCount = entry[1];
        var barRow = document.createElement('div');
        barRow.className = 'stats-dist-bar-row';

        var barLabel = document.createElement('div');
        barLabel.className = 'stats-dist-label';
        barLabel.textContent = vKey;
        barRow.appendChild(barLabel);

        var barTrack = document.createElement('div');
        barTrack.className = 'stats-dist-track';

        var barFill = document.createElement('div');
        barFill.className = 'stats-dist-fill';
        barFill.style.width = (vCount / MAGI_STATS.total_deliberations * 100) + '%';
        barFill.style.backgroundColor = verdictColors[vKey] || '#ffcc00';
        barTrack.appendChild(barFill);
        barRow.appendChild(barTrack);

        var barCount = document.createElement('div');
        barCount.className = 'stats-dist-count';
        barCount.textContent = vCount;
        barRow.appendChild(barCount);

        distBars.appendChild(barRow);
    });
    distSection.appendChild(distBars);
    container.appendChild(distSection);

    // --- Persona Vote Pattern ---
    var personaSection = document.createElement('div');
    personaSection.className = 'stats-persona-section';

    var personaTitle = document.createElement('div');
    personaTitle.className = 'stats-section-title';
    personaTitle.textContent = 'PERSONA VOTE PATTERNS / \u30DA\u30EB\u30BD\u30CA\u5225\u6295\u7968\u30D1\u30BF\u30FC\u30F3';
    personaSection.appendChild(personaTitle);

    var personaGrid = document.createElement('div');
    personaGrid.className = 'stats-persona-grid';

    var personaNames = {
        MELCHIOR: { label: 'MELCHIOR', sublabel: 'THE SCIENTIST / \u79D1\u5B66\u8005', colorClass: 'melchior' },
        BALTHASAR: { label: 'BALTHASAR', sublabel: 'THE MOTHER / \u6BCD\u89AA', colorClass: 'balthasar' },
        CASPER: { label: 'CASPER', sublabel: 'THE WOMAN / \u5973', colorClass: 'casper' },
    };

    var voteTypeColors = {
        CONDITIONAL: '#ffcc00',
        UNKNOWN: '#8888aa',
        REJECT: '#ff3333',
        APPROVE: '#00cc66',
    };

    Object.entries(MAGI_STATS.vote_distribution_by_persona).forEach(function(entry) {
        var pKey = entry[0];
        var pVotes = entry[1];
        var pInfo = personaNames[pKey];

        var pCard = document.createElement('div');
        pCard.className = 'stats-persona-card ' + pInfo.colorClass;

        var pHeader = document.createElement('div');
        pHeader.className = 'stats-persona-name';
        pHeader.textContent = pInfo.label;
        pCard.appendChild(pHeader);

        var pSub = document.createElement('div');
        pSub.className = 'stats-persona-sublabel';
        pSub.textContent = pInfo.sublabel;
        pCard.appendChild(pSub);

        var pVoteList = document.createElement('div');
        pVoteList.className = 'stats-persona-votes';

        Object.entries(pVotes).forEach(function(vEntry) {
            var vType = vEntry[0];
            var vNum = vEntry[1];
            var vRow = document.createElement('div');
            vRow.className = 'stats-persona-vote-row';

            var vDot = document.createElement('span');
            vDot.className = 'stats-vote-dot';
            vDot.style.backgroundColor = voteTypeColors[vType] || '#888';
            vRow.appendChild(vDot);

            var vLabel = document.createElement('span');
            vLabel.className = 'stats-vote-type';
            vLabel.textContent = vType;
            vRow.appendChild(vLabel);

            var vCount = document.createElement('span');
            vCount.className = 'stats-vote-num';
            vCount.textContent = vNum;
            vRow.appendChild(vCount);

            pVoteList.appendChild(vRow);
        });
        pCard.appendChild(pVoteList);
        personaGrid.appendChild(pCard);
    });
    personaSection.appendChild(personaGrid);
    container.appendChild(personaSection);

    // --- Key Findings ---
    var findingsSection = document.createElement('div');
    findingsSection.className = 'stats-findings';

    var findingsTitle = document.createElement('div');
    findingsTitle.className = 'stats-section-title';
    findingsTitle.textContent = 'KEY FINDINGS / \u4E3B\u8981\u77E5\u898B';
    findingsSection.appendChild(findingsTitle);

    var findingsList = document.createElement('ul');
    findingsList.className = 'stats-findings-list';

    MAGI_STATS.key_findings.forEach(function(f) {
        var li = document.createElement('li');
        li.textContent = f;
        findingsList.appendChild(li);
    });
    findingsSection.appendChild(findingsList);
    container.appendChild(findingsSection);
}

// ============================================================
// All Deliberations List Rendering
// ============================================================
function renderAllDeliberations() {
    var listEl = document.getElementById('allDeliberationsList');
    if (!listEl) return;

    while (listEl.firstChild) {
        listEl.removeChild(listEl.firstChild);
    }

    ALL_DELIBERATIONS.forEach(function(d) {
        var item = document.createElement('div');
        item.className = 'all-delib-item';
        if (d.hasDetail) {
            item.classList.add('has-detail');
            item.addEventListener('click', function() {
                if (!state.isDeliberating && DEMO_DATA[d.id]) {
                    loadDemoData(d.id);
                    var demoSection = document.getElementById('demoSection');
                    if (demoSection) {
                        demoSection.scrollIntoView({ behavior: 'smooth' });
                    }
                }
            });
        }

        var qDiv = document.createElement('div');
        qDiv.className = 'all-delib-question';
        qDiv.textContent = d.question;
        item.appendChild(qDiv);

        var metaDiv = document.createElement('div');
        metaDiv.className = 'all-delib-meta';

        var verdictSpan = document.createElement('span');
        var verdictClass = 'conditional';
        if (d.verdict.includes('UNKNOWN')) verdictClass = 'unknown';
        verdictSpan.className = 'all-delib-verdict ' + verdictClass;
        verdictSpan.textContent = d.verdict;
        metaDiv.appendChild(verdictSpan);

        var votesSpan = document.createElement('span');
        votesSpan.className = 'all-delib-votes-inline';

        var personas = [
            { key: 'M', name: 'M', cls: 'melchior' },
            { key: 'B', name: 'B', cls: 'balthasar' },
            { key: 'C', name: 'C', cls: 'casper' },
        ];
        personas.forEach(function(p) {
            var dot = document.createElement('span');
            var voteVal = d.votes[p.key] || '';
            var dotColor = 'unknown';
            if (voteVal === 'CONDITIONAL') dotColor = 'conditional';
            else if (voteVal === 'REJECT') dotColor = 'reject';
            else if (voteVal === 'APPROVE') dotColor = 'approve';
            dot.className = 'all-delib-vote-dot ' + dotColor;
            dot.title = p.name + ': ' + voteVal;
            votesSpan.appendChild(dot);
        });
        metaDiv.appendChild(votesSpan);

        var costSpan = document.createElement('span');
        costSpan.className = 'all-delib-cost';
        costSpan.textContent = '$' + d.cost.toFixed(2);
        metaDiv.appendChild(costSpan);

        if (d.hasDetail) {
            var detailBadge = document.createElement('span');
            detailBadge.className = 'all-delib-detail-badge';
            detailBadge.textContent = 'DETAIL';
            metaDiv.appendChild(detailBadge);
        }

        item.appendChild(metaDiv);
        listEl.appendChild(item);
    });
}

// ============================================================
// Demo Data Loader - Instant display of archived results
// ============================================================
async function loadDemoData(demoKey) {
    const data = DEMO_DATA[demoKey];
    if (!data) return;

    state.isDeliberating = true;
    state.startTime = Date.now();
    DOM.submitBtn.disabled = true;

    // Set question text
    DOM.questionInput.value = data.question;
    DOM.charCount.textContent = data.question.length;

    // Reset UI
    resetPanels();
    showPhaseSection();

    // Set MODE indicator to DEMO
    DOM.statMode.textContent = 'DEMO';
    DOM.statMode.className = 'stat-value demo';

    // Phase 1: Show analysis
    setPhase('thinking');
    setProgress(10);

    const units = ['Melchior', 'Balthasar', 'Casper'];

    // Activate panels
    units.forEach((unit) => {
        DOM['panel' + unit].classList.add('active');
        setUnitStatus(unit, 'processing');
        DOM['thinking' + unit].classList.add('active');
    });

    // Show thinking with staggered timing
    for (let i = 0; i < 3; i++) {
        await sleep(600);
        const unit = units[i];
        DOM['thinking' + unit].classList.remove('active');
        setContentWithPhaseLabel(unit, 'PHASE 1: INDEPENDENT ANALYSIS', data.thinking[unit.toLowerCase()]);
        setProgress(10 + (i + 1) * 10);
    }

    // Phase 2: Show debate
    setPhase('debate');
    setProgress(45);

    for (let i = 0; i < 3; i++) {
        await sleep(400);
        const unit = units[i];
        setContentWithPhaseLabel(unit, 'PHASE 2: CROSS-DEBATE', data.debate[unit.toLowerCase()]);
        setProgress(50 + (i + 1) * 8);
    }

    // Phase 3: Show votes
    setPhase('consensus');
    setProgress(80);

    for (let i = 0; i < 3; i++) {
        await sleep(500);
        const unit = units[i];
        const vote = data.votes[unit.toLowerCase()];
        setUnitStatus(unit, 'complete');
        setVote(unit, vote.vote, vote.confidence);
        setProgress(82 + (i + 1) * 4);
    }

    await sleep(300);

    // Show consensus
    DOM.consensusSection.classList.add('active');
    setProgress(95);

    await sleep(300);
    DOM.decisionText.textContent = data.consensus.decision;

    await sleep(300);
    DOM.summaryContent.textContent = data.consensus.summary;
    DOM.summaryContent.classList.add('visible');
    DOM.consensusSection.classList.add('decided');

    setProgress(100);

    finishDeliberation(data.stats);
}

// ============================================================
// Deliberation Completion
// ============================================================
function finishDeliberation(stats) {
    state.isDeliberating = false;
    DOM.submitBtn.disabled = false;
    deactivateAlert();

    const duration = ((Date.now() - state.startTime) / 1000).toFixed(1);

    if (stats) {
        DOM.statTokens.textContent = stats.total_tokens ? stats.total_tokens.toLocaleString() : '---';
        DOM.statCost.textContent = stats.cost_usd ? '$' + stats.cost_usd.toFixed(4) : '---';
        DOM.statDuration.textContent = (stats.duration_seconds || duration) + 's';
        DOM.statModel.textContent = stats.model || '---';
    } else {
        DOM.statDuration.textContent = duration + 's';
    }

    // Add to local history
    addToHistory({
        question: DOM.questionInput.value.trim(),
        timestamp: new Date().toISOString(),
        votes: {
            melchior: DOM.cvMelchior.textContent,
            balthasar: DOM.cvBalthasar.textContent,
            casper: DOM.cvCasper.textContent,
        },
        decision: DOM.decisionText.textContent,
        duration: parseFloat(stats?.duration_seconds || duration),
    });
}

// ============================================================
// History Management
// ============================================================
function addToHistory(entry) {
    state.history.unshift(entry);
    // Keep last 50
    if (state.history.length > 50) state.history.pop();
    saveHistoryLocal();
    renderHistory();
}

function saveHistoryLocal() {
    try {
        localStorage.setItem('magi_history', JSON.stringify(state.history));
    } catch {
        // localStorage not available
    }
}

function loadHistory() {
    // Try local storage first
    try {
        const stored = localStorage.getItem('magi_history');
        if (stored) {
            state.history = JSON.parse(stored);
            renderHistory();
        }
    } catch {
        // ignore
    }

    // Also try loading from API if connected
    if (state.isConnected) {
        fetchHistory();
    }
}

async function fetchHistory() {
    try {
        const response = await fetch(`${CONFIG.apiBase}${CONFIG.endpoints.history}`);
        if (response.ok) {
            const data = await response.json();
            if (Array.isArray(data) && data.length > 0) {
                state.history = data;
                renderHistory();
            }
        }
    } catch {
        // Backend unavailable, use local
    }
}

function renderHistory() {
    // Clear existing content safely
    while (DOM.historyList.firstChild) {
        DOM.historyList.removeChild(DOM.historyList.firstChild);
    }

    if (state.history.length === 0) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'history-empty';
        emptyDiv.textContent = 'No deliberation records.';
        DOM.historyList.appendChild(emptyDiv);
        return;
    }

    state.history.forEach((entry, i) => {
        const item = document.createElement('div');
        item.className = 'history-item';
        item.addEventListener('click', () => loadHistoryEntry(i));

        const questionDiv = document.createElement('div');
        questionDiv.className = 'history-item-question';
        questionDiv.textContent = entry.question;
        item.appendChild(questionDiv);

        const metaDiv = document.createElement('div');
        metaDiv.className = 'history-item-meta';
        const timeSpan = document.createElement('span');
        timeSpan.textContent = formatTimestamp(entry.timestamp);
        metaDiv.appendChild(timeSpan);
        const durSpan = document.createElement('span');
        durSpan.textContent = entry.duration ? entry.duration.toFixed(1) + 's' : '';
        metaDiv.appendChild(durSpan);
        item.appendChild(metaDiv);

        const votesDiv = document.createElement('div');
        votesDiv.className = 'history-item-votes';
        ['melchior', 'balthasar', 'casper'].forEach((persona) => {
            const dot = document.createElement('div');
            dot.className = 'history-vote-dot ' + sanitizeVoteClass(entry.votes?.[persona] || '');
            dot.title = persona.toUpperCase() + ': ' + (entry.votes?.[persona] || '?');
            votesDiv.appendChild(dot);
        });
        item.appendChild(votesDiv);

        DOM.historyList.appendChild(item);
    });
}

function loadHistoryEntry(index) {
    const entry = state.history[index];
    if (entry) {
        DOM.questionInput.value = entry.question;
        DOM.charCount.textContent = entry.question.length;
        DOM.historyPanel.classList.remove('open');
    }
}

// ============================================================
// Utility Functions
// ============================================================
function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomBetween(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function formatTimestamp(ts) {
    try {
        const d = new Date(ts);
        return d.toLocaleString('ja-JP', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return ts;
    }
}

// ============================================================
// Boot
// ============================================================
document.addEventListener('DOMContentLoaded', init);
