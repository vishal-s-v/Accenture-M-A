'use strict';

// ── State ──────────────────────────────────────────────────
const state = {
    taskId: null,
    pollTimer: null,
    report: null,
    targetIdx: 0,
};

// ── DOM Shortcuts ──────────────────────────────────────────
const $ = id => document.getElementById(id);
const el = {
    projectSelect: $('projectSelect'),
    deleteBtn: $('deleteProjectBtn'),
    maForm: $('maForm'),
    acquirer: $('acquirerInput'),
    industryFocus: $('industryFocus'),
    geographyPref: $('geographyPref'),
    revenueRange: $('revenueRange'),
    acqBudget: $('acquisitionBudget'),
    strategicGoals: $('strategicGoals'),
    techAreas: $('technologyAreas'),
    riskAppetite: $('riskAppetite'),
    timeHorizon: $('timeHorizon'),
    ollamaModel: $('ollamaModel'),
    simulate: $('simulateCheckbox'),
    runBtn: $('runBtn'),
    runBtnText: $('runBtnText'),
    runBtnSpinner: $('runBtnSpinner'),
    runBtnIcon: $('runBtnIcon'),

    // Ollama
    ollamaStatus: $('ollamaStatus'),
    ollamaStatusText: $('ollamaStatusText'),

    // Views
    welcomeView: $('welcomeView'),
    runnerView: $('runnerView'),
    reportView: $('reportView'),

    // Runner
    pipelineStatusText: $('pipelineStatusText'),
    pipelineBadge: $('pipelineBadge'),
    pipelineBadgeText: $('pipelineBadgeText'),
    progressPct: $('progressPct'),
    progressFill: $('progressFill'),
    terminalBody: $('terminalBody'),
    providerBadge: $('providerBadge'),

    // Report
    reportTitle: $('reportTitle'),
    reportDate: $('reportDate'),
    reportProviderBadge: $('reportProviderBadge'),

    // Exec summary
    acquirerRationale: $('acquirerRationale'),
    strategicPriorities: $('strategicPriorities'),
    gapCapability: $('gapCapability'),
    gapMarket: $('gapMarket'),
    gapTech: $('gapTech'),
    gapCustomer: $('gapCustomer'),
    gapGeo: $('gapGeo'),
    roadmap: $('roadmap'),

    // Industry
    industryStructure: $('industryStructure'),
    consolidationTrends: $('consolidationTrends'),
    growthSegments: $('growthSegments'),
    emergingTech: $('emergingTech'),
    disruptionRisks: $('disruptionRisks'),

    // Longlist
    longlistBody: $('longlistBody'),

    // Deep dive
    targetList: $('targetList'),
    targetDetail: $('targetDetail'),

    // Partner
    partnerCritique: $('partnerCritique'),
    hiddenOpportunities: $('hiddenOpportunities'),
    hiddenRisks: $('hiddenRisks'),
    partnerQA: $('partnerQA'),
};

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    bindEvents();
    checkOllamaConnection();
});

// ── Event Binding ──────────────────────────────────────────
function bindEvents() {
    el.maForm.addEventListener('submit', handleSubmit);
    el.projectSelect.addEventListener('change', handleProjectChange);
    el.deleteBtn.addEventListener('click', handleDelete);

    // Report tabs
    document.querySelectorAll('.rtab').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Re-check Ollama when simulate is toggled off
    el.simulate.addEventListener('change', () => {
        if (!el.simulate.checked) checkOllamaConnection();
    });
}

async function checkOllamaConnection() {
    el.ollamaStatus.className = 'ollama-status checking';
    el.ollamaStatusText.textContent = 'Checking connection...';
    try {
        const resp = await fetch('http://localhost:11434/api/tags', { signal: AbortSignal.timeout(3000) });
        if (resp.ok) {
            el.ollamaStatus.className = 'ollama-status connected';
            el.ollamaStatusText.textContent = 'Ollama is running ✓';
        } else {
            throw new Error('non-ok');
        }
    } catch {
        el.ollamaStatus.className = 'ollama-status error';
        el.ollamaStatusText.textContent = 'Cannot reach localhost:11434';
    }
}

// ── View Management ────────────────────────────────────────
function showView(name) {
    el.welcomeView.classList.add('hidden');
    el.runnerView.classList.add('hidden');
    el.reportView.classList.add('hidden');

    if (name === 'welcome') el.welcomeView.classList.remove('hidden');
    else if (name === 'runner') el.runnerView.classList.remove('hidden');
    else if (name === 'report') el.reportView.classList.remove('hidden');
}

// ── Tab Management ─────────────────────────────────────────
function switchTab(tabName) {
    document.querySelectorAll('.rtab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.rtab-panel').forEach(panel => {
        panel.classList.add('hidden');
        panel.classList.remove('active');
    });
    const target = $(`tab-${tabName}`);
    if (target) {
        target.classList.remove('hidden');
        target.classList.add('active');
    }
}

// ── Projects ───────────────────────────────────────────────
async function loadProjects() {
    try {
        const projects = await apiFetch('/api/projects');
        const currentVal = el.projectSelect.value;
        el.projectSelect.innerHTML = '<option value="">— Select a run —</option>';
        projects.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.task_id;
            const label = p.simulate ? 'Sim' : (p.model || 'llama3.2:latest');
            opt.textContent = `${p.acquirer} · ${p.created_at} [${p.status}] (${label})`;
            el.projectSelect.appendChild(opt);
        });
        el.projectSelect.value = currentVal;
    } catch (e) {
        console.error('loadProjects:', e);
    }
}

async function handleProjectChange() {
    const taskId = el.projectSelect.value;
    stopPolling();

    if (!taskId) {
        state.taskId = null;
        state.report = null;
        el.deleteBtn.classList.add('hidden');
        showView('welcome');
        return;
    }

    state.taskId = taskId;
    el.deleteBtn.classList.remove('hidden');

    try {
        const data = await apiFetch(`/api/status/${taskId}`);
        if (data.status === 'completed') {
            await loadReport(taskId);
        } else if (data.status === 'failed') {
            resetRunner();
            updateRunner(data);
            showView('runner');
        } else {
            resetRunner();
            updateRunner(data);
            showView('runner');
            startPolling(taskId);
        }
    } catch (e) {
        alert('Failed to load project: ' + e.message);
    }
}

async function handleDelete() {
    if (!state.taskId) return;
    if (!confirm('Delete this M&A evaluation run permanently?')) return;
    try {
        await apiFetch(`/api/projects/${state.taskId}`, { method: 'DELETE' });
        el.projectSelect.value = '';
        state.taskId = null;
        state.report = null;
        el.deleteBtn.classList.add('hidden');
        await loadProjects();
        showView('welcome');
    } catch (e) {
        alert('Delete failed: ' + e.message);
    }
}

// ── Form Submit ────────────────────────────────────────────
async function handleSubmit(e) {
    e.preventDefault();

    const acquirer = el.acquirer.value.trim();
    if (!acquirer) return;

    const simulate = el.simulate.checked;
    const model = el.ollamaModel.value.trim() || 'llama3.2:latest';

    setRunBtnLoading(true);

    const payload = {
        acquirer,
        industry_focus: el.industryFocus.value.trim() || null,
        geography_preference: el.geographyPref.value.trim() || null,
        revenue_range: el.revenueRange.value.trim() || null,
        acquisition_budget: el.acqBudget.value.trim() || null,
        strategic_goals: el.strategicGoals.value.trim() || null,
        technology_areas: el.techAreas.value.trim() || null,
        risk_appetite: el.riskAppetite.value,
        time_horizon: el.timeHorizon.value.trim() || null,
        model,
        simulate,
    };

    try {
        const data = await apiFetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        state.taskId = data.task_id;
        el.providerBadge.textContent = simulate ? 'SIMULATION' : model;

        resetRunner();
        showView('runner');
        startPolling(data.task_id);

        await loadProjects();
        el.projectSelect.value = data.task_id;
        el.deleteBtn.classList.remove('hidden');
    } catch (err) {
        alert('Failed to start analysis: ' + err.message);
    } finally {
        setRunBtnLoading(false);
    }
}

function setRunBtnLoading(loading) {
    el.runBtn.disabled = loading;
    el.runBtnText.textContent = loading ? 'Launching Agents...' : 'Launch M&A Evaluation';
    el.runBtnSpinner.classList.toggle('hidden', !loading);
    el.runBtnIcon.classList.toggle('hidden', loading);
}

// ── Polling ────────────────────────────────────────────────
function startPolling(taskId) {
    stopPolling();
    state.pollTimer = setInterval(async () => {
        try {
            const data = await apiFetch(`/api/status/${taskId}`);
            updateRunner(data);

            if (data.status === 'completed') {
                stopPolling();
                await loadReport(taskId);
            } else if (data.status === 'failed') {
                stopPolling();
                el.pipelineBadgeText.textContent = 'Failed';
                el.pipelineBadge.style.borderColor = 'rgba(239,68,68,0.4)';
                el.progressFill.style.background = 'var(--red)';
            }
        } catch (e) {
            console.error('poll error:', e);
        }
    }, 1500);
}

function stopPolling() {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
}

function resetRunner() {
    el.progressPct.textContent = '0%';
    el.progressFill.style.width = '0%';
    el.terminalBody.innerHTML = '<div class="tline accent">&gt; Spawning multi-agent M&A pipeline...</div>';
    document.querySelectorAll('.flow-node, .flow-sub, .flow-group, .flow-arrow').forEach(n => {
        n.classList.remove('active', 'done');
    });
    el.pipelineBadgeText.textContent = 'Running';
    el.pipelineBadge.style.borderColor = '';
    el.progressFill.style.background = '';
}

function updateRunner(data) {
    el.pipelineStatusText.textContent = data.current_agent || 'Initializing...';
    el.progressPct.textContent = `${data.progress}%`;
    el.progressFill.style.width = `${data.progress}%`;
    el.providerBadge.textContent = data.simulate ? 'SIMULATION' : (data.model || 'llama3.2:latest');

    // Logs
    el.terminalBody.innerHTML = '';
    (data.logs || []).forEach(log => {
        const div = document.createElement('div');
        div.className = 'tline';
        if (log.includes('CRITICAL') || log.includes('ERROR') || log.includes('✗')) div.classList.add('error');
        else if (log.includes('✓') || log.includes('completed') || log.includes('Completed')) div.classList.add('success');
        else if (log.includes('Initializing') || log.includes('Starting') || log.includes('starting') || log.includes('Spawning')) div.classList.add('accent');
        else if (log.includes('Agent') || log.includes('Evaluating')) div.classList.add('info');
        div.textContent = `> ${log}`;
        el.terminalBody.appendChild(div);
    });
    el.terminalBody.scrollTop = el.terminalBody.scrollHeight;

    updateFlowDiagram(data.current_agent, data.progress);
}

function updateFlowDiagram(agent, progress) {
    const setNode = (id, state) => {
        const el = $(id);
        if (!el) return;
        el.classList.remove('active', 'done');
        if (state) el.classList.add(state);
    };

    const setArrow = (id, done) => {
        const el = $(id);
        if (!el) return;
        el.classList.toggle('done', done);
    };

    // Node 1
    if (progress >= 20) { setNode('fnode-1', 'done'); setArrow('farrow-1', true); }
    else if (agent?.includes('Strategy')) setNode('fnode-1', 'active');

    // Node 2
    if (progress >= 35) { setNode('fnode-2', 'done'); setArrow('farrow-2', true); }
    else if (agent?.includes('Industry')) setNode('fnode-2', 'active');

    // Node 3
    if (progress >= 45) setNode('fnode-3', 'done');
    else if (agent?.includes('Discovery') || agent?.includes('Target Discovery')) setNode('fnode-3', 'active');

    // Deep group
    // Order: 4=Tech, 5=Financial, 6=Risk (parallel) → 7=Synergies → 8=Devil's Advocate
    if (progress >= 90) {
        $('fgroup-deep').classList.remove('active');
        $('fgroup-deep').classList.add('done');
        ['fsub-4','fsub-5','fsub-6','fsub-7','fsub-8'].forEach(id => setNode(id, 'done'));
    } else if (progress >= 45) {
        $('fgroup-deep').classList.add('active');
        ['fsub-4','fsub-5','fsub-6','fsub-7','fsub-8'].forEach(id => setNode(id, null));

        if (agent?.includes('Synerg')) {
            // Agents 4-6 done, synergies running
            setNode('fsub-4', 'done'); setNode('fsub-5', 'done'); setNode('fsub-6', 'done');
            setNode('fsub-7', 'active');
        } else if (agent?.includes('Devil') || agent?.includes('Thesis') || agent?.includes('Challenging')) {
            setNode('fsub-4', 'done'); setNode('fsub-5', 'done'); setNode('fsub-6', 'done');
            setNode('fsub-7', 'done'); setNode('fsub-8', 'active');
        } else {
            // Parallel phase: Tech / Financial / Risk all active together
            setNode('fsub-4', 'active');
            setNode('fsub-5', 'active');
            setNode('fsub-6', 'active');
        }
    }

    // Node 9
    if (progress === 100) setNode('fnode-9', 'done');
    else if (agent?.includes('Partner')) setNode('fnode-9', 'active');
}

// ── Report ─────────────────────────────────────────────────
async function loadReport(taskId) {
    try {
        const results = await apiFetch(`/api/report/${taskId}`);
        const status = await apiFetch(`/api/status/${taskId}`);
        state.report = results;
        state.targetIdx = 0;
        renderReport(results, status);
        showView('report');
        switchTab('exec');
        loadProjects();
    } catch (e) {
        alert('Failed to load report: ' + e.message);
    }
}

function renderReport(data, status) {
    // Title + meta
    const acquirerName = el.projectSelect.options[el.projectSelect.selectedIndex]?.text?.split(' ·')[0] || 'Acquirer';
    el.reportTitle.innerHTML = `Strategic M&A Report: <span class="gradient-text">${acquirerName}</span>`;
    el.reportDate.textContent = `Generated ${status?.created_at || new Date().toLocaleString()}`;
    el.reportProviderBadge.textContent = status?.simulate ? 'Simulation' : (status?.model || 'llama3.2:latest');

    // ── Exec Summary ──
    el.acquirerRationale.textContent = data.strategy.acquisition_rationale;

    el.strategicPriorities.innerHTML = '';
    data.strategy.strategic_priorities.forEach(p => addLi(el.strategicPriorities, p));

    fillGapList(el.gapCapability, data.strategy.gaps.capability_gaps);
    fillGapList(el.gapMarket, data.strategy.gaps.market_gaps);
    fillGapList(el.gapTech, data.strategy.gaps.technology_gaps);
    fillGapList(el.gapCustomer, data.strategy.gaps.customer_gaps);
    fillGapList(el.gapGeo, data.strategy.gaps.geographic_gaps);

    el.roadmap.innerHTML = '';
    data.partner.ideal_roadmap_milestones.forEach(m => {
        const sep = m.indexOf(': ');
        const period = sep !== -1 ? m.slice(0, sep) : m;
        const desc = sep !== -1 ? m.slice(sep + 2) : '';
        const item = document.createElement('div');
        item.className = 'roadmap-item';
        item.innerHTML = `<div class="roadmap-dot"></div><div class="roadmap-period">${period}</div>${desc ? `<div class="roadmap-desc">${desc}</div>` : ''}`;
        el.roadmap.appendChild(item);
    });

    // ── Industry ──
    el.industryStructure.textContent = data.industry.structure;
    fillList(el.consolidationTrends, data.industry.consolidation_trends);
    fillList(el.growthSegments, data.industry.attractive_categories);
    fillList(el.emergingTech, data.industry.emerging_technologies);
    fillList(el.disruptionRisks, data.industry.disruption_risks);

    // ── Longlist ──
    el.longlistBody.innerHTML = '';
    data.longlist.forEach(t => {
        const tr = document.createElement('tr');
        if (t.evaluated) tr.className = 'row-hi';

        const riskBadge = t.risk_score !== 'N/A'
            ? `<span class="badge ${riskClass(parseInt(t.risk_score))}">${t.risk_score}/10</span>`
            : '<span class="badge badge-purple">N/A</span>';

        const synBadge = t.synergy_score !== 'N/A'
            ? `<span class="badge ${synergyClass(parseFloat(t.synergy_score))}">${t.synergy_score}/100</span>`
            : '<span class="badge badge-purple">N/A</span>';

        tr.innerHTML = `
            <td><strong>${t.rank}</strong></td>
            <td><strong>${t.company}</strong></td>
            <td>${t.industry}</td>
            <td><span class="badge badge-blue">${t.strategic_fit}/10</span></td>
            <td>${synBadge}</td>
            <td>${riskBadge}</td>
            <td>${t.evaluated
                ? `<button class="btn-sm-outline" onclick="viewTarget('${t.company}')">View Details</button>`
                : '<span style="font-size:11px;color:var(--text-3)">Not shortlisted</span>'
            }</td>`;
        el.longlistBody.appendChild(tr);
    });

    // ── Deep Dive ──
    renderTargetList();
    renderTargetDetail();

    // ── Partner ──
    el.partnerCritique.textContent = data.partner.critique;
    fillList(el.hiddenOpportunities, data.partner.hidden_opportunities);
    fillList(el.hiddenRisks, data.partner.hidden_risks);

    el.partnerQA.innerHTML = '';
    Object.entries(data.partner.final_questions).forEach(([q, a]) => {
        const div = document.createElement('div');
        div.className = 'qa-entry';
        div.innerHTML = `<div class="qa-q">Q: ${q}</div><div class="qa-a">${a}</div>`;
        el.partnerQA.appendChild(div);
    });
}

function renderTargetList() {
    el.targetList.innerHTML = '';
    state.report.top_evaluations.forEach((te, i) => {
        const rec = state.report.partner.recommendations_table.find(r => r.company_name === te.profile.name);
        const tier = rec?.tier?.split(':')[0] || 'Tier 3';
        const card = document.createElement('div');
        card.className = `target-card${i === state.targetIdx ? ' active' : ''}`;
        card.innerHTML = `
            <div class="tc-header">
                <span class="tc-name">${te.profile.name}</span>
                <span class="tc-score">${te.weighted_synergy_score}</span>
            </div>
            <div class="tc-meta">${te.profile.headquarters} · ${tier}</div>`;
        card.onclick = () => {
            state.targetIdx = i;
            renderTargetList();
            renderTargetDetail();
        };
        el.targetList.appendChild(card);
    });
}

function renderTargetDetail() {
    const te = state.report.top_evaluations[state.targetIdx];
    if (!te) return;

    const rec = state.report.partner.recommendations_table.find(r => r.company_name === te.profile.name);
    const tier = rec?.tier || 'Tier 3';
    const tierShort = tier.split(':')[0];

    el.targetDetail.innerHTML = `
        <!-- Header -->
        <div class="pcard">
            <div class="detail-header">
                <div>
                    <div class="detail-company">${te.profile.name}</div>
                    <div class="detail-meta">${te.profile.industry} · ${te.profile.headquarters} · ${te.profile.market_position}</div>
                </div>
                <div class="score-ring">
                    <div class="score-circle">${te.weighted_synergy_score}</div>
                    <div class="score-label">Synergy Rating</div>
                    <div class="score-tier">${tierShort}</div>
                </div>
            </div>
            <div class="meta-grid">
                <div class="meta-item"><div class="meta-label">Revenue (Est.)</div><div class="meta-value">${te.financial.target_financials.revenue}</div></div>
                <div class="meta-item"><div class="meta-label">EBITDA (Est.)</div><div class="meta-value">${te.financial.target_financials.ebitda}</div></div>
                <div class="meta-item"><div class="meta-label">Valuation Range</div><div class="meta-value">${te.financial.target_financials.valuation_estimate}</div></div>
                <div class="meta-item"><div class="meta-label">YoY Growth</div><div class="meta-value">${te.financial.target_financials.growth_profile}</div></div>
            </div>
            <div class="meta-grid" style="grid-template-columns:1fr 1fr">
                <div class="meta-item"><div class="meta-label">Key Products</div><div class="meta-value" style="font-size:12px">${te.profile.key_products.join(', ')}</div></div>
                <div class="meta-item"><div class="meta-label">Core Capabilities</div><div class="meta-value" style="font-size:12px">${te.profile.core_capabilities.join(', ')}</div></div>
            </div>
            ${rec ? `<div class="ib-rec"><strong>IB Recommendation:</strong> ${rec.rationalization}</div>` : ''}
        </div>

        <!-- Synergy Bars -->
        <div class="pcard">
            <h3 class="pcard-title">Synergy Scoring Breakdown</h3>
            <div class="bar-chart">
                ${bar('Strategic Fit (20%)', te.synergies.strategic_fit, 10, 'green')}
                ${bar('Revenue Synergy (15%)', te.synergies.revenue_synergy.score, 10)}
                ${bar('Product Synergy (10%)', te.synergies.product_synergy.score, 10)}
                ${bar('Technology Synergy (10%)', te.technology.technology_synergy_score, 10)}
                ${bar('Customer Synergy (10%)', te.synergies.customer_synergy.score, 10)}
                ${bar('Geographic Synergy (10%)', te.synergies.geographic_synergy.score, 10)}
                ${bar('Financial Feasibility (10%)', te.financial.affordability_score, 10)}
                ${bar('Risk Discount (10% — lower risk = higher score)', 10 - te.risk.risk_score, 10, 'amber')}
                ${bar('Cultural Compatibility (5%)', te.devils_advocate.cultural_compatibility_score, 10)}
            </div>
        </div>

        <!-- Synergy Narrative -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
            <div class="pcard">
                <h3 class="pcard-title">Revenue & Market Opportunities</h3>
                <p class="body-text">${te.synergies.revenue_synergy.explanation}</p>
                <ul class="bullet-list plus-list" style="margin-top:12px">
                    ${te.synergies.revenue_synergy.opportunities.map(o => `<li>${o}</li>`).join('')}
                </ul>
            </div>
            <div class="pcard">
                <h3 class="pcard-title">Product & Platform Synergies</h3>
                <p class="body-text">${te.synergies.product_synergy.explanation}</p>
                <ul class="bullet-list arrow-list" style="margin-top:12px">
                    ${te.synergies.product_synergy.opportunities.map(o => `<li>${o}</li>`).join('')}
                </ul>
            </div>
        </div>

        <!-- Technology -->
        <div class="pcard">
            <h3 class="pcard-title">Technology & Platform Architecture</h3>
            <p class="body-text"><strong>Stack Compatibility:</strong> ${te.technology.tech_stack_analysis}</p>
            <p class="body-text" style="margin-top:10px"><strong>Engineering Talent:</strong> ${te.technology.talent_and_platform_compatibility}</p>
            <ul class="bullet-list check-list" style="margin-top:12px">
                ${te.technology.ip_and_patents.map(ip => `<li>${ip}</li>`).join('')}
            </ul>
        </div>

        <!-- Financials -->
        <div class="pcard">
            <h3 class="pcard-title">Financial Assessment</h3>
            <p class="body-text">${te.financial.financial_feasibility}</p>
            <div class="fin-score-grid">
                ${finScore('Affordability', te.financial.affordability_score)}
                ${finScore('Financial Health', te.financial.financial_health_score)}
                ${finScore('ROI Potential', te.financial.roi_potential_score)}
                ${finScore('Value Creation', te.financial.value_creation_score)}
            </div>
        </div>

        <!-- Risk -->
        <div class="pcard">
            <h3 class="pcard-title">Risk Assessment Matrix</h3>
            <table class="risk-table">
                <thead><tr><th>Dimension</th><th>Severity</th><th>Description</th></tr></thead>
                <tbody>
                    ${riskRow('Strategic Risk', te.risk.strategic_risks)}
                    ${riskRow('Financial Risk', te.risk.financial_risks)}
                    ${riskRow('Operational Risk', te.risk.operational_risks)}
                    ${riskRow('Technology Risk', te.risk.technology_risks)}
                    ${riskRow('Cultural Risk', te.risk.cultural_risks)}
                </tbody>
            </table>
        </div>

        <!-- Devil's Advocate -->
        <div class="da-box">
            <div class="da-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                Agent 8 · Devil's Advocate — Adversarial Thesis Challenge
            </div>
            <div class="da-qa">
                ${daItem('Why should this deal NOT happen?', te.devils_advocate.why_deal_should_not_happen)}
                ${daItem('What assumptions are weakest?', te.devils_advocate.weak_assumptions)}
                ${daItem('What value destruction scenarios exist?', te.devils_advocate.value_destruction_scenarios)}
                ${daItem('What could go wrong post-merger?', te.devils_advocate.post_merger_risks)}
                ${daItem('Why might competitors benefit instead?', te.devils_advocate.competitor_benefits)}
            </div>
            <div class="case-grid">
                <div class="case-box bull">
                    <h5>🟢 Bull Case Scenario</h5>
                    <p>${te.devils_advocate.bull_case}</p>
                </div>
                <div class="case-box bear">
                    <h5>🔴 Bear Case Scenario</h5>
                    <p>${te.devils_advocate.bear_case}</p>
                </div>
            </div>
        </div>
    `;
}

// ── Template Helpers ───────────────────────────────────────
function bar(label, val, max, color = '') {
    const pct = Math.round((Math.max(0, val) / max) * 100);
    return `
    <div class="bar-row">
        <div class="bar-header"><span>${label}</span><span>${val}/${max}</span></div>
        <div class="bar-track"><div class="bar-fill ${color}" style="width:${pct}%"></div></div>
    </div>`;
}

function finScore(name, score) {
    const cls = score >= 8 ? 'badge-green' : score >= 5 ? 'badge-amber' : 'badge-red';
    return `<div class="fin-score-item"><div class="fin-score-name">${name}</div><span class="badge ${cls}">${score}/10</span></div>`;
}

function riskRow(label, dim) {
    const cls = dim.level?.toLowerCase() === 'low' ? 'badge-green' : dim.level?.toLowerCase() === 'high' ? 'badge-red' : 'badge-amber';
    return `<tr><td>${label}</td><td><span class="badge ${cls}">${dim.level}</span></td><td>${dim.description}</td></tr>`;
}

function daItem(q, a) {
    return `<div class="da-qa-item"><div class="da-q">${q}</div><div class="da-a">${a}</div></div>`;
}

function addLi(parent, text) {
    const li = document.createElement('li');
    li.textContent = text;
    parent.appendChild(li);
}

function fillList(parent, arr) {
    parent.innerHTML = '';
    (arr || []).forEach(item => addLi(parent, item));
}

function fillGapList(parent, arr) {
    parent.innerHTML = '';
    (arr || []).forEach(item => addLi(parent, item));
}

function riskClass(score) {
    if (score <= 3) return 'badge-green';
    if (score <= 6) return 'badge-amber';
    return 'badge-red';
}

function synergyClass(score) {
    if (score >= 75) return 'badge-green';
    if (score >= 50) return 'badge-amber';
    return 'badge-red';
}

// ── Global Triggers ────────────────────────────────────────
window.viewTarget = function(companyName) {
    const idx = state.report.top_evaluations.findIndex(te => te.profile.name === companyName);
    if (idx !== -1) {
        state.targetIdx = idx;
        switchTab('deepdive');
        renderTargetList();
        renderTargetDetail();
    }
};

// ── Fetch Helper ───────────────────────────────────────────
async function apiFetch(url, options = {}) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
}
