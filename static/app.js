'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = { taskId: null, pollTimer: null, report: null, mode: 'profile' };

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkOllama();
  loadProjects();
});


// ── Mode toggle ───────────────────────────────────────────────────────────────
function setMode(m) {
  state.mode = m;
  document.getElementById('modeProfile').classList.toggle('active', m === 'profile');
  document.getElementById('modeDiscover').classList.toggle('active', m === 'discover');
  document.getElementById('formProfile').classList.toggle('hidden', m !== 'profile');
  document.getElementById('formDiscover').classList.toggle('hidden', m !== 'discover');
  document.getElementById('flow-profile').classList.toggle('hidden', m !== 'profile');
  document.getElementById('flow-discover').classList.toggle('hidden', m !== 'discover');
}

// ── Ollama health ─────────────────────────────────────────────────────────────
async function checkOllama() {
  const dot  = document.getElementById('ollamaStatus');
  const text = document.getElementById('ollamaStatusText');
  try {
    const r = await fetch('http://localhost:11434/api/tags', { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      dot.innerHTML = '<span class="status-dot dot-ok"></span>';
      text.textContent = 'Ollama connected'; text.style.color = 'var(--green)';
    } else throw new Error();
  } catch {
    dot.innerHTML = '<span class="status-dot dot-error"></span>';
    text.textContent = 'Ollama not reachable — use Simulation Mode'; text.style.color = 'var(--red)';
  }
}

// ── Projects list ─────────────────────────────────────────────────────────────
async function loadProjects() {
  try {
    const projects = await fetch('/api/projects').then(r => r.json());
    const sel = document.getElementById('savedProjects');
    sel.innerHTML = '<option value="">— Select saved report —</option>';
    projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.task_id;
      const date = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';
      const tag  = p.mode === 'discovery' ? '[discover]' : '[profile]';
      const sim  = p.simulate ? ' [sim]' : '';
      opt.textContent = `${p.company || 'Unknown'} ${tag}${sim} · ${date}`;
      sel.appendChild(opt);
    });
  } catch (e) { console.error('loadProjects:', e); }
}

async function loadProject(taskId) {
  if (!taskId) return;
  const status = await fetch(`/api/status/${taskId}`).then(r => r.json());
  if (status.status !== 'completed') { alert(`Status: ${status.status}`); return; }
  const report = await fetch(`/api/report/${taskId}`).then(r => r.json());
  state.report = report; state.taskId = taskId;
  if (status.mode === 'discovery') showDiscovery(report, status);
  else                             showReport(status.company || report.company, status);
}

// ── Submit handlers ───────────────────────────────────────────────────────────
async function handleProfile(e) {
  e.preventDefault();
  const company  = document.getElementById('companyInput').value.trim();
  const model    = document.getElementById('modelInput').value.trim() || 'llama3.2:latest';
  const simulate = document.getElementById('simulateToggle').checked;
  if (!company) return;
  document.getElementById('submitBtn').disabled = true;
  try {
    const d = await fetch('/api/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company, model, simulate }),
    }).then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.detail); }); return r.json(); });
    state.taskId = d.task_id;
    showProgress(company);
    startPoll();
  } catch (err) {
    alert('Failed: ' + err.message);
    document.getElementById('submitBtn').disabled = false;
  }
}

async function handleDiscover(e) {
  e.preventDefault();
  const acquirer = document.getElementById('acquirerInput').value.trim();
  const model    = document.getElementById('discoverModelInput').value.trim() || 'llama3.2:latest';
  const simulate = document.getElementById('discoverSimulate').checked;
  if (!acquirer) return;
  document.getElementById('discoverBtn').disabled = true;
  const payload = {
    acquirer,
    sector:         document.getElementById('thesisSector').value.trim(),
    geography:      document.getElementById('thesisGeo').value.trim(),
    capability_gap: document.getElementById('thesisCap').value.trim(),
    revenue_range:  document.getElementById('thesisRev').value.trim(),
    model, simulate,
  };
  try {
    const d = await fetch('/api/discover', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(r => { if (!r.ok) return r.json().then(e => { throw new Error(e.detail); }); return r.json(); });
    state.taskId = d.task_id;
    showProgress(acquirer + ' · M&A Discovery');
    startPoll();
  } catch (err) {
    alert('Failed: ' + err.message);
    document.getElementById('discoverBtn').disabled = false;
  }
}

// ── Polling ───────────────────────────────────────────────────────────────────
function startPoll() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(poll, 2500);
}

async function poll() {
  if (!state.taskId) return;
  const data = await fetch(`/api/status/${state.taskId}`).then(r => r.json()).catch(() => null);
  if (!data) return;
  updateProgress(data);
  updateFlow(data.current_agent || '', data.progress || 0, data.mode || 'profile');
  if (data.status === 'completed') {
    clearInterval(state.pollTimer);
    const report = await fetch(`/api/report/${state.taskId}`).then(r => r.json());
    state.report = report;
    if (data.mode === 'discovery') showDiscovery(report, data);
    else                           showReport(data.company || report.company, data);
    loadProjects();
    document.getElementById('submitBtn').disabled  = false;
    document.getElementById('discoverBtn').disabled = false;
  } else if (data.status === 'failed') {
    clearInterval(state.pollTimer);
    const logs = data.logs || [];
    alert('Analysis failed:\n' + (logs[logs.length - 1] || 'Unknown error'));
    showEmpty();
    document.getElementById('submitBtn').disabled  = false;
    document.getElementById('discoverBtn').disabled = false;
  }
}

function updateProgress(d) {
  document.getElementById('progressCompany').textContent = d.company || 'Analyzing…';
  document.getElementById('progressAgent').textContent   = d.current_agent || 'Running…';
  const pct = d.progress || 0;
  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressPct').textContent  = pct + '%';
  const logEl = document.getElementById('progressLog');
  logEl.innerHTML = (d.logs || []).map(l => `<div class="log-line">${esc(l)}</div>`).join('');
  logEl.scrollTop = logEl.scrollHeight;
}

function updateFlow(label, progress, mode) {
  const l = label.toLowerCase();
  if (mode === 'discovery') {
    ['fd0','fd1','fd2','fd3','fd4'].forEach(id => {
      const el = document.getElementById(id); if (!el) return;
      el.classList.remove('active','done');
    });
    if (progress >= 100) {
      ['fd0','fd1','fd2','fd3','fd4'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('done'); });
    } else if (l.includes('synergy')) {
      ['fd0','fd1','fd2','fd3'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('done'); });
      document.getElementById('fd4')?.classList.add('active');
    } else if (l.includes('target') || l.includes('profile')) {
      ['fd0','fd1','fd2'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('done'); });
      document.getElementById('fd3')?.classList.add('active');
    } else if (l.includes('discovery') || l.includes('extract')) {
      ['fd0','fd1'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('done'); });
      document.getElementById('fd2')?.classList.add('active');
    } else if (l.includes('acquirer')) {
      document.getElementById('fd0')?.classList.add('done');
      document.getElementById('fd1')?.classList.add('active');
    } else {
      document.getElementById('fd0')?.classList.add('active');
    }
    return;
  }
  // Profile mode
  ['fn0','fn1','fn2','fn3','fn4','fn5','fn6','fn7','fn8','fn9'].forEach(id => {
    const el = document.getElementById(id); if (el) el.classList.remove('active','done');
  });
  if (progress >= 100) {
    ['fn0','fn1','fn2','fn3','fn4','fn5','fn6','fn7','fn8','fn9'].forEach(id => {
      const el = document.getElementById(id); if (el) el.classList.add('done');
    });
  } else if (l.includes('strategic') || l.includes('agent 9')) {
    ['fn0','fn1','fn2','fn3','fn4','fn5','fn6','fn7','fn8'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('done'); });
    document.getElementById('fn9')?.classList.add('active');
  } else if (l.includes('parallel') || ['fn3','fn4','fn5','fn6','fn7','fn8'].some(id => l.includes(id.slice(-1)))) {
    ['fn0','fn1','fn2'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('done'); });
    ['fn3','fn4','fn5','fn6','fn7','fn8'].forEach(id => { const el = document.getElementById(id); if (el) el.classList.add('active'); });
  } else if (l.includes('services') || l.includes('agent 2')) {
    document.getElementById('fn0')?.classList.add('done');
    document.getElementById('fn1')?.classList.add('done');
    document.getElementById('fn2')?.classList.add('active');
  } else if (l.includes('company') || l.includes('agent 1')) {
    document.getElementById('fn0')?.classList.add('done');
    document.getElementById('fn1')?.classList.add('active');
  } else if (l.includes('data') || l.includes('scraping') || l.includes('acquisition')) {
    document.getElementById('fn0')?.classList.add('active');
  }
}

// ── View transitions ──────────────────────────────────────────────────────────
function showEmpty() {
  document.getElementById('emptyState').classList.remove('hidden');
  document.getElementById('progressState').classList.add('hidden');
  document.getElementById('reportState').classList.add('hidden');
  document.getElementById('discoveryState').classList.add('hidden');
}

function showProgress(label) {
  document.getElementById('emptyState').classList.add('hidden');
  document.getElementById('progressState').classList.remove('hidden');
  document.getElementById('reportState').classList.add('hidden');
  document.getElementById('discoveryState').classList.add('hidden');
  document.getElementById('progressCompany').textContent = label;
  document.getElementById('progressAgent').textContent   = 'Initializing…';
  document.getElementById('progressBar').style.width     = '0%';
  document.getElementById('progressPct').textContent     = '0%';
  document.getElementById('progressLog').innerHTML       = '';
}

function renderSourceChips(containerId, report) {
  const el = document.getElementById(containerId);
  if (!el) return;
  // Detect which sources contributed data (from first target or top-level)
  const scraped = report._scraped_meta || {};
  const llmSources = report._llm_sources || [];
  const allSources = [
    { label: 'Website',   active: scraped.website_pages > 0 },
    { label: 'Wikipedia', active: scraped.wiki_ok },
    { label: 'DDG',       active: scraped.search_count > 0 },
    { label: 'yFinance',  active: scraped.fin_ok },
    { label: 'OpenAI',    active: llmSources.includes('OpenAI gpt-4o-mini') || llmSources.includes('OpenAI') },
    { label: 'Gemini',    active: llmSources.includes('Gemini gemini-1.5-flash') || llmSources.includes('Gemini') },
  ];
  el.innerHTML = allSources.map(s =>
    `<span class="source-chip ${s.active ? 'active' : ''}">${esc(s.label)}</span>`
  ).join('');
}

function showReport(company, meta) {
  document.getElementById('emptyState').classList.add('hidden');
  document.getElementById('progressState').classList.add('hidden');
  document.getElementById('reportState').classList.remove('hidden');
  document.getElementById('discoveryState').classList.add('hidden');
  document.getElementById('reportCompanyName').textContent = company;
  const sim = meta.simulate ? ' · Simulation' : ' · Grounded';
  document.getElementById('reportMeta').textContent = `Accenture V&A Intelligence${sim} · ${meta.model || ''}`;
  renderSourceChips('reportSources', state.report || {});
  renderProfile(state.report);
  // Reset to first tab
  document.querySelectorAll('#reportState .rtab').forEach((b,i) => b.classList.toggle('active', i === 0));
  document.querySelectorAll('#reportState .rtab-panel').forEach((p,i) => {
    p.classList.toggle('hidden', i !== 0);
    p.classList.toggle('active', i === 0);
  });
}

function showDiscovery(report, meta) {
  document.getElementById('emptyState').classList.add('hidden');
  document.getElementById('progressState').classList.add('hidden');
  document.getElementById('reportState').classList.add('hidden');
  document.getElementById('discoveryState').classList.remove('hidden');
  document.getElementById('discAcquirerName').textContent = (report.acquirer || '') + ' — M&A Target Discovery';
  const sim = meta.simulate ? ' · Simulation' : ' · Grounded';
  const t   = report.thesis || {};
  const thesis = [t.sector, t.geography, t.capability_gap].filter(Boolean).join(' · ');
  document.getElementById('discMeta').textContent = `${thesis}${sim}`;
  renderSourceChips('discSources', report);
  renderDiscovery(report);
}

function switchTab(tabId, btn) {
  const container = btn ? btn.closest('.report-state') : document.getElementById('reportState');
  container.querySelectorAll('.rtab').forEach(b => b.classList.remove('active'));
  container.querySelectorAll('.rtab-panel').forEach(p => { p.classList.add('hidden'); p.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  const panel = document.getElementById(`tab-${tabId}`);
  if (panel) { panel.classList.remove('hidden'); panel.classList.add('active'); }
}

function newAnalysis() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.taskId = null; state.report = null;
  showEmpty();
  document.getElementById('analyzeForm').reset();
  document.getElementById('discoverForm').reset();
  document.getElementById('modelInput').value = 'llama3.2:latest';
  document.getElementById('discoverModelInput').value = 'llama3.2:latest';
  document.getElementById('submitBtn').disabled  = false;
  document.getElementById('discoverBtn').disabled = false;
}

function exportReport() {
  if (!state.report) return;
  const name = (state.report.company || state.report.acquirer || 'report').replace(/\s+/g, '_');
  const blob = new Blob([JSON.stringify(state.report, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `va_intelligence_${name}.json`;
  a.click();
}

// ═══════════════════════════════════════════════════════════════════════════════
// PROFILE RENDERERS
// ═══════════════════════════════════════════════════════════════════════════════
function renderProfile(r) {
  if (!r) return;
  renderS1(r.overview || {});
  renderS2(r.overview || {});
  renderS3(r.services || {});
  renderS4(r.locations || {});
  renderS5(r.clients || {});
  renderS6(r.financials || {});
  renderS7(r.leadership || {});
  renderS8S9(r.glassdoor_news || {});
  renderS10(r.workforce || {});
  renderS11(r.strategic || {});
}

function renderS1(ov) {
  document.getElementById('s1-overview').textContent = ov.business_overview || 'Not found in allowed sources.';
}

function renderS2(ov) {
  const grid = document.getElementById('s2-grid');
  const fields = [
    ['Legal / Trade Name', ov.legal_name],
    ['Company Type',       ov.company_type],
    ['Year Founded',       ov.year_founded],
    ['Headquarters',       ov.hq],
    ['Global Offices',     ov.global_offices],
    ['Employees',          ov.employee_count],
    ['Sector / Industry',  ov.sector_industry],
    ['Business Model',     ov.business_model],
    ['Website',            ov.website_url ? `<a href="${esc(ov.website_url)}" target="_blank" rel="noopener">${esc(ov.website_url)}</a>` : null],
    ['LinkedIn',           ov.linkedin_url ? `<a href="${esc(ov.linkedin_url)}" target="_blank" rel="noopener">View Profile</a>` : null],
  ];
  if ((ov.certifications_awards || []).length) {
    fields.push(['Certifications & Awards', ov.certifications_awards.join(', ')]);
  }
  grid.innerHTML = fields.map(([k, v]) => {
    const isLink = typeof v === 'string' && v.startsWith('<a');
    const display = v ? (isLink ? v : esc(String(v))) : 'Not found in allowed sources';
    return `<div class="kv-item"><div class="kv-key">${esc(k)}</div><div class="kv-val">${display}</div></div>`;
  }).join('');
}

function renderS3(sv) {
  const list = document.getElementById('s3-services');
  const items = sv.services_solutions_products || [];
  list.innerHTML = items.length
    ? items.map(s => `<div class="service-item"><div class="service-name">${esc(s.name||'')}</div><div class="service-desc">${esc(s.description||'')}</div></div>`).join('')
    : '<p class="section-prose">Not found in allowed sources.</p>';
}

function renderS4(loc) {
  const el = document.getElementById('s4-locations');
  const regions = [
    { label: 'AMER', items: loc.amer_offices || [] },
    { label: 'EMEA', items: loc.emea_offices || [] },
    { label: 'APAC', items: loc.apac_offices || [] },
    { label: 'Delivery Centers', items: loc.delivery_centers || [] },
  ];
  const hq = loc.headquarters ? `<div class="kv-item" style="margin-bottom:10px"><div class="kv-key">Headquarters</div><div class="kv-val">${esc(loc.headquarters)}</div></div>` : '';
  const parent = loc.parent_company ? `<div class="kv-item" style="margin-top:10px"><div class="kv-key">Parent Company</div><div class="kv-val">${esc(loc.parent_company)}</div></div>` : '';
  const grid = regions.filter(r => r.items.length).map(r =>
    `<div class="region-block"><div class="region-label">${esc(r.label)}</div><ul class="region-list">${r.items.map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>`
  ).join('');
  el.innerHTML = hq + `<div class="region-grid">${grid}</div>` + parent;
}

function renderS5(cli) {
  const el = document.getElementById('s5-clients');
  const clients = cli.named_clients || [];
  const segs    = cli.client_segments || [];
  const cases   = cli.anonymous_case_studies || '';
  const clientHtml = clients.length
    ? `<div class="subsection-title">Named Clients</div><div class="client-tags">${clients.map(c => `<span class="client-tag">${esc(c)}</span>`).join('')}</div>`
    : '<p class="section-prose" style="margin-bottom:10px">Client names not disclosed on Official Website.</p>';
  const segHtml = segs.length
    ? `<div class="subsection-title">Market Segments</div><div class="segment-tags">${segs.map(s => `<span class="segment-tag">${esc(s)}</span>`).join('')}</div>`
    : '';
  const caseHtml = cases
    ? `<div class="kv-item" style="margin-top:10px"><div class="kv-key">Anonymous Case Studies</div><div class="kv-val">${esc(cases)}</div></div>`
    : '';
  el.innerHTML = clientHtml + segHtml + caseHtml;
}

function renderS6(fin) {
  const el = document.getElementById('s6-financials');
  const summary = `<div class="fin-summary">
    <div class="fin-card"><div class="fin-card-label">Revenue</div><div class="fin-card-val">${esc(fin.revenue||'N/A')}</div></div>
    <div class="fin-card"><div class="fin-card-label">Revenue / Employee</div><div class="fin-card-val">${esc(fin.revenue_per_employee||'N/A')}</div></div>
    <div class="fin-card"><div class="fin-card-label">Source</div><div class="fin-card-val" style="font-size:11px">${esc(fin.revenue_source||'N/A')}</div></div>
  </div>`;
  const rounds = fin.funding_rounds || [];
  const roundsHtml = rounds.length
    ? `<div class="subsection-title">Funding Rounds</div><div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Round</th><th>Amount</th><th>Lead Investors</th></tr></thead><tbody>${rounds.map(r => `<tr><td>${esc(r.date||'')}</td><td>${esc(r.round_type||'')}</td><td>${esc(r.amount||'')}</td><td>${esc(r.lead_investors||'')}</td></tr>`).join('')}</tbody></table></div>`
    : '<div class="subsection-title">Funding Rounds</div><p class="section-prose">No funding rounds in allowed sources.</p>';
  const acqs = fin.acquisitions || [];
  const acqHtml = acqs.length
    ? `<div class="subsection-title">Acquisitions (last 10 years)</div><div class="table-wrap"><table class="data-table"><thead><tr><th>Company</th><th>Descriptor</th><th>Year</th><th>Value</th><th>Headcount</th><th>Rationale</th></tr></thead><tbody>${acqs.map(a => `<tr><td>${esc(a.company_name||'')}</td><td>${esc(a.descriptor||'')}</td><td>${esc(a.year||'')}</td><td>${esc(a.deal_value||'')}</td><td>${esc(a.headcount_added||'')}</td><td>${esc(a.strategic_rationale||'')}</td></tr>`).join('')}</tbody></table></div>`
    : '<div class="subsection-title">Acquisitions</div><p class="section-prose">No acquisitions found in allowed sources in the past 10 years.</p>';
  const partners = fin.key_partnerships || [];
  const partnerHtml = partners.length
    ? `<div class="subsection-title">Key Partnerships</div><div class="partner-chips">${partners.map(p => `<span class="partner-chip">${esc(p)}</span>`).join('')}</div>`
    : '';
  el.innerHTML = summary + roundsHtml + acqHtml + partnerHtml;
}

function renderS7(lead) {
  const el = document.getElementById('s7-leadership');
  const leaders = lead.leaders || [];
  el.innerHTML = leaders.length
    ? `<div class="leaders-grid">${leaders.map(l => `<div class="leader-card"><div class="leader-name">${esc(l.full_name||'')}</div><div class="leader-title">${esc(l.title||'')}</div><div class="leader-prev">${esc(l.previous_role||'')}</div>${l.accenture_alumni ? '<span class="alumni-badge">Accenture Alumni</span>' : ''}</div>`).join('')}</div>`
    : '<p class="section-prose">Not found in allowed sources.</p>';
}

function renderS8S9(gn) {
  const s8 = document.getElementById('s8-glassdoor');
  const s9 = document.getElementById('s9-news');
  const rating  = gn.glassdoor_rating       || 'Not visible on Glassdoor profile';
  const reviews = gn.glassdoor_total_reviews || '';
  const isNum   = !isNaN(parseFloat(rating));
  s8.innerHTML = `<div class="glassdoor-box">${isNum
    ? `<div class="gd-rating-num">${esc(rating)}</div><div><div class="gd-label">Overall Rating</div><div class="gd-reviews">${esc(reviews)} reviews</div></div>`
    : `<div class="gd-label">${esc(rating)}</div>`}</div>`;
  const news = gn.recent_news || [];
  s9.innerHTML = news.length
    ? `<div class="news-list">${news.map(n => `<div class="news-item"><div class="news-date">${esc(n.month_year||'')}</div><div class="news-text">${esc(n.description||'')}</div></div>`).join('')}</div>`
    : '<p class="section-prose">Not found in allowed sources.</p>';
}

function renderS10(wf) {
  const el = document.getElementById('s10-workforce');
  const fns    = wf.functions  || [];
  const locs   = wf.locations  || [];
  const skills = wf.top_skills || [];
  const open   = wf.open_positions || 'Not found in allowed sources';
  const mkBars = (items, kName, pName) => items.map(item => {
    const pct = parseFloat(String(item[pName]||'0').replace('%','')) || 0;
    return `<div class="wf-bar-row"><div class="wf-bar-label" title="${esc(item[kName]||'')}">${esc(item[kName]||'')}</div><div class="wf-bar-track"><div class="wf-bar-fill" style="width:${Math.min(pct,100)}%"></div></div><div class="wf-bar-pct">${esc(item[pName]||'')}</div></div>`;
  }).join('');
  el.innerHTML = `<div class="workforce-grid"><div class="wf-block"><div class="wf-title">Functions</div>${mkBars(fns,'function_name','percentage')}</div><div class="wf-block"><div class="wf-title">Locations</div>${mkBars(locs,'location','percentage')}</div></div><div class="subsection-title">Top Skills</div><div class="skills-wrap">${skills.map(s => `<span class="skill-tag">${esc(s)}</span>`).join('')}</div><div class="kv-item" style="margin-top:12px"><div class="kv-key">Open Positions</div><div class="kv-val">${esc(String(open))}</div></div>`;
}

function renderS11(st) {
  const el = document.getElementById('s11-strategic');
  const strengths = st.strategic_strengths || [];
  const risks     = st.key_risks           || [];
  el.innerHTML = `
    <div class="strategic-grid">
      <div class="strategic-col"><div class="strategic-col-title">Strategic Strengths</div>${strengths.map(s => `<div class="strategic-item strength">${esc(s)}</div>`).join('')}</div>
      <div class="strategic-col"><div class="strategic-col-title">Key Risks</div>${risks.map(r => `<div class="strategic-item risk">${esc(r)}</div>`).join('')}</div>
    </div>
    <div class="prose-block"><div class="prose-block-title">Strategic Fit for Accenture</div><p>${esc(st.strategic_fit_for_accenture||'Not found in allowed sources.')}</p></div>
    <div class="prose-block"><div class="prose-block-title">M&amp;A Suitability</div><p>${esc(st.ma_suitability||'Not found in allowed sources.')}</p></div>`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DISCOVERY RENDERERS
// ═══════════════════════════════════════════════════════════════════════════════
function renderDiscovery(report) {
  const targets = report.targets || [];
  const tabBar  = document.getElementById('targetTabBar');
  const panels  = document.getElementById('targetPanels');

  if (!targets.length) {
    panels.innerHTML = '<div class="target-panel active"><p class="section-prose">No targets were discovered. Try broader thesis criteria.</p></div>';
    tabBar.innerHTML = '';
    return;
  }

  tabBar.innerHTML = targets.map((t, i) =>
    `<button class="rtab ${i===0?'active':''}" onclick="switchDiscoveryTarget(${i}, this)">${esc(t.company||`Target ${i+1}`)}</button>`
  ).join('');

  panels.innerHTML = targets.map((t, i) => renderTargetPanel(t, i, targets.length)).join('');
}

function switchDiscoveryTarget(idx, btn) {
  document.querySelectorAll('#targetTabBar .rtab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.target-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`target-panel-${idx}`)?.classList.add('active');
}

function renderTargetPanel(t, idx, total) {
  const syn  = t.synergy || {};
  const maxH = Math.max(...(Array.from({length: total}, (_, i) => 0))); // placeholder for bar scaling
  const synLow  = typeof syn.total_low_usd_m  === 'number' ? `$${syn.total_low_usd_m.toFixed(0)}M`  : 'N/A';
  const synHigh = typeof syn.total_high_usd_m === 'number' ? `$${syn.total_high_usd_m.toFixed(0)}M` : 'N/A';

  const synTable = (syn.synergy_items || []).map(item => {
    const conf = (item.confidence_level||'').toLowerCase();
    const confClass = conf === 'high' ? 'confidence-high' : conf === 'medium' ? 'confidence-medium' : 'confidence-low';
    const lo = typeof item.estimated_value_low_usd_m  === 'number' ? `$${item.estimated_value_low_usd_m.toFixed(0)}M`  : '–';
    const hi = typeof item.estimated_value_high_usd_m === 'number' ? `$${item.estimated_value_high_usd_m.toFixed(0)}M` : '–';
    return `<tr>
      <td>${esc(item.synergy_type||'')}</td>
      <td>${esc(item.basis||'')}</td>
      <td>${esc(lo)} – ${esc(hi)}</td>
      <td class="${confClass}">${esc(item.confidence_level||'')}</td>
      <td>Year ${esc(String(item.year_realizable||''))}</td>
    </tr>`;
  }).join('');

  const capFills = (syn.capability_gaps_filled||[]).map(c => `<span class="segment-tag">${esc(c)}</span>`).join('');
  const geoOverlap = (syn.geography_overlap||[]).map(g => `<span class="client-tag">${esc(g)}</span>`).join('');
  const clientOverlap = (syn.client_overlap||[]).map(c => `<span class="client-tag">${esc(c)}</span>`).join('');
  const assumptions = (syn.key_assumptions||[]).map((a,i) => `<div class="news-item" style="margin-bottom:4px"><div class="news-date">Assumption ${i+1}</div><div class="news-text">${esc(a)}</div></div>`).join('');

  // Sub-tabs for profile + synergy
  const panelId = `target-panel-${idx}`;
  const subId   = `sub-${idx}`;

  return `<div class="target-panel ${idx===0?'active':''}" id="${panelId}">

    <!-- Rank card -->
    <div class="target-rank">
      <div class="target-rank-num">#${idx+1}</div>
      <div>
        <div class="target-rank-name">${esc(t.company||'')}</div>
        <div class="target-rank-meta">${[
          (t.overview||{}).sector_industry,
          (t.overview||{}).hq,
          (t.overview||{}).employee_count,
        ].filter(v => v && v !== 'Not found in allowed sources').map(esc).join(' · ')}</div>
        <div class="target-synergy-bar">
          <div class="target-syn-label">Synergy potential</div>
          <div class="target-syn-track"><div class="target-syn-fill" style="width:75%"></div></div>
          <div class="target-syn-val">${synLow} – ${synHigh}</div>
        </div>
        <div style="margin-top:6px;font-size:12px;color:var(--text-2)">${esc(syn.headline_rationale||t.search_rationale||'')}</div>
      </div>
    </div>

    <!-- Sub-tabs -->
    <div class="sub-tab-bar">
      <button class="sub-tab active" onclick="switchSubTab('${subId}','synergy',this)">Synergy Model</button>
      <button class="sub-tab" onclick="switchSubTab('${subId}','profile',this)">Intelligence Profile</button>
    </div>

    <!-- Synergy sub-panel -->
    <div class="sub-panel active" id="${subId}-synergy">

      <div class="synergy-summary">
        <div class="syn-card"><div class="syn-card-label">Synergy Range</div><div class="syn-card-val">${esc(synLow)} – ${esc(synHigh)}</div></div>
        <div class="syn-card"><div class="syn-card-label">Deal Structure</div><div class="syn-card-val" style="font-size:12px">${esc(syn.deal_structure||'N/A')}</div></div>
        <div class="syn-card"><div class="syn-card-label">EV / Revenue</div><div class="syn-card-val" style="font-size:12px">${esc(syn.suggested_ev_revenue_multiple||'N/A')}</div></div>
      </div>

      ${synTable ? `<div class="section-block" style="padding:14px">
        <div class="section-title" style="font-size:14px;margin-bottom:10px">Quantified Synergy Items</div>
        <div class="table-wrap"><table class="data-table">
          <thead><tr><th>Type</th><th>Basis</th><th>Est. Value</th><th>Confidence</th><th>Timeline</th></tr></thead>
          <tbody>${synTable}</tbody>
        </table></div>
      </div>` : ''}

      <div class="twin-row">
        ${capFills ? `<div class="section-block flex-1"><div class="section-tag">Capability Gaps Filled</div><div class="segment-tags" style="margin-top:8px">${capFills}</div></div>` : ''}
        ${geoOverlap || clientOverlap ? `<div class="section-block flex-1">
          ${geoOverlap ? `<div class="section-tag">Geography Overlap</div><div class="client-tags" style="margin:6px 0">${geoOverlap}</div>` : ''}
          ${clientOverlap ? `<div class="section-tag">Client Overlap</div><div class="client-tags" style="margin-top:6px">${clientOverlap}</div>` : ''}
        </div>` : ''}
      </div>

      ${assumptions ? `<div class="section-block"><div class="section-title" style="font-size:13px;margin-bottom:8px">Key Assumptions</div>${assumptions}</div>` : ''}

      <div class="section-block">
        <div class="kv-grid">
          <div class="kv-item"><div class="kv-key">Integration Complexity</div><div class="kv-val">${esc(syn.integration_complexity||'N/A')}</div></div>
          <div class="kv-item"><div class="kv-key">EV / Revenue Multiple</div><div class="kv-val">${esc(syn.suggested_ev_revenue_multiple||'N/A')}</div></div>
          <div class="kv-item"><div class="kv-key">Deal Structure</div><div class="kv-val">${esc(syn.deal_structure||'N/A')}</div></div>
        </div>
      </div>
    </div>

    <!-- Profile sub-panel (re-uses profile renderers) -->
    <div class="sub-panel" id="${subId}-profile">
      <div class="section-block"><div class="section-tag">§1</div><div class="section-title">Business Overview</div><p class="section-prose">${esc((t.overview||{}).business_overview||'Not found in allowed sources.')}</p></div>
      <div class="section-block"><div class="section-tag">§2</div><div class="section-title">Company Overview</div><div class="kv-grid">${renderKvGrid(t.overview||{})}</div></div>
      <div class="section-block"><div class="section-tag">§3</div><div class="section-title">Services &amp; Products</div><div class="services-list">${renderServicesList(t.services||{})}</div></div>
      <div class="section-block"><div class="section-tag">§5</div><div class="section-title">Clients &amp; Segments</div>${renderClientsInline(t.clients||{})}</div>
      <div class="section-block"><div class="section-tag">§6</div><div class="section-title">Financials Summary</div>${renderFinSummary(t.financials||{})}</div>
      <div class="section-block"><div class="section-tag">§11</div><div class="section-title">Strategic Intelligence</div>${renderStrategicInline(t.strategic||{})}</div>
    </div>

  </div>`;
}

function switchSubTab(subId, panel, btn) {
  const container = btn.closest('.target-panel');
  container.querySelectorAll('.sub-tab').forEach(b => b.classList.remove('active'));
  container.querySelectorAll('.sub-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`${subId}-${panel}`)?.classList.add('active');
}

// ── Inline renderers for discovery target profile sub-panel ──────────────────
function renderKvGrid(ov) {
  return [
    ['Legal Name', ov.legal_name], ['Type', ov.company_type], ['Founded', ov.year_founded],
    ['HQ', ov.hq], ['Employees', ov.employee_count], ['Sector', ov.sector_industry],
    ['Business Model', ov.business_model],
  ].map(([k,v]) => `<div class="kv-item"><div class="kv-key">${esc(k)}</div><div class="kv-val">${esc(v||'Not found in allowed sources')}</div></div>`).join('');
}

function renderServicesList(sv) {
  const items = sv.services_solutions_products || [];
  return items.length
    ? items.map(s => `<div class="service-item"><div class="service-name">${esc(s.name||'')}</div><div class="service-desc">${esc(s.description||'')}</div></div>`).join('')
    : '<p class="section-prose">Not found in allowed sources.</p>';
}

function renderClientsInline(cli) {
  const clients = cli.named_clients || [];
  const segs    = cli.client_segments || [];
  return (clients.length ? `<div class="client-tags">${clients.map(c => `<span class="client-tag">${esc(c)}</span>`).join('')}</div>` : '<p class="section-prose">No named clients.</p>') +
    (segs.length ? `<div class="segment-tags" style="margin-top:8px">${segs.map(s => `<span class="segment-tag">${esc(s)}</span>`).join('')}</div>` : '');
}

function renderFinSummary(fin) {
  const partners = (fin.key_partnerships||[]);
  return `<div class="fin-summary">
    <div class="fin-card"><div class="fin-card-label">Revenue</div><div class="fin-card-val">${esc(fin.revenue||'N/A')}</div></div>
    <div class="fin-card"><div class="fin-card-label">Rev / Employee</div><div class="fin-card-val">${esc(fin.revenue_per_employee||'N/A')}</div></div>
    <div class="fin-card"><div class="fin-card-label">Source</div><div class="fin-card-val" style="font-size:11px">${esc(fin.revenue_source||'N/A')}</div></div>
  </div>
  ${partners.length ? `<div class="subsection-title">Key Partnerships</div><div class="partner-chips">${partners.map(p=>`<span class="partner-chip">${esc(p)}</span>`).join('')}</div>` : ''}`;
}

function renderStrategicInline(st) {
  const s = st.strategic_strengths || [];
  const r = st.key_risks || [];
  return `<div class="strategic-grid">
    <div class="strategic-col"><div class="strategic-col-title">Strengths</div>${s.map(x=>`<div class="strategic-item strength">${esc(x)}</div>`).join('')}</div>
    <div class="strategic-col"><div class="strategic-col-title">Risks</div>${r.map(x=>`<div class="strategic-item risk">${esc(x)}</div>`).join('')}</div>
  </div>
  <div class="prose-block" style="margin-top:10px"><div class="prose-block-title">M&amp;A Suitability</div><p>${esc(st.ma_suitability||'Not found in allowed sources.')}</p></div>`;
}

// ── Helper ─────────────────────────────────────────────────────────────────────
function esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
