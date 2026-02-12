const API_URL = "http://localhost:8000";

// State
let currentState = {
    isRunning: false,
    stats: {},
    emails: [],
    logs: []
};

// DOM Elements
const toggleBtn = document.getElementById('toggle-btn');
const refreshBtn = document.getElementById('refresh-btn');
const statusText = document.getElementById('status-text');
const statusIndicator = document.getElementById('status-indicator');
const navItems = document.querySelectorAll('nav li');
const pages = document.querySelectorAll('.page');
const pageTitle = document.getElementById('page-title');

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    fetchStats();
    
    // Polling
    setInterval(fetchStatus, 2000);
    setInterval(fetchStats, 5000);
});

// Event Listeners
toggleBtn.addEventListener('click', toggleAgent);
refreshBtn.addEventListener('click', () => {
    fetchStats();
    fetchEmails();
    fetchLogs();
});

navItems.forEach(item => {
    item.addEventListener('click', () => {
        // Active handling
        navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        
        // Page switching
        const target = item.dataset.target;
        pages.forEach(p => p.classList.remove('active'));
        document.getElementById(target).classList.add('active');
        
        pageTitle.textContent = item.textContent;

        if (target === 'emails') fetchEmails();
        if (target === 'logs') fetchLogs();
    });
});

// API Calls
async function fetchStatus() {
    try {
        const res = await fetch(`${API_URL}/control/status`);
        const data = await res.json();
        updateStatus(data.is_running, data.uptime);
    } catch (e) {
        console.error("Status fetch failed", e);
        updateStatus(false, 0);
    }
}

async function fetchStats() {
    try {
        const res = await fetch(`${API_URL}/stats`);
        const data = await res.json();
        
        document.getElementById('stat-emails').textContent = data.total_emails;
        document.getElementById('stat-actions').textContent = data.total_actions;
        document.getElementById('stat-retries').textContent = data.pending_retries;
    } catch (e) {
        console.error("Stats fetch failed", e);
    }
}

async function fetchEmails() {
    try {
        const res = await fetch(`${API_URL}/emails?limit=50`);
        const data = await res.json();
        renderEmails(data);
    } catch (e) {
        console.error("Emails fetch failed", e);
    }
}

async function fetchLogs() {
    try {
        const res = await fetch(`${API_URL}/logs?limit=50`);
        const data = await res.json();
        renderLogs(data);
    } catch (e) {
        console.error("Logs fetch failed", e);
    }
}

async function toggleAgent() {
    const endpoint = currentState.isRunning ? '/control/stop' : '/control/start';
    try {
        await fetch(`${API_URL}${endpoint}`, { method: 'POST' });
        setTimeout(fetchStatus, 500);
    } catch (e) {
        console.error("Toggle failed", e);
    }
}

// Rendering
function updateStatus(isRunning, uptime) {
    currentState.isRunning = isRunning;
    
    if (isRunning) {
        statusText.textContent = `Running (${formatUptime(uptime)})`;
        statusIndicator.classList.add('running');
        toggleBtn.textContent = "Stop Agent";
        toggleBtn.classList.replace('primary', 'secondary');
    } else {
        statusText.textContent = "Stopped";
        statusIndicator.classList.remove('running');
        toggleBtn.textContent = "Start Agent";
        toggleBtn.classList.replace('secondary', 'primary');
    }
    
    document.getElementById('stat-uptime').textContent = formatUptime(uptime);
}

function formatUptime(seconds) {
    if (!seconds) return "0s";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h}h ${m}m ${s}s`;
}

function renderEmails(emails) {
    const tbody = document.getElementById('emails-table-body');
    tbody.innerHTML = emails.map(e => `
        <tr>
            <td>#${e.id}</td>
            <td>${e.subject.substring(0, 40)}...</td>
            <td>${e.sender}</td>
            <td><span class="tag ${getPriorityClass(e.priority_score)}">${e.priority_label || 'Unknown'}</span></td>
            <td>${e.task_status}</td>
            <td>${e.next_action}</td>
        </tr>
    `).join('');
}

function renderLogs(logs) {
    const container = document.getElementById('logs-list');
    container.innerHTML = logs.map(l => `
        <div class="log-item">
            <div class="log-header">
                <span>${l.created_at}</span>
                <span>ID: ${l.email_id}</span>
            </div>
            <div class="log-content">
                <strong>Intent:</strong> ${l.intent} <br>
                <strong>Action:</strong> ${l.agent_action}
            </div>
        </div>
    `).join('');
}

function getPriorityClass(score) {
    if (score >= 80) return 'high';
    if (score >= 50) return 'medium';
    return 'low';
}
