import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function Login() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = btoa(`${username}:${password}`);

        try {
            // Create a specific axios instance or pass headers directly just to verify
            await axios.get('/api/admin/audit-logs?limit=1', {
                headers: { 'Authorization': `Basic ${token}` }
            });

            // If successful, store credential
            localStorage.setItem('auth_token', token);
            navigate('/admin/audit');
        } catch (err) {
            setError('Credenciales incorrectas');
        }
    };

    return (
        <div className="flex justify-center items-center h-screen bg-[#f0f2f5] font-sans">
            <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm text-center">
                <div className="flex justify-center mb-4">
                    <img src="/images/logo-boc.png" alt="BoC" className="h-[60px]" />
                </div>
                <h2 className="text-xl font-bold mb-6 text-[#333]">Acceso Auditoría</h2>
                <form onSubmit={handleLogin} className="text-left">
                    <div className="mb-4">
                        <label className="block mb-2 text-[#666]">Usuario</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full p-3 border border-[#ddd] rounded box-border text-base"
                            required
                        />
                    </div>
                    <div className="mb-4">
                        <label className="block mb-2 text-[#666]">Contraseña</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full p-3 border border-[#ddd] rounded box-border text-base"
                            required
                        />
                    </div>
                    {error && <p className="text-red-600 mb-4 text-sm">{error}</p>}
                    <button
                        type="submit"
                        className="w-full p-3 bg-[#B22222] text-white border-none rounded cursor-pointer text-base hover:bg-[#8B0000] transition-colors"
                    >
                        Ingresar
                    </button>
                </form>
                <a href="/" className="block mt-4 text-[#666] text-sm no-underline hover:underline">← Volver al inicio</a>
            </div>
        </div>
    );
}
