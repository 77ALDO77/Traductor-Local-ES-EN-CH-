/**
 * BoC_Translator - Document Translation Module
 */

const API_BASE = '';

// Estado
const state = {
    uploadedFile: null,
    isTranslating: false,
    sourceLanguage: 'English',
    targetLanguage: 'Spanish'
};

// Elementos DOM
let dropZone, fileInput, browseBtn, translateBtn, progressContainer, progressBar, progressText, downloadSection;

document.addEventListener('DOMContentLoaded', () => {
    // Elementos
    dropZone = document.getElementById('drop-zone');
    fileInput = document.getElementById('file-input');
    browseBtn = document.getElementById('browse-btn');
    translateBtn = document.getElementById('translate-btn');
    progressContainer = document.getElementById('progress-container');
    progressBar = document.getElementById('progress-bar');
    progressText = document.getElementById('progress-text');
    downloadSection = document.getElementById('download-section');

    // Event listeners
    browseBtn?.addEventListener('click', () => fileInput?.click());
    fileInput?.addEventListener('change', handleFileSelect);
    translateBtn?.addEventListener('click', handleTranslate);

    // Drag & Drop
    if (dropZone) {
        dropZone.addEventListener('dragover', handleDragOver);
        dropZone.addEventListener('dragleave', handleDragLeave);
        dropZone.addEventListener('drop', handleDrop);
    }

    // Selectores de idioma
    document.getElementById('source-lang')?.addEventListener('change', (e) => {
        state.sourceLanguage = e.target.value;
    });
    document.getElementById('target-lang')?.addEventListener('change', (e) => {
        state.targetLanguage = e.target.value;
    });

    console.log('Document Translator initialized');
});

function handleDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('border-primary', 'bg-primary/5');
}

function handleDragLeave(e) {
    e.preventDefault();
    dropZone.classList.remove('border-primary', 'bg-primary/5');
}

function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('border-primary', 'bg-primary/5');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        processFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        processFile(files[0]);
    }
}

async function processFile(file) {
    // Limpiar archivo anterior si existe
    if (state.uploadedFile) {
        try {
            await fetch(`${API_BASE}/api/documents/cleanup/${state.uploadedFile.filename}`, {
                method: 'DELETE'
            });
        } catch (error) {
            console.log('Cleanup warning:', error);
        }
        state.uploadedFile = null;

        // Limpiar UI
        downloadSection.classList.add('hidden');
        downloadSection.innerHTML = '';
        progressContainer.classList.add('hidden');
    }

    // Validar extensión
    const validExtensions = ['pdf', 'docx', 'xlsx', 'doc', 'xls'];
    const ext = file.name.split('.').pop().toLowerCase();

    if (!validExtensions.includes(ext)) {
        showNotification('Unsupported file type. Use PDF, DOCX, or XLSX.', 'error');
        return;
    }

    // Validar tamaño (10MB)
    if (file.size > 10 * 1024 * 1024) {
        showNotification('File exceeds 10MB limit.', 'error');
        return;
    }

    // Mostrar archivo seleccionado
    showFileSelected(file);

    // Subir archivo
    const formData = new FormData();
    formData.append('file', file);

    try {
        showNotification('Uploading file...', 'info');

        const response = await fetch(`${API_BASE}/api/documents/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const result = await response.json();
        state.uploadedFile = result;

        showNotification(`File uploaded: ${result.total_chunks} chunks detected`, 'success');
        showPreview(result.preview_text);
        translateBtn.disabled = false;

    } catch (error) {
        console.error('Upload error:', error);
        showNotification(`Upload failed: ${error.message}`, 'error');
    }
}

function showFileSelected(file) {
    const fileInfo = document.getElementById('file-info');
    if (fileInfo) {
        fileInfo.innerHTML = `
            <div class="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <span class="material-symbols-outlined text-green-600">check_circle</span>
                <div>
                    <p class="font-medium text-green-800 dark:text-green-200">${file.name}</p>
                    <p class="text-sm text-green-600 dark:text-green-400">${formatFileSize(file.size)}</p>
                </div>
            </div>
        `;
        fileInfo.classList.remove('hidden');
    }
}

function showPreview(text) {
    const previewContainer = document.getElementById('preview-container');
    if (previewContainer) {
        previewContainer.innerHTML = `
            <div class="mt-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <p class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Preview:</p>
                <p class="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">${text}</p>
            </div>
        `;
        previewContainer.classList.remove('hidden');
    }
}

async function handleTranslate() {
    if (!state.uploadedFile || state.isTranslating) return;

    if (state.sourceLanguage === state.targetLanguage) {
        showNotification('Source and target languages must be different', 'warning');
        return;
    }

    state.isTranslating = true;
    translateBtn.disabled = true;
    showProgress(true);

    const formData = new FormData();
    formData.append('filename', state.uploadedFile.filename);
    formData.append('source_language', state.sourceLanguage);
    formData.append('target_language', state.targetLanguage);

    try {
        const response = await fetch(`${API_BASE}/api/documents/translate/stream`, {
            method: 'POST',
            body: formData
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    updateProgress(data);

                    if (data.status === 'completed') {
                        showDownloadButton(data.download_url, data.translated_filename);
                        showNotification(`Translation completed in ${(data.processing_time_ms / 1000).toFixed(1)}s`, 'success');
                    } else if (data.status === 'error') {
                        showNotification(data.message, 'error');
                    }
                }
            }
        }

    } catch (error) {
        console.error('Translation error:', error);
        showNotification(`Translation failed: ${error.message}`, 'error');
    } finally {
        state.isTranslating = false;
        translateBtn.disabled = false;
    }
}

function showProgress(show) {
    if (progressContainer) {
        progressContainer.classList.toggle('hidden', !show);
    }
}

function updateProgress(data) {
    if (progressBar) {
        progressBar.style.width = `${data.progress_percent}%`;
    }
    if (progressText) {
        // Mostrar información detallada del progreso
        const percent = data.progress_percent.toFixed(1);
        const chunks = `${data.current_chunk}/${data.total_chunks}`;

        let detailedMessage = `${percent}% - ${data.message}`;

        // Agregar detalles específicos de chunks si están disponibles
        if (data.current_chunk && data.total_chunks && data.total_chunks > 1) {
            detailedMessage += ` (${chunks} elementos)`;
        }

        progressText.innerHTML = `
            <div class="space-y-2">
                <div class="flex justify-between items-center">
                    <span class="font-semibold">${percent}%</span>
                    <span class="text-sm">${chunks} chunks</span>
                </div>
                <div class="text-sm text-gray-600 dark:text-gray-400">
                    ${data.message}
                </div>
            </div>
        `;
    }
}

function showDownloadButton(url, filename) {
    if (downloadSection) {
        downloadSection.innerHTML = `
            <a href="${url}" download="${filename}" 
               class="inline-flex items-center gap-2 px-6 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors">
                <span class="material-symbols-outlined">download</span>
                Download: ${filename}
            </a>
        `;
        downloadSection.classList.remove('hidden');
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white font-medium z-50 transition-all`;

    const colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        warning: 'bg-yellow-600',
        info: 'bg-blue-600'
    };
    notification.classList.add(colors[type] || colors.info);
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.classList.add('opacity-0');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
