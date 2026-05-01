import { Construction } from 'lucide-react';

export default function Voice() {
    return (
        <div className="flex flex-col gap-8 max-w-5xl mx-auto h-[70vh] justify-center items-center text-center">
            <div className="p-12 bg-gray-50 dark:bg-white/5 rounded-2xl border-2 border-dashed border-gray-300 dark:border-white/10 flex flex-col items-center gap-6">
                <div className="p-4 bg-orange-100 dark:bg-orange-900/20 rounded-full">
                    <Construction className="w-12 h-12 text-orange-600 dark:text-orange-400" />
                </div>
                <div className="flex flex-col gap-2">
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                        Módulo desactivado
                    </h1>
                    <p className="text-gray-500 dark:text-gray-400 max-w-md">
                        El servicio de reconocimiento de voz se encuentra temporalmente desactivado por mantenimiento de hardware y optimización de recursos.
                    </p>
                </div>
                <button
                    className="px-6 py-2.5 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg hover:opacity-90 font-medium md:transition-opacity"
                    disabled
                >
                    Notificar cuando esté disponible
                </button>
            </div>
        </div>
    );
}
