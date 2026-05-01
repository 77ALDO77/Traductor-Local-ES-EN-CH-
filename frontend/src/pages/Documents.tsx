import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Upload, FileText, Trash2, Download, X, Play, RefreshCw, FileType, AlertCircle } from 'lucide-react';

interface Document {
    filename: string;
    original_name: string;
    source_lang: string;
    target_lang: string;
    status: string;
    upload_time: string;
    file_size?: number;
    total_chunks?: number;
    preview_text?: string;
    progress?: number;
    message?: string;
    translated_filename?: string;
    download_url?: string;
    processing_time_ms?: number;
}

export default function Documents() {
    // Estado Global
    const [documents, setDocuments] = useState<Document[]>([]);

    // Estado del "Documento Activo" (El que se está trabajando ahora mismo)
    const [activeDoc, setActiveDoc] = useState<Document | null>(null);
    const [isTranslating, setIsTranslating] = useState(false);

    // Configuración
    const [sourceLang, setSourceLang] = useState('Spanish');
    const [targetLang, setTargetLang] = useState('Chinese');
    const [uploading, setUploading] = useState(false);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const [translationLogs, setTranslationLogs] = useState<string[]>([]);

    useEffect(() => {
        fetchDocuments();
        // Polling para actualizar historial (menos agresivo)
        const interval = setInterval(fetchDocuments, 10000);
        return () => clearInterval(interval);
    }, []);

    // Auto-scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [translationLogs]);

    const fetchDocuments = async () => {
        try {
            const response = await axios.get('/api/documents/list');
            // Ordenar por fecha (más reciente primero)
            const sorted = response.data.sort((a: Document, b: Document) =>
                new Date(b.upload_time).getTime() - new Date(a.upload_time).getTime()
            );
            setDocuments(sorted);
        } catch (error) {
            console.error("Error fetching documents", error);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            handleUpload(e.target.files[0]);
        }
    };

    const handleUpload = async (file: File) => {
        if (!file) return;

        // Validaciones básicas (replicando documents.js)
        const validExts = ['pdf', 'docx', 'xlsx', 'doc', 'xls'];
        const ext = file.name.split('.').pop()?.toLowerCase() || '';
        if (!validExts.includes(ext)) {
            alert('Formato no soportado. Usa PDF, DOCX o XLSX.');
            return;
        }

        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post('/api/documents/upload', formData);

            // Construir el objeto documento basado en la respuesta
            const newDoc: Document = {
                filename: response.data.filename,
                original_name: file.name,
                source_lang: sourceLang, // Valores por defecto iniciales
                target_lang: targetLang,
                status: 'uploaded',
                upload_time: new Date().toISOString(),
                file_size: response.data.file_size,
                total_chunks: response.data.total_chunks,
                preview_text: response.data.preview_text,
                progress: 0
            };

            // Establecer como ACTIVO inmediatamente
            setActiveDoc(newDoc);
            setTranslationLogs([]); // Limpiar logs anteriores
            await fetchDocuments(); // Actualizar tabla inferior

        } catch (error: any) {
            console.error("Upload failed", error);
            alert(error.response?.data?.detail || 'Error al subir archivo');
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleTranslate = async () => {
        if (!activeDoc || isTranslating) return;

        if (sourceLang === targetLang) {
            alert("El idioma de origen y destino deben ser diferentes");
            return;
        }

        setIsTranslating(true);
        setTranslationLogs(prev => [...prev, `[INFO] Iniciando traducción: ${sourceLang} -> ${targetLang}`]);

        // Actualizar UI local
        setActiveDoc(prev => prev ? ({ ...prev, status: 'processing', progress: 0, message: 'Iniciando...' }) : null);

        const formData = new FormData();
        formData.append('filename', activeDoc.filename);
        formData.append('source_language', sourceLang);
        formData.append('target_language', targetLang);

        try {
            const response = await fetch('/api/documents/translate/stream', {
                method: 'POST',
                body: formData,
            });

            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));

                            // Actualizar estado activo
                            setActiveDoc(prev => {
                                if (!prev) return null;
                                return {
                                    ...prev,
                                    status: data.status,
                                    progress: data.progress_percent,
                                    message: data.message,
                                    translated_filename: data.translated_filename,
                                    download_url: data.download_url,
                                    processing_time_ms: data.processing_time_ms
                                };
                            });

                            // Agregar log si el mensaje cambió o es importante
                            if (data.message) {
                                setTranslationLogs(prev => {
                                    // Evitar duplicados consecutivos
                                    if (prev[prev.length - 1]?.includes(data.message)) return prev;
                                    return [...prev, `[${new Date().toLocaleTimeString()}] ${data.message}`];
                                });
                            }

                        } catch (e) {
                            console.warn("JSON Parse Error in stream", e);
                        }
                    }
                }
            }

            setTranslationLogs(prev => [...prev, `[SUCCESS] Proceso finalizado.`]);
            fetchDocuments(); // Refrescar historial

        } catch (error) {
            console.error("Translation stream error", error);
            setActiveDoc(prev => prev ? ({ ...prev, status: 'failed', message: 'Error de conexión' }) : null);
            setTranslationLogs(prev => [...prev, `[ERROR] Falló la conexión con el servidor.`]);
        } finally {
            setIsTranslating(false);
        }
    };

    const handleDelete = async (filename: string) => {
        if (!confirm('¿Eliminar archivo y sus traducciones?')) return;
        try {
            await axios.delete(`/api/documents/cleanup/${filename}`);
            if (activeDoc?.filename === filename) {
                setActiveDoc(null);
                setTranslationLogs([]);
            }
            fetchDocuments();
        } catch (err) {
            console.error(err);
        }
    };

    const handleSelectFromHistory = (doc: Document) => {
        // Cargar un documento del historial al área de trabajo
        setActiveDoc(doc);
        window.scrollTo({ top: 0, behavior: 'smooth' });
        setTranslationLogs([`[INFO] Documento cargado desde el historial.`]);
    };

    // Helper para formatear bytes
    const formatBytes = (bytes?: number) => {
        if (!bytes) return '0 B';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    return (
        <div className="flex flex-col gap-8 max-w-6xl mx-auto p-4">

            {/* Header */}
            <div className="flex flex-col gap-1">
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Traductor de Documentos</h1>
                <p className="text-gray-500 dark:text-gray-400">
                    Sube archivos PDF, DOCX o XLSX manteniendo el formato original.
                </p>
            </div>

            {/* --- ZONA DE TRABAJO (WORKSPACE) --- */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Panel Izquierdo: Configuración y Subida */}
                <div className="lg:col-span-1 flex flex-col gap-4">
                    {/* Tarjeta de Subida */}
                    <div className={`p-6 rounded-xl border-2 border-dashed transition-all cursor-pointer bg-white dark:bg-container-dark
                        ${uploading ? 'opacity-50 pointer-events-none' : 'hover:border-primary border-gray-300 dark:border-white/10'}`}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            type="file"
                            ref={fileInputRef}
                            onChange={handleFileChange}
                            accept=".docx,.xlsx,.pdf,.pptx"
                            className="hidden"
                        />
                        <div className="flex flex-col items-center text-center gap-3">
                            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                                <Upload className="w-6 h-6" />
                            </div>
                            <div>
                                <h3 className="font-semibold text-gray-900 dark:text-white">Subir Documento</h3>
                                <p className="text-xs text-gray-500 mt-1">PDF, DOCX, XLSX (Máx 20MB)</p>
                            </div>
                            <button disabled={uploading} className="text-sm text-primary font-medium hover:underline">
                                {uploading ? 'Subiendo...' : 'Explorar archivos'}
                            </button>
                        </div>
                    </div>

                    {/* Controles de Idioma */}
                    <div className="bg-white dark:bg-container-dark p-5 rounded-xl shadow-sm border border-gray-200 dark:border-white/10">
                        <h3 className="font-medium text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                            <RefreshCw className="w-4 h-4 text-gray-400" /> Configuración
                        </h3>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-gray-500 uppercase mb-1">Origen</label>
                                <select
                                    value={sourceLang}
                                    onChange={(e) => setSourceLang(e.target.value)}
                                    disabled={isTranslating}
                                    className="w-full rounded-lg border-gray-300 dark:border-white/10 dark:bg-black/20 dark:text-white p-2.5 text-sm"
                                >
                                    <option value="Spanish">Español</option>
                                    <option value="English">Inglés</option>
                                    <option value="Chinese">Chino (Simplificado)</option>
                                </select>
                            </div>

                            <div className="flex justify-center">
                                <span className="text-gray-400">↓</span>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-gray-500 uppercase mb-1">Destino</label>
                                <select
                                    value={targetLang}
                                    onChange={(e) => setTargetLang(e.target.value)}
                                    disabled={isTranslating}
                                    className="w-full rounded-lg border-gray-300 dark:border-white/10 dark:bg-black/20 dark:text-white p-2.5 text-sm"
                                >
                                    <option value="Chinese">Chino (Simplificado)</option>
                                    <option value="English">Inglés</option>
                                    <option value="Spanish">Español</option>
                                </select>
                            </div>

                            {activeDoc && activeDoc.status !== 'processing' && (
                                <button
                                    onClick={handleTranslate}
                                    disabled={isTranslating || activeDoc.status === 'processing'}
                                    className="w-full py-3 bg-primary hover:bg-red-800 text-white rounded-lg font-medium shadow-sm transition-all flex items-center justify-center gap-2 mt-2"
                                >
                                    {isTranslating ? 'Procesando...' : (
                                        <>
                                            <Play className="w-4 h-4" /> Traducir Ahora
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Panel Central/Derecho: Documento Activo */}
                <div className="lg:col-span-2 space-y-4">
                    {!activeDoc ? (
                        <div className="h-full min-h-[400px] flex flex-col items-center justify-center bg-gray-50 dark:bg-white/5 rounded-xl border-2 border-dashed border-gray-200 dark:border-white/10 text-gray-400">
                            <FileText className="w-16 h-16 mb-4 opacity-50" />
                            <p>Selecciona o sube un archivo para comenzar</p>
                        </div>
                    ) : (
                        <>
                            {/* Tarjeta de Estado del Documento */}
                            <div className="bg-white dark:bg-container-dark rounded-xl shadow-sm border border-gray-200 dark:border-white/10 overflow-hidden">
                                <div className="p-5 border-b border-gray-100 dark:border-white/5 flex justify-between items-start">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 bg-blue-50 dark:bg-blue-900/20 rounded-lg flex items-center justify-center text-blue-600 dark:text-blue-400">
                                            <FileType className="w-6 h-6" />
                                        </div>
                                        <div>
                                            <h2 className="font-bold text-gray-900 dark:text-white text-lg">{activeDoc.original_name}</h2>
                                            <div className="flex items-center gap-3 text-sm text-gray-500">
                                                <span>{formatBytes(activeDoc.file_size)}</span>
                                                <span>•</span>
                                                <span>{activeDoc.total_chunks || 0} bloques detectados</span>
                                            </div>
                                        </div>
                                    </div>
                                    <button onClick={() => setActiveDoc(null)} className="text-gray-400 hover:text-gray-600">
                                        <X className="w-5 h-5" />
                                    </button>
                                </div>

                                {/* Barra de Progreso Grande */}
                                {(activeDoc.status === 'processing' || activeDoc.status === 'completed') && (
                                    <div className="p-6 bg-gray-50 dark:bg-white/5">
                                        <div className="flex justify-between text-sm font-medium mb-2">
                                            <span className="text-gray-700 dark:text-gray-300">
                                                {activeDoc.status === 'completed' ? 'Traducción Completada' : activeDoc.message}
                                            </span>
                                            <span className="text-primary">{Math.round(activeDoc.progress || 0)}%</span>
                                        </div>
                                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 overflow-hidden">
                                            <div
                                                className="bg-primary h-full transition-all duration-500 ease-out flex items-center justify-center"
                                                style={{ width: `${activeDoc.progress || 0}%` }}
                                            >
                                                <div className="w-full h-full bg-[linear-gradient(45deg,rgba(255,255,255,0.2)_25%,transparent_25%,transparent_50%,rgba(255,255,255,0.2)_50%,rgba(255,255,255,0.2)_75%,transparent_75%,transparent)] bg-[length:1rem_1rem] animate-[progress-bar-stripes_1s_linear_infinite]" />
                                            </div>
                                        </div>

                                        {/* Botón de Descarga Gigante si terminó */}
                                        {activeDoc.status === 'completed' && activeDoc.download_url && (
                                            <div className="mt-6 flex justify-center">
                                                <a
                                                    href={activeDoc.download_url}
                                                    download
                                                    className="flex items-center gap-2 px-8 py-3 bg-green-600 hover:bg-green-700 text-white rounded-full font-bold shadow-lg transform transition hover:scale-105"
                                                >
                                                    <Download className="w-5 h-5" />
                                                    Descargar Documento Traducido
                                                </a>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Vista Previa (Simulada como en documents.js) */}
                                <div className="p-5">
                                    <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Vista Previa del Contenido</h4>
                                    <div className="bg-gray-50 dark:bg-black/20 p-4 rounded-lg border border-gray-200 dark:border-white/5 max-h-48 overflow-y-auto font-mono text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                                        {activeDoc.preview_text || "No hay vista previa disponible."}
                                    </div>
                                </div>
                            </div>

                            {/* Consola de Logs (Estilo 'Matrix' o Terminal) */}
                            {translationLogs.length > 0 && (
                                <div className="bg-black text-green-400 p-4 rounded-xl font-mono text-xs h-40 overflow-y-auto border border-gray-800 shadow-inner">
                                    {translationLogs.map((log, i) => (
                                        <div key={i} className="mb-1">{log}</div>
                                    ))}
                                    <div ref={logsEndRef} />
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* --- HISTORIAL (TABLA) --- */}
            <div className="mt-8">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">Historial de Archivos</h3>
                <div className="bg-white dark:bg-container-dark rounded-xl shadow-sm border border-gray-200 dark:border-white/10 overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200 dark:divide-white/10">
                            <thead className="bg-gray-50 dark:bg-white/5">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Archivo</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fecha</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Acciones</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-white/10">
                                {documents.map((doc) => (
                                    <tr key={doc.filename} className={`hover:bg-gray-50 dark:hover:bg-white/5 transition-colors ${activeDoc?.filename === doc.filename ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''}`}>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="flex items-center cursor-pointer" onClick={() => handleSelectFromHistory(doc)}>
                                                <FileText className="h-5 w-5 text-gray-400 mr-3" />
                                                <span className="text-sm font-medium text-gray-900 dark:text-white">{doc.original_name}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            {doc.status === 'completed' ? (
                                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                                    Completado
                                                </span>
                                            ) : doc.status === 'processing' ? (
                                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                                    Procesando {Math.round(doc.progress || 0)}%
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                                    Subido
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {new Date(doc.upload_time).toLocaleDateString()}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            <div className="flex justify-end gap-2">
                                                {/* Botón Cargar en Workspace */}
                                                <button onClick={() => handleSelectFromHistory(doc)} className="text-gray-400 hover:text-primary" title="Ver Detalles">
                                                    <AlertCircle className="w-5 h-5" />
                                                </button>

                                                {/* Botón Descargar (Mini) */}
                                                {doc.status === 'completed' && (
                                                    <button
                                                        onClick={() => window.open(`/api/documents/download/${doc.filename.replace(/\.[^/.]+$/, "")}_translated_${doc.upload_time.split('T')[0]}.docx`, '_blank')}
                                                        // Nota: La URL de descarga real depende de cómo la guardó el backend, usamos la del estado si existe
                                                        // Si no, intentamos construirla o usar la función del activeDoc
                                                        className="text-gray-400 hover:text-green-600"
                                                    >
                                                        <Download className="w-5 h-5" />
                                                    </button>
                                                )}

                                                <button onClick={() => handleDelete(doc.filename)} className="text-gray-400 hover:text-red-600">
                                                    <Trash2 className="w-5 h-5" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}