import React, { useState, useEffect } from 'react'
import { dashboardApi } from '../api'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function Dashboard() {
    const [summary, setSummary] = useState(null)
    const [chartData, setChartData] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 60000) // Refresh every minute
        return () => clearInterval(interval)
    }, [])

    const fetchData = async () => {
        try {
            const [summaryRes, chartRes] = await Promise.all([
                dashboardApi.getSummary(),
                dashboardApi.getChartData()
            ])
            setSummary(summaryRes)
            setChartData(chartRes.data || [])
            setLoading(false)
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error)
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-500 border-t-transparent"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-gradient-to-r from-emerald-500 to-teal-500 rounded-2xl p-8 shadow-2xl">
                <h2 className="text-3xl font-bold text-white mb-2">即時電力監控儀表板</h2>
                <p className="text-emerald-100">實時監控用電狀況與綠能發電數據</p>
            </div>

            {/* Summary Cards */}
            {summary && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl hover:shadow-emerald-500/10 transition-all duration-300">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-slate-300 text-sm font-medium">當前負載</h3>
                            <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
                                <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                </svg>
                            </div>
                        </div>
                        <p className="text-3xl font-bold text-white mb-2">
                            {summary.current_load?.toLocaleString() || 0} <span className="text-xl text-slate-400">kW</span>
                        </p>
                        <p className="text-sm text-slate-400">即時用電功率</p>
                    </div>

                    <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl hover:shadow-yellow-500/10 transition-all duration-300">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-slate-300 text-sm font-medium">太陽能發電</h3>
                            <div className="w-10 h-10 bg-yellow-500/20 rounded-lg flex items-center justify-center">
                                <svg className="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                                </svg>
                            </div>
                        </div>
                        <p className="text-3xl font-bold text-white mb-2">
                            {summary.solar_generation?.toLocaleString() || 0} <span className="text-xl text-slate-400">kW</span>
                        </p>
                        <p className="text-sm text-slate-400">當前光電發電量</p>
                    </div>

                    <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl hover:shadow-cyan-500/10 transition-all duration-300">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-slate-300 text-sm font-medium">風力發電</h3>
                            <div className="w-10 h-10 bg-cyan-500/20 rounded-lg flex items-center justify-center">
                                <svg className="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                        </div>
                        <p className="text-3xl font-bold text-white mb-2">
                            {summary.wind_generation?.toLocaleString() || 0} <span className="text-xl text-slate-400">kW</span>
                        </p>
                        <p className="text-sm text-slate-400">當前風能發電量</p>
                    </div>

                    <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl hover:shadow-emerald-500/10 transition-all duration-300">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-slate-300 text-sm font-medium">綠能使用率</h3>
                            <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
                                <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                        </div>
                        <p className="text-3xl font-bold text-white mb-2">
                            {summary.renewable_ratio?.toFixed(1) || 0}<span className="text-xl text-slate-400">%</span>
                        </p>
                        <p className="text-sm text-slate-400">再生能源占比</p>
                    </div>
                </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Load Chart */}
                <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                    <h3 className="text-xl font-bold text-white mb-6">24小時負載趨勢</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="hour" stroke="#94a3b8" />
                            <YAxis stroke="#94a3b8" />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '8px',
                                    color: '#fff'
                                }}
                            />
                            <Legend />
                            <Line type="monotone" dataKey="load" stroke="#3b82f6" strokeWidth={2} name="負載 (kW)" />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {/* Generation Chart */}
                <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                    <h3 className="text-xl font-bold text-white mb-6">綠能發電分布</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="hour" stroke="#94a3b8" />
                            <YAxis stroke="#94a3b8" />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '8px',
                                    color: '#fff'
                                }}
                            />
                            <Legend />
                            <Bar dataKey="solar" fill="#fbbf24" name="太陽能 (kW)" />
                            <Bar dataKey="wind" fill="#06b6d4" name="風力 (kW)" />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    )
}

export default Dashboard
