/**
 * BoC_Translator - Voice Translation Module
 * Maneja grabación de audio, WebSocket y UI del chat de voz
 */

const API_BASE = '';

// Estado
const state = {
    isRecording: false,
    targetLanguage: 'Spanish',
    websocket: null,
    mediaRecorder: null,
    audioChunks: [],
    isConnected: false
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

    // Selector de idioma
    document.querySelectorAll('[data-language]').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const lang = e.currentTarget.dataset.language;
            setTargetLanguage(lang);
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
        updateStatus('Listo para grabar');

        // Enviar configuración inicial
        state.websocket.send(JSON.stringify({
            type: 'config',
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

        // Reconectar después de 2 segundos
        setTimeout(connectWebSocket, 2000);
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
            // Mostrar texto original (burbuja izquierda)
            addChatMessage(message.data.text, 'original', message.data.language);
            break;

        case 'translation':
            // Mostrar traducción (burbuja derecha)
            addChatMessage(message.data.translated, 'translated', message.data.target_language);
            break;

        case 'error':
            console.error('Error del servidor:', message.data.message);
            showNotification(message.data.message, 'error');
            break;

        case 'pong':
            // Keep-alive response
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
                sampleRate: 16000,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        state.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });

        state.audioChunks = [];

        state.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                state.audioChunks.push(event.data);
            }
        };

        state.mediaRecorder.onstop = async () => {
            // Convertir chunks a blob
            const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });

            // Convertir a WAV para enviar
            const wavBlob = await convertToWav(audioBlob);

            // Enviar por WebSocket
            sendAudioToServer(wavBlob);

            // Detener stream
            stream.getTracks().forEach(track => track.stop());
        };

        state.mediaRecorder.start();
        state.isRecording = true;

        updateMicButton(true);
        showWaveform(true);
        updateStatus('Grabando...');

    } catch (error) {
        console.error('Error accessing microphone:', error);
        showNotification('No se pudo acceder al micrófono', 'error');
    }
}

function stopRecording() {
    if (state.mediaRecorder && state.isRecording) {
        state.mediaRecorder.stop();
        state.isRecording = false;

        updateMicButton(false);
        showWaveform(false);
        updateStatus('Procesando...');
    }
}

async function convertToWav(webmBlob) {
    // Usar AudioContext para decodificar y re-encodear
    const audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000
    });

    const arrayBuffer = await webmBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

    // Convertir a WAV
    const wavBuffer = audioBufferToWav(audioBuffer);
    return new Blob([wavBuffer], { type: 'audio/wav' });
}

function audioBufferToWav(buffer) {
    const numOfChan = 1; // Mono
    const length = buffer.length * numOfChan * 2;
    const bufferArray = new ArrayBuffer(44 + length);
    const view = new DataView(bufferArray);
    const channels = [];
    let sample;
    let offset = 0;
    let pos = 0;

    // Escribir header WAV
    setUint32(0x46464952); // "RIFF"
    setUint32(36 + length); // file length - 8
    setUint32(0x45564157); // "WAVE"

    setUint32(0x20746d66); // "fmt " chunk
    setUint32(16); // length
    setUint16(1); // PCM
    setUint16(numOfChan);
    setUint32(buffer.sampleRate);
    setUint32(buffer.sampleRate * 2 * numOfChan); // byte rate
    setUint16(numOfChan * 2); // block align
    setUint16(16); // bits per sample

    setUint32(0x61746164); // "data" chunk
    setUint32(length);

    // Escribir datos
    const channelData = buffer.getChannelData(0);
    for (let i = 0; i < buffer.length; i++) {
        sample = Math.max(-1, Math.min(1, channelData[i]));
        sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(pos, sample, true);
        pos += 2;
    }

    function setUint16(data) {
        view.setUint16(pos, data, true);
        pos += 2;
    }

    function setUint32(data) {
        view.setUint32(pos, data, true);
        pos += 4;
    }

    return bufferArray;
}

async function sendAudioToServer(wavBlob) {
    if (!state.isConnected || !state.websocket) {
        showNotification('No hay conexión', 'error');
        return;
    }

    // Convertir a base64
    const reader = new FileReader();
    reader.onloadend = () => {
        const base64Audio = reader.result.split(',')[1];

        state.websocket.send(JSON.stringify({
            type: 'audio',
            data: base64Audio,
            sample_rate: 16000,
            target_language: state.targetLanguage
        }));

        updateStatus('Transcribiendo...');
    };
    reader.readAsDataURL(wavBlob);
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
    langBadge.textContent = language;

    bubbleDiv.appendChild(textP);
    bubbleDiv.appendChild(langBadge);
    messageDiv.appendChild(bubbleDiv);
    chatContainer.appendChild(messageDiv);

    // Scroll al final
    chatContainer.scrollTop = chatContainer.scrollHeight;

    updateStatus('Listo para grabar');
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
            target_language: language
        }));
    }

    showNotification(`Idioma destino: ${language}`, 'info');
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
