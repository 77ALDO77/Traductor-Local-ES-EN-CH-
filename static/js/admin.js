// Initial load
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadLogs();
});

function checkAuth() {
    const token = sessionStorage.getItem('auth_token');
    if (!token) {
        window.location.href = '/login';
    }
    return token;
}

function switchView(viewName) {
    // Update Sidebar
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.view === viewName) {
            item.classList.add('active');
        }
    });

    // Update Content
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active-view'));
    document.getElementById(`view-${viewName}`).classList.add('active-view');

    // Update Headers
    const titles = {
        'audit': 'System Audit Logs',
        'files': 'Residual Files Cleanup',
        'system': 'System Resource Monitor'
    };
    const titleEl = document.getElementById('page-heading');
    if (titleEl) titleEl.textContent = titles[viewName];

    // Load Data
    if (viewName === 'audit') loadLogs();
    if (viewName === 'files') loadFiles();
    if (viewName === 'system') loadSystemStatus();
}

function refreshCurrentView() {
    const activeItem = document.querySelector('.nav-item.active');
    if (activeItem && activeItem.dataset.view) {
        switchView(activeItem.dataset.view);
    } else {
        loadLogs(); // Default
    }
}

// --- LOGS FUNCTIONALITY ---

async function loadLogs() {
    const token = checkAuth();
    if (!token) return;

    try {
        const response = await fetch('/api/admin/audit-logs', { headers: { 'Authorization': 'Basic ' + token } });
        if (response.status === 401) return logout();

        const logs = await response.json();
        renderLogsTable(logs);
    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

function renderLogsTable(logs) {
    const tbody = document.querySelector('#logsTable tbody');
    tbody.innerHTML = '';

    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center p-4 text-gray-500">No logs found</td></tr>';
        return;
    }

    logs.forEach(log => {
        const tr = document.createElement('tr');

        let statusClass = 'status-success';
        const s = (log.Status || '').toUpperCase();
        if (s.includes('FAIL') || s.includes('ERROR')) statusClass = 'status-failed';
        else if (s.includes('WIPED')) statusClass = 'status-wiped';
        else if (s.includes('CANCEL')) statusClass = 'status-cancelled';

        tr.innerHTML = `
            <td>${formatDate(log.Timestamp)}</td>
            <td><strong>${log.Action}</strong></td>
            <td>${log.Filename}</td>
            <td><span class="status-badge ${statusClass}">${log.Status}</span></td>
            <td class="text-gray-500 font-mono text-xs">${log.Details}</td>
        `;
        tbody.appendChild(tr);
    });
}

// --- FILES FUNCTIONALITY ---

async function loadFiles() {
    const token = checkAuth();
    if (!token) return;

    try {
        const response = await fetch('/api/admin/files', { headers: { 'Authorization': 'Basic ' + token } });
        if (response.status === 401) return logout();

        const files = await response.json();
        renderFilesTable(files);
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

function renderFilesTable(files) {
    const tbody = document.querySelector('#filesTable tbody');
    const deleteAllBtn = document.getElementById('delete-all-btn');
    tbody.innerHTML = '';

    // Show/hide Delete All button based on file count
    if (files.length > 0) {
        deleteAllBtn?.classList.remove('hidden');
        deleteAllBtn?.classList.add('flex');
    } else {
        deleteAllBtn?.classList.add('hidden');
        deleteAllBtn?.classList.remove('flex');
    }

    if (files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center p-4 text-gray-500">No residual files found. Clean system!</td></tr>';
        return;
    }

    files.forEach(file => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="font-medium">${file.name}</td>
            <td>${formatBytes(file.size)}</td>
            <td>${new Date(file.created * 1000).toLocaleString()}</td>
            <td>
                <button class="btn-wipe" onclick="deleteFile('${file.name}')">
                    <span class="material-symbols-outlined" style="font-size: 16px;">delete_forever</span>
                    Secure Wipe
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function deleteFile(filename) {
    if (!confirm(`WARNING: This will overwrite "${filename}" with random data and then permanently delete it. This action cannot be undone.\n\nProceed?`)) {
        return;
    }

    const token = checkAuth();
    try {
        const response = await fetch(`/api/admin/files/${filename}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Basic ' + token }
        });

        if (response.ok) {
            loadFiles(); // Reload list
            alert('File securely wiped and deleted.');
        } else {
            alert('Failed to delete file.');
        }
    } catch (error) {
        console.error(error);
        alert('Error during deletion.');
    }
}

async function deleteAllFiles() {
    if (!confirm(`⚠️ CRITICAL WARNING ⚠️\n\nThis will PERMANENTLY and SECURELY delete ALL residual files in the system.\n\nAll files will be:\n1. Overwritten with random data\n2. Permanently deleted\n\nThis action CANNOT be undone.\n\nProceed with bulk deletion?`)) {
        return;
    }

    const token = checkAuth();
    try {
        const btn = document.getElementById('delete-all-btn');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<span class="material-symbols-outlined text-[20px] animate-spin">sync</span> Deleting...';
        btn.disabled = true;

        const response = await fetch('/api/admin/files', {
            method: 'DELETE',
            headers: { 'Authorization': 'Basic ' + token }
        });

        if (response.ok) {
            const result = await response.json();
            loadFiles(); // Reload list

            let message = result.message;
            if (result.errors && result.errors.length > 0) {
                message += `\n\nErrors:\n${result.errors.join('\n')}`;
            }
            alert(message);
        } else {
            alert('Failed to delete files.');
        }

        btn.innerHTML = originalHTML;
        btn.disabled = false;
    } catch (error) {
        console.error(error);
        alert('Error during bulk deletion.');
        const btn = document.getElementById('delete-all-btn');
        btn.disabled = false;
    }
}

// --- SYSTEM FUNCTIONALITY ---

async function loadSystemStatus() {
    const token = checkAuth();
    if (!token) return;

    try {
        const response = await fetch('/api/admin/system', { headers: { 'Authorization': 'Basic ' + token } });
        if (response.status === 401) return logout();
        const data = await response.json();

        // Render GPU
        const te = data.translator_engine || {};
        const gpu = te.gpu || {};

        if (gpu.vram_total_mb) {
            const vramPct = Math.round((gpu.vram_used_mb / gpu.vram_total_mb) * 100);
            updateBar('vram', vramPct, `${gpu.vram_used_mb} / ${gpu.vram_total_mb} MB`);
            updateBar('gpu-util', gpu.gpu_util_percent, `${gpu.gpu_util_percent}%`);
        } else {
            // Offline or CPU mode
            document.getElementById('vram-text').textContent = 'N/A (CPU Mode or Offline)';
            document.getElementById('vram-bar').style.width = '0%';
        }

        // Render Models
        const modelList = document.getElementById('model-list');
        modelList.innerHTML = '';

        // NLLB/Whisper status
        const loaded = te.loaded_models || {};
        addModelItem(modelList, 'NLLB-200 (Translator)', loaded.nllb ? 'Ready' : 'Inactive', loaded.nllb);
        addModelItem(modelList, 'Whisper (Speech)', loaded.whisper ? 'Loaded' : 'Sleeping', loaded.whisper);

        // Ollama
        const ollama = data.ollama || {};
        (ollama.running_models || []).forEach(m => {
            addModelItem(modelList, `Ollama: ${m.name}`, 'VRAM Loaded', true);
        });

    } catch (error) {
        console.error('Error loading system stats:', error);
    }
}

function updateBar(idPrefix, percent, text) {
    document.getElementById(`${idPrefix}-bar`).style.width = `${percent}%`;
    document.getElementById(`${idPrefix}-text`).textContent = text;

    // Color logic
    const bar = document.getElementById(`${idPrefix}-bar`);
    if (percent > 90) bar.style.backgroundColor = '#9b1c1c'; // Critical
    else if (percent > 70) bar.style.backgroundColor = '#b45309'; // Warning
    else bar.style.backgroundColor = '#0e9f6e'; // Good
}

function addModelItem(parent, name, status, isActive) {
    const li = document.createElement('li');
    li.style.cssText = 'padding:12px 0; border-bottom:1px solid #f3f4f6; display:flex; justify-content:space-between; align-items:center;';
    li.innerHTML = `
        <span style="font-weight:500;">${name}</span>
        <span class="status-badge ${isActive ? 'status-success' : 'status-wiped'}">${status}</span>
    `;
    parent.appendChild(li);
}

async function optimizeSystem() {
    if (!confirm('This will attempt to release GPU memory by unloading idle models and clearing caches. The application may lag briefly.\n\nProceed?')) return;

    const token = checkAuth();
    try {
        const btn = document.querySelector('button[onclick="optimizeSystem()"]');
        const originalText = btn.innerHTML;
        btn.innerHTML = 'Optimizing...';
        btn.disabled = true;

        const response = await fetch('/api/admin/system/optimize', {
            method: 'POST',
            headers: { 'Authorization': 'Basic ' + token }
        });

        const result = await response.json();
        alert('Optimization triggered successfully.');
        loadSystemStatus(); // Refresh stats

        btn.innerHTML = originalText;
        btn.disabled = false;
    } catch (e) {
        alert('Optimization failed: ' + e);
    }
}

// --- UTILS ---

function formatDate(isoString) {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString();
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function logout() {
    sessionStorage.removeItem('auth_token');
    window.location.href = '/login';
}

// Make functions global for inline events
window.switchView = switchView;
window.loadLogs = loadLogs;
window.loadFiles = loadFiles;
window.loadSystemStatus = loadSystemStatus;
window.optimizeSystem = optimizeSystem;
window.deleteFile = deleteFile;
window.deleteAllFiles = deleteAllFiles;
window.logout = logout;
window.refreshCurrentView = refreshCurrentView;
