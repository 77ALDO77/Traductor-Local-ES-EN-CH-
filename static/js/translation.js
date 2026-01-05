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
            handleAutoActions(); // Trigger translation on language change
        });
    });

    // Temporizador para debounce
    let debounceTimer;

    // Contador de caracteres y Auto-Translate
    if (sourceTextarea && charCount) {
        sourceTextarea.addEventListener('input', () => {
            const length = sourceTextarea.value.length;
            charCount.textContent = `${length} / 5000`;

            if (length > 5000) {
                charCount.classList.add('text-red-500');
            } else {
                charCount.classList.remove('text-red-500');
            }

            // Detección y Traducción Automática
            handleAutoActions();
        });
    }

    // Lógica centralizada de acciones automáticas
    function handleAutoActions() {
        const text = sourceTextarea.value;
        const length = text.length;

        // Detección automática de idioma
        if (length > 5) { // Reducido umbral para detección más rápida
            const detected = detectLanguage(text);
            if (detected && detected !== state.sourceLanguage) {
                state.sourceLanguage = detected;
                updateRadioButtons('language-source', detected);

                // Switch inteligente de target
                let newTarget = state.targetLanguage;
                // Si origen es X, asegurar que destino NO sea X
                if (detected === state.targetLanguage) {
                    if (detected === 'Spanish') newTarget = 'English';
                    else if (detected === 'English') newTarget = 'Spanish';
                    else if (detected === 'Chinese') newTarget = 'Spanish';
                }

                if (newTarget !== state.targetLanguage) {
                    state.targetLanguage = newTarget;
                    updateRadioButtons('language-target', newTarget);
                }

                showNotification(`Detected: ${detected} -> Translating...`, 'info');
            }
        }

        // Traducción automática (Debounce)
        clearTimeout(debounceTimer);
        if (length > 0 && length <= 5000) {
            // Indicador visual en el output antes de traducir
            if (targetOutput && !state.isTranslating) {
                targetOutput.style.opacity = '0.7';
            }

            debounceTimer = setTimeout(() => {
                handleTranslate();
            }, 800); // 800ms es un buen balance
        }
    }

    // Funcion helper para detectar idioma
    function detectLanguage(text) {
        // Muestra de texto para análisis (primeros 100 chars)
        const sample = text.slice(0, 100);

        // 1. Detectar Chino (caracteres Unicode U+4E00 a U+9FFF)
        if (/[\u4E00-\u9FFF]/.test(sample)) return 'Chinese';

        // 2. Detectar Español vs Inglés (palabras funcionales comunes)
        // Contamos ocurrencias simples
        const esCount = (sample.match(/\b(el|la|los|las|de|que|y|en|un|una|es|por|para)\b/gi) || []).length;
        const enCount = (sample.match(/\b(the|and|is|in|to|of|it|you|that|for|on|with)\b/gi) || []).length;

        if (esCount > enCount) return 'Spanish';
        if (enCount > esCount) return 'English';

        return null; // No conclusivo
    }

    // Función helper para actualizar UI
    function updateRadioButtons(groupName, value) {
        document.querySelectorAll(`input[name="${groupName}"]`).forEach(radio => {
            if (radio.value === value) {
                radio.checked = true;
                // Forzar actualización visual del contenedor padre (clases de Tailwind)
                // Esto es un hack porque el CSS depende de :has(:checked) que funciona nativo, 
                // pero a veces requiere repaint.
            }
        });
    }

    // Botón de traducir (ahora es opcional/manual override)
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
    // Si ya está traduciendo, ignorar (a menos que debamos cancelar la anterior, pero simple es mejor aqui)
    if (state.isTranslating) return;

    const text = sourceTextarea?.value?.trim();

    // Reset UI si está vacío
    if (!text) {
        if (targetOutput) targetOutput.textContent = 'Translation will appear here...';
        return;
    }

    if (text.length > 5000) {
        showNotification('Text exceeds 5000 character limit', 'error');
        return;
    }

    if (state.sourceLanguage === state.targetLanguage) {
        return; // Silencioso en auto-mode
    }

    state.isTranslating = true;

    // Feedback visual sutil y Spinner
    if (targetOutput) {
        targetOutput.classList.add('opacity-50'); // Dim effect
    }
    const spinner = document.getElementById('loading-spinner');
    if (spinner) spinner.classList.remove('hidden');
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
            targetOutput.classList.remove('opacity-50');
            // Ya no manipulamos altura, usamos CSS resize-y
        }

    } catch (error) {
        console.error('Translation error:', error);
        // Solo notificar errores graves, no interrupciones menores
        if (targetOutput) {
            targetOutput.classList.remove('opacity-50');
            targetOutput.textContent = 'Error converting text.';
        }
    } finally {
        state.isTranslating = false;
        if (spinner) spinner.classList.add('hidden');
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
            // Disparar evento input para activar resize y traducción
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
