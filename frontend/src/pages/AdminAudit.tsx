import { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Settings, Check, AlertTriangle, RotateCw } from 'lucide-react';

interface AuditLog {
    id: number;
    timestamp: string;
    user: string;
    action: string;
    details: string;
    ip_address: string;
}

interface LLMModel {
    name: string;
    created?: number;
    owned_by?: string;
}

export default function AdminAudit() {
    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [models, setModels] = useState<LLMModel[]>([]);
    const [currentModel, setCurrentModel] = useState('');
    const [selectedModel, setSelectedModel] = useState('');
    const [modelLoading, setModelLoading] = useState(false);
    const [modelError, setModelError] = useState('');
    const [modelSuccess, setModelSuccess] = useState('');
    const navigate = useNavigate();

    const getAuthHeaders = () => {
        const token = localStorage.getItem('auth_token');
        if (!token) {
            navigate('/login');
            return {};
        }
        return { Authorization: `Basic ${token}` };
    };

    const fetchModels = async () => {
        try {
            const response = await axios.get('/api/admin/models', {
                headers: getAuthHeaders()
            });
            setModels(response.data.models || []);
            setCurrentModel(response.data.current_model || '');
            setSelectedModel(response.data.current_model || '');
        } catch (error: any) {
            if (error.response?.status === 401) {
                localStorage.removeItem('auth_token');
                navigate('/login');
            }
        }
    };

    const handleSwitchModel = async () => {
        if (!selectedModel || selectedModel === currentModel) return;
        setModelLoading(true);
        setModelError('');
        setModelSuccess('');
        try {
            await axios.post('/api/admin/models/select',
                { model: selectedModel },
                { headers: getAuthHeaders() }
            );
            setCurrentModel(selectedModel);
            setModelSuccess(`Modelo cambiado a "${selectedModel}" correctamente.`);
            setTimeout(() => setModelSuccess(''), 4000);
        } catch (error: any) {
            setModelError(error.response?.data?.detail || 'Error al cambiar modelo');
        } finally {
            setModelLoading(false);
        }
    };

    useEffect(() => {
        const fetchData = async () => {
            const token = localStorage.getItem('auth_token');
            if (!token) {
                navigate('/login');
                return;
            }

            try {
                const [logsResp, modelsResp] = await Promise.all([
                    axios.get('/api/admin/audit-logs', { headers: { Authorization: `Basic ${token}` } }),
                    axios.get('/api/admin/models', { headers: { Authorization: `Basic ${token}` } })
                ]);
                setLogs(logsResp.data);
                setModels(modelsResp.data.models || []);
                setCurrentModel(modelsResp.data.current_model || '');
                setSelectedModel(modelsResp.data.current_model || '');
            } catch (error: any) {
                if (error.response?.status === 401) {
                    localStorage.removeItem('auth_token');
                    navigate('/login');
                }
            }
        };

        fetchData();
    }, [navigate]);

    const handleLogout = () => {
        localStorage.removeItem('auth_token');
        navigate('/login');
    };

    return (
        <div className="flex flex-col gap-6 max-w-6xl mx-auto">
            <div className="flex justify-between items-center">
                <div className="flex flex-col gap-2">
                    <h1 className="text-gray-900 dark:text-white text-3xl font-bold">Admin Panel</h1>
                    <p className="text-gray-600 dark:text-gray-400 text-base">
                        Model management and audit logs.
                    </p>
                </div>
                <button
                    onClick={handleLogout}
                    className="px-4 py-2 text-sm font-medium text-red-600 bg-red-100 rounded-lg hover:bg-red-200 border border-red-200"
                >
                    Logout
                </button>
            </div>

            {/* Model Selector */}
            <div className="bg-white dark:bg-container-dark rounded-xl shadow-sm border border-gray-200 dark:border-white/10 p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Settings className="w-5 h-5 text-gray-500" />
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Translation Model</h2>
                </div>

                <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-end">
                    <div className="flex flex-col gap-1.5 flex-1">
                        <label className="text-sm font-medium text-gray-600 dark:text-gray-400">
                            Active Model
                        </label>
                        <select
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                            className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                        >
                            {models.length === 0 && (
                                <option value="">No models found</option>
                            )}
                            {models.map((m) => (
                                <option key={m.name} value={m.name}>
                                    {m.name}
                                </option>
                            ))}
                        </select>
                        {currentModel && (
                            <div className="flex items-center gap-1.5 mt-1">
                                {selectedModel === currentModel ? (
                                    <span className="flex items-center gap-1 text-xs text-green-600">
                                        <Check className="w-3.5 h-3.5" /> Active
                                    </span>
                                ) : (
                                    <span className="flex items-center gap-1 text-xs text-amber-600">
                                        <AlertTriangle className="w-3.5 h-3.5" /> Not applied
                                    </span>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="flex gap-2">
                        <button
                            onClick={fetchModels}
                            disabled={modelLoading}
                            className="px-3 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 border border-gray-200 flex items-center gap-1.5"
                            title="Refresh models"
                        >
                            <RotateCw className="w-4 h-4" />
                        </button>
                        <button
                            onClick={handleSwitchModel}
                            disabled={modelLoading || selectedModel === currentModel}
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                        >
                            {modelLoading ? 'Switching...' : 'Apply'}
                        </button>
                    </div>
                </div>

                {modelError && (
                    <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
                        {modelError}
                    </div>
                )}
                {modelSuccess && (
                    <div className="mt-3 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400">
                        {modelSuccess}
                    </div>
                )}
            </div>

            {/* Audit Logs Table */}
            <div className="bg-white dark:bg-container-dark rounded-xl shadow-sm border border-gray-200 dark:border-white/10 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200 dark:border-white/10">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Audit Logs</h2>
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-white/10">
                        <thead className="bg-gray-50 dark:bg-white/5">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-white/10 text-sm">
                            {logs.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-6 py-8 text-center text-gray-400">
                                        No audit logs found.
                                    </td>
                                </tr>
                            ) : (
                                logs.map((log) => (
                                    <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-white/5">
                                        <td className="px-6 py-4 whitespace-nowrap text-gray-900 dark:text-white">
                                            {new Date(log.timestamp).toLocaleString()}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-gray-400">{log.user}</td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className="px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
                                                {log.action}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-gray-500 dark:text-gray-400 max-w-xs truncate" title={log.details}>
                                            {log.details}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-gray-400">{log.ip_address}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
