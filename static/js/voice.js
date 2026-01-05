/**
 * BoC_Translator - Voice Translation Module
 * Maneja grabación de audio, WebSocket y UI del chat de voz
 */

const API_BASE = '';

// Estado
const state = {
    isRecording: false,
    sourceLanguage: 'Spanish',
    targetLanguage: 'Spanish',
    websocket: null,
    mediaRecorder: null,
    mediaStream: null,
    isConnected: false,
    reconnectAttempts: 0,
    // Elementos de mensaje en curso para transcripción/traducción progresiva
    currentOriginalEl: null,
    currentTranslatedEl: null
};

// Elementos DOM
let micButton, chatContainer, waveform, statusText, languageDropdown;

document.addEventListener('DOMContentLoaded', () => {
    // Elementos
    micButton = document.getElementById('mic-button');
    chatContainer = document.getElementById('chat-container');
    waveform = document.getElementById('waveform');
    statusText = document.getElementById('status-text');
    languageDropdown = document.getElementById('language-dropdown');

    // Event listeners
    micButton?.addEventListener('click', toggleRecording);

    // Selector de idioma destino
    document.querySelectorAll('[data-language]').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const lang = e.currentTarget.dataset.language;
            setTargetLanguage(lang);
        });
    });

    // Selector de idioma origen (usuario habla)
    document.querySelectorAll('[data-source-language]').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const lang = e.currentTarget.dataset.sourceLanguage;
            setSourceLanguage(lang);
        });
    });

    // Conectar WebSocket
    connectWebSocket();

    // Limpiar chat de demo
    if (chatContainer) {
        chatContainer.innerHTML = '';
    }

    console.log('Voice Translation initialized');
});

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/voice/ws`;

    state.websocket = new WebSocket(wsUrl);

    state.websocket.onopen = () => {
        console.log('WebSocket connected');
        state.isConnected = true;
        state.reconnectAttempts = 0;
        updateStatus('Listo para grabar');

        // Enviar configuración inicial
        state.websocket.send(JSON.stringify({
            type: 'config',
            source_language: state.sourceLanguage,
            target_language: state.targetLanguage
        }));
    };

    state.websocket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };

    state.websocket.onclose = () => {
        console.log('WebSocket disconnected');
        state.isConnected = false;
        updateStatus('Desconectado. Reconectando...');

        // Si estaba grabando, detener con aviso
        if (state.isRecording) {
            stopRecording(true);
            showNotification('Conexión perdida. Grabación detenida.', 'warning');
        }

        // Reconectar con backoff exponencial (máx 10s)
        state.reconnectAttempts += 1;
        const delay = Math.min(10000, 1000 * Math.pow(2, state.reconnectAttempts - 1));
        setTimeout(connectWebSocket, delay);
    };

    state.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateStatus('Error de conexión');
    };
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'status':
            updateStatus(message.data.message);
            break;

        case 'transcription':
            // Mostrar/actualizar transcripción progresiva (burbuja izquierda)
            updateProgressMessage('original', message.data.text, message.data.language);
            break;

        case 'translation':
            // Mostrar/actualizar traducción progresiva (burbuja derecha)
            updateProgressMessage('translated', message.data.translated, message.data.target_language);
            break;

        case 'error':
            console.error('Error del servidor:', message.data.message);
            showNotification(message.data.message, 'error');
            break;

        case 'pong':
            // Keep-alive response
            break;

        case 'segment_end':
            // Finalizar burbuja actual y preparar para la siguiente
            state.currentOriginalEl = null;
            state.currentTranslatedEl = null;
            break;
    }
}

async function toggleRecording() {
    if (state.isRecording) {
        stopRecording();
    } else {
        await startRecording();
    }
}

async function startRecording() {
    if (!state.isConnected) {
        showNotification('No hay conexión con el servidor', 'error');
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                sampleRate: 48000,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        state.mediaStream = stream;
        // Preferir 'audio/webm;codecs=opus' con fallback seguro
        let preferredType = 'audio/webm;codecs=opus';
        let mimeType = undefined;
        try {
            if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported) {
                if (MediaRecorder.isTypeSupported(preferredType)) {
                    mimeType = preferredType;
                } else if (MediaRecorder.isTypeSupported('audio/webm')) {
                    mimeType = 'audio/webm';
                } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
                    // Último recurso (no deseado para backend actual)
                    mimeType = 'audio/ogg;codecs=opus';
                }
            }
        } catch (_) { /* no-op */ }

        state.mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

        // Envío en streaming cada 0.5s para menor latencia
        state.mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0 && state.isConnected && state.websocket?.readyState === WebSocket.OPEN) {
                blobToBase64(event.data).then((base64Audio) => {
                    try {
                        state.websocket.send(JSON.stringify({
                            type: 'audio',
                            data: base64Audio,
                            sample_rate: 48000,
                            source_language: state.sourceLanguage,
                            target_language: state.targetLanguage
                        }));
                    } catch (e) {
                        console.error('Error enviando chunk de audio:', e);
                    }
                }).catch(err => console.error('Error convirtiendo audio a base64:', err));
            }
        };

        state.mediaRecorder.onstop = () => {
            // Detener stream
            if (state.mediaStream) {
                state.mediaStream.getTracks().forEach(track => track.stop());
                state.mediaStream = null;
            }
        };

        // timeslice en ms para generar chunks de 0.5s
        state.mediaRecorder.start(500);
        state.isRecording = true;

        updateMicButton(true);
        showWaveform(true);
        updateStatus('Grabando... (streaming)');

    } catch (error) {
        console.error('Error accessing microphone:', error);

        let errorMsg = 'No se pudo acceder al micrófono.';
        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            errorMsg = 'Permiso de micrófono denegado. Por favor permítelo en tu navegador.';
        } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
            errorMsg = 'No se encontró ningún micrófono.';
        } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
            errorMsg = 'El micrófono está siendo usado por otra aplicación.';
        } else if (window.isSecureContext === false) {
            errorMsg = 'Error: El acceso al micrófono requiere HTTPS o localhost.';
        }

        showNotification(errorMsg, 'error');
        updateStatus('Error de micrófono');
    }
}

function stopRecording(fromDisconnect = false) {
    if (state.mediaRecorder && state.isRecording) {
        try { state.mediaRecorder.stop(); } catch { }
        state.isRecording = false;

        updateMicButton(false);
        showWaveform(false);
        updateStatus(fromDisconnect ? 'Desconectado' : 'Listo para grabar');

        // Reiniciar referencias de mensajes en curso para el próximo turno
        state.currentOriginalEl = null;
        state.currentTranslatedEl = null;
    }
}

// Utilidad: convertir Blob a base64 (sin prefijo data:)
function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            try {
                const base64 = (reader.result || '').toString().split(',')[1];
                resolve(base64);
            } catch (e) {
                reject(e);
            }
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

function addChatMessage(text, type, language) {
    if (!chatContainer || !text) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = type === 'original'
        ? 'flex justify-start'
        : 'flex justify-end';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = type === 'original'
        ? 'bg-[#F5F5F5] dark:bg-zinc-800 rounded-lg rounded-bl-none p-4 max-w-md'
        : 'bg-primary/10 dark:bg-primary/20 rounded-lg rounded-br-none p-4 max-w-md';

    const textP = document.createElement('p');
    textP.className = 'text-black dark:text-white';
    textP.textContent = text;

    // Badge de idioma
    const langBadge = document.createElement('span');
    langBadge.className = 'text-xs text-gray-500 dark:text-gray-400 block mt-1';
    langBadge.textContent = language || '';

    bubbleDiv.appendChild(textP);
    bubbleDiv.appendChild(langBadge);
    messageDiv.appendChild(bubbleDiv);
    chatContainer.appendChild(messageDiv);

    // Scroll al final
    chatContainer.scrollTop = chatContainer.scrollHeight;

    return { container: messageDiv, bubble: bubbleDiv, textEl: textP, langEl: langBadge };
}

function updateProgressMessage(kind, text, language) {
    if (!chatContainer) return;
    let refKey = kind === 'original' ? 'currentOriginalEl' : 'currentTranslatedEl';
    let ref = state[refKey];

    if (!ref) {
        ref = addChatMessage(text, kind, language);
        state[refKey] = ref;
    } else if (ref.textEl) {
        ref.textEl.textContent = text;
        if (language && ref.langEl) ref.langEl.textContent = language;
    }

    // asegurar scroll al final
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setTargetLanguage(language) {
    state.targetLanguage = language;

    // Actualizar UI del dropdown
    const selectedLangEl = document.getElementById('selected-language');
    if (selectedLangEl) {
        selectedLangEl.textContent = language;
    }

    // Notificar al servidor
    if (state.isConnected && state.websocket) {
        state.websocket.send(JSON.stringify({
            type: 'config',
            source_language: state.sourceLanguage,
            target_language: language
        }));
    }

    showNotification(`Idioma destino: ${language}`, 'info');
}

function setSourceLanguage(language) {
    state.sourceLanguage = language;

    // Actualizar UI del dropdown
    const selectedSrcEl = document.getElementById('selected-source-language');
    if (selectedSrcEl) {
        selectedSrcEl.textContent = language;
    }

    // Notificar al servidor
    if (state.isConnected && state.websocket) {
        state.websocket.send(JSON.stringify({
            type: 'config',
            source_language: language,
            target_language: state.targetLanguage
        }));
    }

    showNotification(`Hablas en: ${language}`, 'info');
}

function updateMicButton(isRecording) {
    if (!micButton) return;

    if (isRecording) {
        micButton.classList.add('bg-red-500', 'animate-pulse');
        micButton.classList.remove('bg-primary');
    } else {
        micButton.classList.remove('bg-red-500', 'animate-pulse');
        micButton.classList.add('bg-primary');
    }
}

function showWaveform(show) {
    if (waveform) {
        waveform.style.opacity = show ? '1' : '0.3';
    }
}

function updateStatus(message) {
    if (statusText) {
        statusText.textContent = message;
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white font-medium z-50`;

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

// Keep-alive ping cada 30 segundos
setInterval(() => {
    if (state.isConnected && state.websocket) {
        state.websocket.send(JSON.stringify({ type: 'ping' }));
    }
}, 30000);
