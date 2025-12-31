import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './views/Dashboard'
import Forecast from './views/Forecast'
import Optimization from './views/Optimization'
import Audit from './views/Audit'

function App() {
    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            {/* Navigation */}
            <nav className="bg-slate-800/50 backdrop-blur-xl border-b border-slate-700/50">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-16">
                        <div className="flex items-center">
                            <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
                                EcoGrid Audit
                            </h1>
                        </div>
                        <div className="flex space-x-4">
                            <NavLink
                                to="/"
                                className={({ isActive }) =>
                                    `px-4 py-2 rounded-lg transition-all duration-300 ${isActive
                                        ? 'bg-emerald-500/20 text-emerald-400 shadow-lg shadow-emerald-500/20'
                                        : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                                    }`
                                }
                            >
                                儀表板
                            </NavLink>
                            <NavLink
                                to="/forecast"
                                className={({ isActive }) =>
                                    `px-4 py-2 rounded-lg transition-all duration-300 ${isActive
                                        ? 'bg-emerald-500/20 text-emerald-400 shadow-lg shadow-emerald-500/20'
                                        : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                                    }`
                                }
                            >
                                預測
                            </NavLink>
                            <NavLink
                                to="/optimization"
                                className={({ isActive }) =>
                                    `px-4 py-2 rounded-lg transition-all duration-300 ${isActive
                                        ? 'bg-emerald-500/20 text-emerald-400 shadow-lg shadow-emerald-500/20'
                                        : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                                    }`
                                }
                            >
                                優化
                            </NavLink>
                            <NavLink
                                to="/audit"
                                className={({ isActive }) =>
                                    `px-4 py-2 rounded-lg transition-all duration-300 ${isActive
                                        ? 'bg-emerald-500/20 text-emerald-400 shadow-lg shadow-emerald-500/20'
                                        : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                                    }`
                                }
                            >
                                審計
                            </NavLink>
                        </div>
                    </div>
                </div>
            </nav>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/forecast" element={<Forecast />} />
                    <Route path="/optimization" element={<Optimization />} />
                    <Route path="/audit" element={<Audit />} />
                </Routes>
            </main>
        </div>
    )
}

export default App
