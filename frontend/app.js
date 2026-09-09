// Fact Knowledge Layer Frontend Application Logic

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initUploadControls();
    loadDashboardData();

    document.getElementById('btn-reseed').addEventListener('click', handleReseed);
    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('fact-search').addEventListener('input', filterFacts);
    document.getElementById('doc-filter').addEventListener('change', filterFacts);
});

let allFacts = [];
let allDocuments = [];

// Navigation handling
function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            navButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(t => t.classList.remove('active'));

            btn.classList.add('active');
            const targetTab = btn.getAttribute('data-tab');
            document.getElementById(targetTab).classList.add('active');

            // Update title
            const tabTitles = {
                'cases-tab': 'The 4 Required Cases Spotlight',
                'facts-tab': 'Fact Knowledge Matrix',
                'relationships-tab': 'Cross-Document Relationships',
                'upload-tab': 'Upload PDF & Process Knowledge'
            };
            document.getElementById('page-title').textContent = tabTitles[targetTab] || 'Fact Knowledge Layer';
        });
    });
}

// Initial Data Load
async function loadDashboardData() {
    await Promise.allSettled([
        fetchCases(),
        fetchFacts(),
        fetchRelationships(),
        fetchDocuments(),
        fetchStats()
    ]);
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const data = await res.json();
        if (data.documents_count !== undefined) {
            document.getElementById('stat-docs').textContent = data.documents_count;
        }
        if (data.facts_count !== undefined) {
            document.getElementById('stat-facts').textContent = data.facts_count;
        }
        if (data.relationships_count !== undefined) {
            document.getElementById('stat-rels').textContent = data.relationships_count;
        }
    } catch (err) {
        console.warn('Stats fetch notice:', err);
    }
}

async function fetchCases() {
    try {
        const res = await fetch('/api/cases');
        if (!res.ok) return;
        const data = await res.json();
        renderCases(data.cases || []);
    } catch (err) {
        console.error('Error fetching cases:', err);
    }
}


function renderCases(cases) {
    const container = document.getElementById('cases-container');
    container.innerHTML = '';

    const badgeMap = {
        'corroborated': 'badge-corroborated',
        'contradiction': 'badge-contradiction',
        'reconciled_by_context': 'badge-reconciled',
        'extraction_failure': 'badge-failure'
    };

    const labelMap = {
        'corroborated': 'Corroborated',
        'contradiction': 'Genuine Contradiction',
        'reconciled_by_context': 'Reconciled by Context',
        'extraction_failure': 'Extraction Failure & Handling'
    };

    cases.forEach(c => {
        const badgeClass = badgeMap[c.relationship_type] || 'badge-corroborated';
        const badgeLabel = labelMap[c.relationship_type] || c.relationship_type;

        const card = document.createElement('div');
        card.className = 'case-card';
        card.innerHTML = `
            <div class="case-header">
                <span class="case-badge ${badgeClass}">${badgeLabel}</span>
                <span style="font-size:11px; color:var(--text-dim);">Case #${c.case_number}</span>
            </div>
            <div>
                <h4 class="case-title">${c.title}</h4>
                <p class="case-desc">${c.description}</p>
            </div>
            <div class="evidence-comparison">
                <div class="evidence-box">
                    <h5><i class="fa-solid fa-file-pdf"></i> ${c.doc_a_name} (Pg ${c.fact_a_page})</h5>
                    <div class="evidence-quote">"${c.fact_a_quote}"</div>
                </div>
                <div class="evidence-box">
                    <h5><i class="fa-solid fa-file-pdf"></i> ${c.doc_b_name} (Pg ${c.fact_b_page})</h5>
                    <div class="evidence-quote">"${c.fact_b_quote}"</div>
                </div>
            </div>
            <div class="reasoning-box">
                <h5><i class="fa-solid fa-brain text-cyan"></i> AI Grounded Reasoning</h5>
                <p class="reasoning-text">${c.reasoning}</p>
                <div style="margin-top:6px; font-size:11px; color:var(--accent-gold); font-weight:600;">
                    <i class="fa-solid fa-lightbulb"></i> Key Insight: ${c.key_insight}
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

async function fetchDocuments() {
    try {
        const res = await fetch('/api/documents');
        const data = await res.json();
        allDocuments = data.documents || [];
        document.getElementById('stat-docs').textContent = allDocuments.length;

        const filterSelect = document.getElementById('doc-filter');
        filterSelect.innerHTML = '<option value="">All Documents</option>';
        allDocuments.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.id;
            opt.textContent = d.filename;
            filterSelect.appendChild(opt);
        });
    } catch (err) {
        console.error('Error fetching documents:', err);
    }
}

async function fetchFacts() {
    try {
        const res = await fetch('/api/facts');
        const data = await res.json();
        allFacts = data.facts || [];
        document.getElementById('stat-facts').textContent = allFacts.length;
        renderFacts(allFacts);
    } catch (err) {
        console.error('Error fetching facts:', err);
    }
}

function renderFacts(facts) {
    const tbody = document.getElementById('facts-tbody');
    tbody.innerHTML = '';

    if (facts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-muted);">No facts match the filter criteria.</td></tr>`;
        return;
    }

    facts.forEach(f => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${f.subject}</strong></td>
            <td><span style="font-weight:700; color:var(--accent-cyan);">${f.value}</span></td>
            <td>${f.temporal_context || 'N/A'}</td>
            <td>${f.scope_context || 'N/A'}</td>
            <td style="font-size:12px; color:var(--text-muted);">${f.doc_filename}</td>
            <td><span class="case-badge badge-reconciled">Page ${f.page_number}</span></td>
            <td>
                <button class="btn-icon" onclick='openEvidenceModal(${JSON.stringify(f).replace(/'/g, "&apos;")})'>
                    <i class="fa-solid fa-quote-right"></i> Evidence
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterFacts() {
    const query = document.getElementById('fact-search').value.toLowerCase();
    const docId = document.getElementById('doc-filter').value;

    const filtered = allFacts.filter(f => {
        const matchesQuery = !query || 
            f.subject.toLowerCase().includes(query) || 
            f.value.toLowerCase().includes(query) || 
            f.exact_quote.toLowerCase().includes(query);

        const matchesDoc = !docId || f.doc_id == docId;

        return matchesQuery && matchesDoc;
    });

    renderFacts(filtered);
}

async function fetchRelationships() {
    try {
        const res = await fetch('/api/relationships');
        const data = await res.json();
        const rels = data.relationships || [];
        document.getElementById('stat-rels').textContent = rels.length;
        renderRelationships(rels);
    } catch (err) {
        console.error('Error fetching relationships:', err);
    }
}

function renderRelationships(rels) {
    const container = document.getElementById('relationships-container');
    container.innerHTML = '';

    const badgeMap = {
        'corroborated': 'badge-corroborated',
        'contradiction': 'badge-contradiction',
        'reconciled_by_context': 'badge-reconciled',
        'extraction_failure': 'badge-failure'
    };

    rels.forEach(r => {
        const badgeClass = badgeMap[r.relationship_type] || 'badge-corroborated';
        const card = document.createElement('div');
        card.className = 'glass-card';
        card.style.padding = '20px';
        card.style.marginBottom = '16px';
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <span class="case-badge ${badgeClass}">${r.relationship_type.replace(/_/g, ' ')}</span>
                <span style="font-size:12px; color:var(--text-dim);"><i class="fa-solid fa-shield-halved"></i> Confidence: ${(r.confidence * 100).toFixed(0)}%</span>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:12px;">
                <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px;">
                    <div style="font-size:11px; color:var(--accent-cyan); font-weight:700;">DOCUMENT A: ${r.doc_a_name}</div>
                    <div style="font-size:13px; font-weight:600; margin-top:4px;">${r.fact_a_summary}</div>
                </div>
                <div style="background:rgba(0,0,0,0.2); padding:10px; border-radius:6px;">
                    <div style="font-size:11px; color:var(--accent-cyan); font-weight:700;">DOCUMENT B: ${r.doc_b_name}</div>
                    <div style="font-size:13px; font-weight:600; margin-top:4px;">${r.fact_b_summary}</div>
                </div>
            </div>
            <div class="reasoning-box">
                <div style="font-size:12px; font-weight:700; color:#fff; margin-bottom:4px;"><i class="fa-solid fa-diagram-project text-cyan"></i> Relationship Reasoning</div>
                <div style="font-size:12px; color:var(--text-muted);">${r.reasoning}</div>
                ${r.context_explanation ? `<div style="font-size:11px; color:var(--accent-cyan); margin-top:4px;"><strong>Context:</strong> ${r.context_explanation}</div>` : ''}
            </div>
        `;
        container.appendChild(card);
    });
}

// Modal Handling
window.openEvidenceModal = function(fact) {
    const body = document.getElementById('modal-evidence-body');
    body.innerHTML = `
        <div style="margin-bottom:16px;">
            <h4 style="font-size:16px; color:var(--accent-cyan); font-weight:700;">${fact.subject}</h4>
            <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Document: ${fact.doc_filename} | Page Number: ${fact.page_number}</div>
        </div>
        <div style="background:rgba(0,0,0,0.3); border-left:3px solid var(--accent-cyan); padding:14px; border-radius:4px; margin-bottom:16px;">
            <div style="font-size:11px; color:var(--text-dim); text-transform:uppercase; margin-bottom:4px;">Verbatim Source Quote:</div>
            <div style="font-size:14px; font-style:italic; line-height:1.5; color:#fff;">"${fact.exact_quote}"</div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; font-size:12px;">
            <div><strong>Reported Value:</strong> <span style="color:var(--accent-gold); font-weight:700;">${fact.value}</span></div>
            <div><strong>Temporal Context:</strong> ${fact.temporal_context || 'N/A'}</div>
            <div><strong>Scope Context:</strong> ${fact.scope_context || 'N/A'}</div>
            <div><strong>Confidence Score:</strong> ${(fact.confidence * 100).toFixed(0)}%</div>
        </div>
    `;
    document.getElementById('evidence-modal').classList.remove('hidden');
};

function closeModal() {
    document.getElementById('evidence-modal').classList.add('hidden');
}

// Upload Handling
function initUploadControls() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('pdf-file-input');
    const submitBtn = document.getElementById('btn-submit-upload');
    const fileInfo = document.getElementById('selected-file-info');

    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            fileInfo.textContent = `Selected: ${file.name} (${(file.size / (1024*1024)).toFixed(2)} MB)`;
            submitBtn.disabled = false;
        }
    });

    document.getElementById('upload-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        if (fileInput.files.length === 0) return;

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);

        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing & Extracting...`;

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            submitBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Extract Facts & Reconcile`;
            submitBtn.disabled = false;

            if (res.ok) {
                renderUploadResults(data);
                loadDashboardData();
            } else {
                alert(`Upload failed: ${data.detail || 'Unknown error'}`);
            }
        } catch (err) {
            console.error(err);
            submitBtn.innerHTML = `<i class="fa-solid fa-bolt"></i> Extract Facts & Reconcile`;
            submitBtn.disabled = false;
            alert('Error processing file.');
        }
    });
}

function renderUploadResults(data) {
    const container = document.getElementById('upload-results-section');
    const content = document.getElementById('upload-results-content');
    container.classList.remove('hidden');

    content.innerHTML = `
        <div class="glass-card" style="padding:20px; margin-top:16px;">
            <h4 style="color:var(--accent-green); font-size:16px; margin-bottom:8px;"><i class="fa-solid fa-circle-check"></i> Extraction Completed!</h4>
            <p style="font-size:13px; color:var(--text-muted); margin-bottom:12px;">Processed <strong>${data.document.filename}</strong> (${data.document.page_count} pages). Extracted <strong>${data.facts_extracted_count} facts</strong> and generated <strong>${data.relationships_generated_count} cross-document links</strong>.</p>
        </div>
    `;
}

async function handleReseed() {
    if (confirm('Reset database back to initial starter datasets and 4 case studies?')) {
        try {
            const res = await fetch('/api/seed', { method: 'POST' });
            if (res.ok) {
                alert('Database successfully reset!');
                loadDashboardData();
            }
        } catch (err) {
            alert('Failed to reset database.');
        }
    }
}
