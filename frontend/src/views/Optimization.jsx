import React, { useState, useEffect } from 'react'
import { optimizationApi } from '../api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'

function Optimization() {
    const [hoursAhead, setHoursAhead] = useState(24)
    const [initialSoc, setInitialSoc] = useState(50)
    const [batteryCapacity, setBatteryCapacity] = useState(1000)
    const [maxContract, setMaxContract] = useState(5000)
    const [touMode, setTouMode] = useState('summer_weekday')
    const [result, setResult] = useState(null)
    const [schedule, setSchedule] = useState([])
    const [loading, setLoading] = useState(false)

    // TOU time periods definition
    const touPeriods = {
        summer_weekday: {
            peak: ['10:00-12:00', '13:00-17:00'],
            half_peak: ['07:30-10:00', '12:00-13:00', '17:00-22:30'],
            off_peak: ['22:30-07:30 (次日)']
        },
        summer_weekend: {
            half_peak: ['07:30-22:30'],
            off_peak: ['22:30-07:30 (次日)']
        },
        non_summer_weekday: {
            peak: ['10:00-12:00', '13:00-17:00'],
            half_peak: ['07:30-10:00', '12:00-13:00', '17:00-22:30'],
            off_peak: ['22:30-07:30 (次日)']
        },
        non_summer_weekend: {
            half_peak: ['07:30-22:30'],
            off_peak: ['22:30-07:30 (次日)']
        }
    }

    const handleOptimize = async () => {
        setLoading(true)
        try {
            const response = await optimizationApi.optimize({
                hours_ahead: hoursAhead,
                initial_soc: initialSoc,
                battery_capacity_kwh: batteryCapacity,
                max_contract_kw: maxContract
            })

            setResult(response)

            // Fetch schedule
            const scheduleResponse = await optimizationApi.getSchedule({
                hours: hoursAhead
            })
            setSchedule(scheduleResponse.schedule || [])
        } catch (error) {
            console.error('Optimization failed:', error)
            alert('優化失敗: ' + (error.response?.data?.detail || error.message))
        } finally {
            setLoading(false)
        }
    }

    // Calculate TOU tariffs
    const getTouTariff = (hour) => {
        const isSummer = true // Simplified, should be based on date
        const isWeekday = true

        if (isSummer && isWeekday) {
            if ((hour >= 10 && hour < 12) || (hour >= 13 && hour < 17)) return 'peak'
            if ((hour >= 7.5 && hour < 10) || (hour >= 12 && hour < 13) || (hour >= 17 && hour < 22.5)) return 'half_peak'
            return 'off_peak'
        }
        return 'off_peak'
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-gradient-to-r from-emerald-500 to-teal-500 rounded-2xl p-8 shadow-2xl">
                <h2 className="text-3xl font-bold text-white mb-2">智慧電力優化系統</h2>
                <p className="text-emerald-100">基於時間電價 (TOU) 的能源調度最佳化</p>
            </div>

            {/* TOU Information Card */}
            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                <h3 className="text-xl font-bold text-white mb-4 flex items-center">
                    <svg className="w-6 h-6 mr-2 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    時間電價 (TOU) 說明
                </h3>

                <div className="mb-4">
                    <label className="block text-slate-300 text-sm font-medium mb-2">選擇電價時段類型</label>
                    <select
                        value={touMode}
                        onChange={(e) => setTouMode(e.target.value)}
                        className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    >
                        <option value="summer_weekday">夏月尖峰 (週一至週五)</option>
                        <option value="summer_weekend">夏月離峰 (週六、日)</option>
                        <option value="non_summer_weekday">非夏月尖峰 (週一至週五)</option>
                        <option value="non_summer_weekend">非夏月離峰 (週六、日)</option>
                    </select>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Peak Period */}
                    {touPeriods[touMode].peak && (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                            <div className="flex items-center mb-2">
                                <div className="w-3 h-3 bg-red-500 rounded-full mr-2"></div>
                                <h4 className="text-red-400 font-semibold">尖峰時段</h4>
                            </div>
                            <p className="text-slate-300 text-sm mb-2">電價: 最高</p>
                            {touPeriods[touMode].peak.map((period, idx) => (
                                <p key={idx} className="text-slate-400 text-xs">{period}</p>
                            ))}
                        </div>
                    )}

                    {/* Half-Peak Period */}
                    {touPeriods[touMode].half_peak && (
                        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
                            <div className="flex items-center mb-2">
                                <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
                                <h4 className="text-yellow-400 font-semibold">半尖峰時段</h4>
                            </div>
                            <p className="text-slate-300 text-sm mb-2">電價: 中等</p>
                            {touPeriods[touMode].half_peak.map((period, idx) => (
                                <p key={idx} className="text-slate-400 text-xs">{period}</p>
                            ))}
                        </div>
                    )}

                    {/* Off-Peak Period */}
                    {touPeriods[touMode].off_peak && (
                        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
                            <div className="flex items-center mb-2">
                                <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
                                <h4 className="text-green-400 font-semibold">離峰時段</h4>
                            </div>
                            <p className="text-slate-300 text-sm mb-2">電價: 最低</p>
                            {touPeriods[touMode].off_peak.map((period, idx) => (
                                <p key={idx} className="text-slate-400 text-xs">{period}</p>
                            ))}
                        </div>
                    )}
                </div>

                <div className="mt-4 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                    <p className="text-emerald-400 text-sm">
                        💡 <strong>優化策略:</strong> 系統會在離峰時段充電，在尖峰時段放電，以降低整體電費支出
                    </p>
                </div>
            </div>

            {/* Optimization Controls */}
            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                <h3 className="text-xl font-bold text-white mb-6">優化參數設定</h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    {/* Hours Ahead */}
                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">
                            優化時長: {hoursAhead} 小時
                        </label>
                        <input
                            type="range"
                            min="1"
                            max="168"
                            value={hoursAhead}
                            onChange={(e) => setHoursAhead(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                        />
                        <div className="flex justify-between text-xs text-slate-400 mt-1">
                            <span>1h</span>
                            <span>24h</span>
                            <span>72h</span>
                            <span>168h</span>
                        </div>
                    </div>

                    {/* Initial SOC */}
                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">
                            電池初始電量: {initialSoc}%
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={initialSoc}
                            onChange={(e) => setInitialSoc(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                        />
                        <div className="flex justify-between text-xs text-slate-400 mt-1">
                            <span>0%</span>
                            <span>50%</span>
                            <span>100%</span>
                        </div>
                    </div>

                    {/* Battery Capacity */}
                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">
                            電池容量: {batteryCapacity} kWh
                        </label>
                        <input
                            type="range"
                            min="100"
                            max="10000"
                            step="100"
                            value={batteryCapacity}
                            onChange={(e) => setBatteryCapacity(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                        />
                        <div className="flex justify-between text-xs text-slate-400 mt-1">
                            <span>100</span>
                            <span>5000</span>
                            <span>10000</span>
                        </div>
                    </div>

                    {/* Max Contract */}
                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">
                            契約容量: {maxContract} kW
                        </label>
                        <input
                            type="range"
                            min="1000"
                            max="50000"
                            step="100"
                            value={maxContract}
                            onChange={(e) => setMaxContract(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                        />
                        <div className="flex justify-between text-xs text-slate-400 mt-1">
                            <span>1000</span>
                            <span>25000</span>
                            <span>50000</span>
                        </div>
                    </div>
                </div>

                {/* Optimize Button */}
                <button
                    onClick={handleOptimize}
                    disabled={loading}
                    className="w-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white px-6 py-4 rounded-lg font-semibold hover:shadow-lg hover:shadow-emerald-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
                >
                    {loading ? (
                        <span className="flex items-center justify-center">
                            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            優化計算中...
                        </span>
                    ) : (
                        '開始優化'
                    )}
                </button>
            </div>

            {/* Optimization Results */}
            {result && (
                <>
                    {/* Summary Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 backdrop-blur-xl rounded-2xl p-6 border border-emerald-500/30 shadow-xl">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-slate-300 text-sm font-medium">總成本</h3>
                                <div className="w-10 h-10 bg-emerald-500/30 rounded-lg flex items-center justify-center">
                                    <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                </div>
                            </div>
                            <p className="text-3xl font-bold text-white mb-2">
                                ${result.total_cost?.toLocaleString() || 0}
                            </p>
                            <p className="text-sm text-emerald-300">
                                節省 ${result.cost_savings?.toLocaleString() || 0}
                            </p>
                        </div>

                        <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 backdrop-blur-xl rounded-2xl p-6 border border-blue-500/30 shadow-xl">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-slate-300 text-sm font-medium">契約容量費</h3>
                                <div className="w-10 h-10 bg-blue-500/30 rounded-lg flex items-center justify-center">
                                    <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                    </svg>
                                </div>
                            </div>
                            <p className="text-3xl font-bold text-white mb-2">
                                ${result.demand_charge?.toLocaleString() || 0}
                            </p>
                            <p className="text-sm text-slate-400">基本電費</p>
                        </div>

                        <div className="bg-gradient-to-br from-yellow-500/20 to-orange-500/20 backdrop-blur-xl rounded-2xl p-6 border border-yellow-500/30 shadow-xl">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-slate-300 text-sm font-medium">能源費</h3>
                                <div className="w-10 h-10 bg-yellow-500/30 rounded-lg flex items-center justify-center">
                                    <svg className="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                </div>
                            </div>
                            <p className="text-3xl font-bold text-white mb-2">
                                ${result.energy_charge?.toLocaleString() || 0}
                            </p>
                            <p className="text-sm text-slate-400">用電度數費</p>
                        </div>

                        <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 backdrop-blur-xl rounded-2xl p-6 border border-purple-500/30 shadow-xl">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-slate-300 text-sm font-medium">峰值功率</h3>
                                <div className="w-10 h-10 bg-purple-500/30 rounded-lg flex items-center justify-center">
                                    <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                                    </svg>
                                </div>
                            </div>
                            <p className="text-3xl font-bold text-white mb-2">
                                {result.peak_demand?.toLocaleString() || 0} kW
                            </p>
                            <p className="text-sm text-slate-400">最大需量</p>
                        </div>
                    </div>

                    {/* Schedule Chart */}
                    {schedule.length > 0 && (
                        <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                            <h3 className="text-xl font-bold text-white mb-6">優化排程 - 電池充放電計畫</h3>
                            <ResponsiveContainer width="100%" height={400}>
                                <LineChart data={schedule}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                    <XAxis
                                        dataKey="hour"
                                        stroke="#94a3b8"
                                        label={{ value: '時間 (小時)', position: 'insideBottom', offset: -5, fill: '#94a3b8' }}
                                    />
                                    <YAxis
                                        stroke="#94a3b8"
                                        label={{ value: '電力 (kW)', angle: -90, position: 'insideLeft', fill: '#94a3b8' }}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: '#1e293b',
                                            border: '1px solid #334155',
                                            borderRadius: '8px',
                                            color: '#fff'
                                        }}
                                    />
                                    <Legend />
                                    <Line type="monotone" dataKey="grid_power" stroke="#3b82f6" strokeWidth={2} name="電網功率" />
                                    <Line type="monotone" dataKey="battery_power" stroke="#10b981" strokeWidth={2} name="電池功率" />
                                    <Line type="monotone" dataKey="soc" stroke="#f59e0b" strokeWidth={2} name="SOC (%)" />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {/* Cost Breakdown Chart */}
                    {schedule.length > 0 && (
                        <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                            <h3 className="text-xl font-bold text-white mb-6">TOU 電價分布</h3>
                            <ResponsiveContainer width="100%" height={300}>
                                <BarChart data={schedule}>
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
                                    <Bar dataKey="cost" fill="#10b981" name="時段成本 ($)" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}

export default Optimization
