/**
 * BoC_Translator - Frontend Translation Module
 * Maneja la comunicación con el backend para traducciones de texto
 */

const API_BASE = '';  // Mismo origen

// Estado de la aplicación
const state = {
    isTranslating: false,
    sourceLanguage: 'English',
    targetLanguage: 'Spanish'
};

// Elementos del DOM
let sourceTextarea;
let targetOutput;
let translateBtn;
let charCount;

/**
 * Inicializa los event listeners cuando el DOM está listo
 */
document.addEventListener('DOMContentLoaded', () => {
    // Obtener elementos
    sourceTextarea = document.querySelector('textarea[placeholder="Enter text to translate..."]');
    targetOutput = document.getElementById('translation-output');
    translateBtn = document.getElementById('translate-btn');
    charCount = document.getElementById('char-count');

    // Event listeners para selección de idioma origen
    document.querySelectorAll('input[name="language-source"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            state.sourceLanguage = e.target.value;
            console.log('Source language:', state.sourceLanguage);
        });
    });

    // Event listeners para selección de idioma destino
    document.querySelectorAll('input[name="language-target"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            state.targetLanguage = e.target.value;
            console.log('Target language:', state.targetLanguage);
        });
    });

    // Contador de caracteres
    if (sourceTextarea && charCount) {
        sourceTextarea.addEventListener('input', () => {
            const length = sourceTextarea.value.length;
            charCount.textContent = `${length} / 5000`;

            if (length > 5000) {
                charCount.classList.add('text-red-500');
            } else {
                charCount.classList.remove('text-red-500');
            }
        });
    }

    // Botón de traducir
    if (translateBtn) {
        translateBtn.addEventListener('click', handleTranslate);
    }

    // Botón de pegar
    document.getElementById('paste-btn')?.addEventListener('click', handlePaste);

    // Botón de copiar
    document.getElementById('copy-btn')?.addEventListener('click', handleCopy);

    // Inicializar estado de idiomas desde los radio buttons checked
    const checkedSource = document.querySelector('input[name="language-source"]:checked');
    const checkedTarget = document.querySelector('input[name="language-target"]:checked');

    if (checkedSource) state.sourceLanguage = checkedSource.value;
    if (checkedTarget) state.targetLanguage = checkedTarget.value;

    console.log('BoC_Translator initialized');
    console.log('Source:', state.sourceLanguage, 'Target:', state.targetLanguage);
});

/**
 * Maneja la traducción del texto
 */
async function handleTranslate() {
    if (state.isTranslating) return;

    const text = sourceTextarea?.value?.trim();

    if (!text) {
        showNotification('Please enter text to translate', 'warning');
        return;
    }

    if (text.length > 5000) {
        showNotification('Text exceeds 5000 character limit', 'error');
        return;
    }

    if (state.sourceLanguage === state.targetLanguage) {
        showNotification('Source and target languages must be different', 'warning');
        return;
    }

    state.isTranslating = true;
    setTranslateButtonLoading(true);

    try {
        const response = await fetch(`${API_BASE}/api/translate/text`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: text,
                source_language: state.sourceLanguage,
                target_language: state.targetLanguage
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Translation failed');
        }

        const result = await response.json();

        // Mostrar resultado
        if (targetOutput) {
            targetOutput.textContent = result.translated_text;
        }

        // Mostrar tiempo de procesamiento
        if (result.processing_time_ms) {
            console.log(`Translation completed in ${result.processing_time_ms}ms`);
        }

    } catch (error) {
        console.error('Translation error:', error);
        showNotification(`Error: ${error.message}`, 'error');

        if (targetOutput) {
            targetOutput.textContent = 'Translation failed. Please try again.';
        }
    } finally {
        state.isTranslating = false;
        setTranslateButtonLoading(false);
    }
}

/**
 * Maneja el pegado desde el portapapeles
 */
async function handlePaste() {
    try {
        const text = await navigator.clipboard.readText();
        if (sourceTextarea) {
            sourceTextarea.value = text;
            sourceTextarea.dispatchEvent(new Event('input'));
        }
    } catch (error) {
        showNotification('Unable to paste from clipboard', 'error');
    }
}

/**
 * Maneja la copia al portapapeles
 */
async function handleCopy() {
    const text = targetOutput?.textContent;

    if (!text || text === 'Translation will appear here...') {
        showNotification('No translation to copy', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard!', 'success');
    } catch (error) {
        showNotification('Unable to copy to clipboard', 'error');
    }
}

/**
 * Cambia el estado del botón de traducir a loading
 */
function setTranslateButtonLoading(loading) {
    if (!translateBtn) return;

    if (loading) {
        translateBtn.disabled = true;
        translateBtn.textContent = 'Translating...';
    } else {
        translateBtn.disabled = false;
        translateBtn.innerHTML = `
            <span class="material-symbols-outlined">translate</span>
            <span>Translate</span>
        `;
    }
}

// Eliminado: setOutputLoading por respuesta casi instantánea

/**
 * Muestra una notificación toast
 */
function showNotification(message, type = 'info') {
    // Crear elemento de notificación
    const notification = document.createElement('div');
    notification.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white font-medium z-50 transition-all transform translate-y-0 opacity-100`;

    // Color según tipo
    const colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        warning: 'bg-yellow-600',
        info: 'bg-blue-600'
    };
    notification.classList.add(colors[type] || colors.info);
    notification.textContent = message;

    document.body.appendChild(notification);

    // Remover después de 3 segundos
    setTimeout(() => {
        notification.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
