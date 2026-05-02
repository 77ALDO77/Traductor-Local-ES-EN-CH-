import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Copy, ClipboardPaste } from 'lucide-react';

export default function Dashboard() {
    const [sourceLang, setSourceLang] = useState('English');
    const [targetLang, setTargetLang] = useState('Spanish');
    const [text, setText] = useState('');
    const [translatedText, setTranslatedText] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [charCount, setCharCount] = useState(0);

    const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Auto-translate Logic
    useEffect(() => {
        setCharCount(text.length);

        if (debounceTimer.current) clearTimeout(debounceTimer.current);

        if (text.length > 0 && text.length <= 5000) {
            debounceTimer.current = setTimeout(() => {
                handleTranslate();
            }, 800);
        } else if (text.length === 0) {
            setTranslatedText('');
            setError(null);
        }
    }, [text, sourceLang, targetLang]);


    const handleTranslate = async () => {
        if (!text.trim() || text.length > 5000 || sourceLang === targetLang) return;

        setIsLoading(true);
        setError(null);
        try {
            const response = await axios.post('/api/translate/text', {
                text,
                source_language: sourceLang,
                target_language: targetLang,
            });
            setTranslatedText(response.data.translated_text);
        } catch (err) {
            console.error("Translation error:", err);
            const message = axios.isAxiosError(err) && err.response?.data?.detail
                ? err.response.data.detail
                : 'Translation failed. Please try again.';
            setError(message);
            setTranslatedText('');
        } finally {
            setIsLoading(false);
        }
    };

    const handlePaste = async () => {
        try {
            const clipboardText = await navigator.clipboard.readText();
            setText(clipboardText);
        } catch (err) {
            console.error('Failed to read clipboard', err);
        }
    };

    const handleCopy = async () => {
        if (translatedText) {
            await navigator.clipboard.writeText(translatedText);
            // Optional: Toast success
        }
    };

    return (
        <div className="flex flex-col gap-8 max-w-5xl mx-auto">
            <div className="flex flex-col gap-2">
                <h1 className="text-gray-900 dark:text-white text-3xl font-bold">Text Translation</h1>
                <p className="text-gray-600 dark:text-gray-400 text-base">
                    Translate text between languages with high accuracy.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* SOURCE PANEL */}
                <div className="flex flex-col gap-4 bg-container-light dark:bg-container-dark dark:border dark:border-white/10 p-6 rounded-xl shadow-sm">
                    <div className="flex h-10 w-full items-center justify-center rounded-lg bg-background-light dark:bg-black/20 p-1">
                        {['English', 'Spanish', 'Chinese'].map((lang) => (
                            <button
                                key={`source-${lang}`}
                                onClick={() => setSourceLang(lang)}
                                className={`flex cursor-pointer h-full grow items-center justify-center overflow-hidden rounded-lg px-2 text-sm font-medium leading-normal transition-all ${sourceLang === lang
                                    ? 'bg-white dark:bg-background-dark shadow-sm text-[#171212] dark:text-white'
                                    : 'text-[#866569] dark:text-gray-400'
                                    }`}
                            >
                                {lang}
                            </button>
                        ))}
                    </div>

                    <div className="flex flex-col flex-1 relative">
                        <textarea
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            className="form-input flex w-full min-w-0 flex-1 resize-y rounded-lg text-[#171212] dark:text-white focus:outline-0 focus:ring-2 focus:ring-primary/20 border border-[#e5dcdd] dark:border-white/20 bg-white dark:bg-background-dark focus:border-primary min-h-[300px] placeholder:text-[#866569] dark:placeholder:text-gray-500 p-4 text-base font-normal leading-relaxed"
                            placeholder="Enter text to translate..."
                        />
                        <span className={`text-xs pt-2 text-right ${charCount > 5000 ? 'text-red-500' : 'text-[#866569] dark:text-gray-500'}`}>
                            {charCount} / 5000
                        </span>
                    </div>

                    <div className="flex flex-wrap justify-start gap-4">
                        <button
                            onClick={handlePaste}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-white/10 dark:hover:bg-white/20 transition-colors text-sm font-medium text-gray-700 dark:text-gray-200"
                        >
                            <ClipboardPaste className="w-5 h-5" />
                            <span>Paste Text</span>
                        </button>
                    </div>
                </div>

                {/* TARGET PANEL */}
                <div className="flex flex-col gap-4 bg-container-light dark:bg-container-dark dark:border dark:border-white/10 p-6 rounded-xl shadow-sm relative">
                    {/* Spinner */}
                    {isLoading && (
                        <div className="absolute top-6 right-6 z-10">
                            <div className="animate-spin h-6 w-6 border-4 border-primary border-t-transparent rounded-full opacity-75"></div>
                        </div>
                    )}

                    <div className="flex h-10 w-full items-center justify-center rounded-lg bg-background-light dark:bg-black/20 p-1">
                        {['English', 'Spanish', 'Chinese'].map((lang) => (
                            <button
                                key={`target-${lang}`}
                                onClick={() => setTargetLang(lang)}
                                className={`flex cursor-pointer h-full grow items-center justify-center overflow-hidden rounded-lg px-2 text-sm font-medium leading-normal transition-all ${targetLang === lang
                                    ? 'bg-white dark:bg-background-dark shadow-sm text-[#171212] dark:text-white'
                                    : 'text-[#866569] dark:text-gray-400'
                                    }`}
                            >
                                {lang}
                            </button>
                        ))}
                    </div>

                    <div className="flex flex-col flex-1">
                        <div
                            className={`form-input flex w-full min-w-0 flex-1 resize-y overflow-y-auto rounded-lg text-[#171212] dark:text-white border border-[#e5dcdd] dark:border-white/20 bg-background-light dark:bg-black/20 min-h-[300px] p-4 text-base font-normal leading-relaxed whitespace-pre-wrap ${isLoading ? 'opacity-50' : ''}`}
                        >
                            {error ? (
                                <span className="text-red-500">{error}</span>
                            ) : translatedText ? (
                                translatedText
                            ) : (
                                <span className="text-gray-400">Translation will appear here...</span>
                            )}
                        </div>
                    </div>

                    <div className="flex flex-wrap justify-start gap-4">
                        <button
                            onClick={handleCopy}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-white/10 dark:hover:bg-white/20 transition-colors text-sm font-medium text-gray-700 dark:text-gray-200"
                        >
                            <Copy className="w-5 h-5" />
                            <span>Copy Translation</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
