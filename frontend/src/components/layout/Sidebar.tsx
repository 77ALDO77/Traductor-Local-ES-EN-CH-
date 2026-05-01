import { NavLink } from 'react-router-dom';
import { Languages, FileText, Mic, ShieldCheck } from 'lucide-react';

export default function Sidebar() {
    const navItems = [
        { name: 'Text Translation', path: '/', icon: Languages },
        { name: 'Document Translator', path: '/documents', icon: FileText },
        { name: 'Voice Translation', path: '/voice', icon: Mic },
        { name: 'Audit Access', path: '/admin/audit', icon: ShieldCheck },
    ];

    return (
        <aside className="w-64 flex-shrink-0 bg-container-light dark:bg-background-dark dark:border-r dark:border-white/10 shadow-sm h-screen sticky top-0">
            <div className="flex h-full flex-col p-4">
                <div className="flex flex-col gap-8">
                    {/* Logo */}
                    <div className="flex items-center gap-3 px-3">
                        <img src="/static/images/icon-boc-white.png" className="bg-primary rounded-lg p-1.5 h-10 w-10" alt="BoC Logo" />
                        <div className="flex flex-col">
                            <h1 className="text-[#171212] dark:text-white text-lg font-bold leading-normal">
                                BoC Translator
                            </h1>
                            <p className="text-[#866569] dark:text-gray-400 text-sm font-normal leading-normal">
                                Bank of China
                            </p>
                        </div>
                    </div>

                    {/* Navigation */}
                    <nav className="flex flex-col gap-2">
                        {navItems.map((item) => (
                            <NavLink
                                key={item.path}
                                to={item.path}
                                className={({ isActive }) =>
                                    `flex items - center gap - 3 px - 3 py - 2.5 rounded - lg transition - colors ${isActive
                                        ? 'bg-primary/10 dark:bg-primary/20 text-primary'
                                        : 'hover:bg-black/5 dark:hover:bg-white/5 text-[#171212] dark:text-gray-300'
                                    } `
                                }
                            >
                                <item.icon className={`w - 5 h - 5 ${
                                    // Logic inside className function above handles color via text-primary or text-...
                                    ''
                                    } `}
                                />
                                <p className="text-sm font-medium leading-normal">{item.name}</p>
                            </NavLink>
                        ))}

                        <div className="h-px bg-gray-200 dark:bg-white/10 my-2 mx-3"></div>

                        {/* Optional Logout if needed, or just link to login */}
                    </nav>
                </div>
            </div>
        </aside>
    );
}
