import React, { useState, useEffect } from 'react'
import { forecastApi } from '../api'

function Forecast() {
    const [selectedModel, setSelectedModel] = useState('xgboost')
    const [hours, setHours] = useState(24)
    const [prediction, setPrediction] = useState(null)
    const [status, setStatus] = useState(null)
    const [loading, setLoading] = useState(false)
    const [training, setTraining] = useState(false)

    useEffect(() => {
        fetchStatus()
    }, [])

    const fetchStatus = async () => {
        try {
            const res = await forecastApi.getStatus()
            setStatus(res)
        } catch (error) {
            console.error('Failed to fetch forecast status:', error)
        }
    }

    const handlePredict = async () => {
        setLoading(true)
        try {
            const res = await forecastApi.predict({
                model_type: selectedModel,
                hours_ahead: hours
            })
            setPrediction(res)
        } catch (error) {
            console.error('Prediction failed:', error)
            alert('預測失敗: ' + (error.response?.data?.detail || error.message))
        } finally {
            setLoading(false)
        }
    }

    const handleTrain = async () => {
        if (!confirm('確定要重新訓練模型嗎？這可能需要幾分鐘時間。')) return

        setTraining(true)
        try {
            const res = await forecastApi.train()
            alert(res.message || '模型訓練已開始')
            await fetchStatus()
        } catch (error) {
            console.error('Training failed:', error)
            alert('訓練失敗: ' + (error.response?.data?.detail || error.message))
        } finally {
            setTraining(false)
        }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-gradient-to-r from-blue-500 to-cyan-500 rounded-2xl p-8 shadow-2xl">
                <h2 className="text-3xl font-bold text-white mb-2">AI 電力預測系統</h2>
                <p className="text-blue-100">使用機器學習模型預測未來用電量</p>
            </div>

            {/* Model Status */}
            {status && (
                <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                    <h3 className="text-xl font-bold text-white mb-4">模型狀態</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <p className="text-slate-400 text-sm mb-1">訓練數據筆數</p>
                            <p className="text-2xl font-bold text-white">{status.training_samples || 0}</p>
                        </div>
                        <div>
                            <p className="text-slate-400 text-sm mb-1">模型準確度</p>
                            <p className="text-2xl font-bold text-emerald-400">
                                {status.model_accuracy ? `${(status.model_accuracy * 100).toFixed(1)}%` : 'N/A'}
                            </p>
                        </div>
                        <div>
                            <p className="text-slate-400 text-sm mb-1">GPU 狀態</p>
                            <p className="text-2xl font-bold text-cyan-400">
                                {status.gpu_available ? '✓ 可用' : '✗ 不可用'}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Prediction Controls */}
            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                <h3 className="text-xl font-bold text-white mb-6">預測設定</h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    {/* Model Selection */}
                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">選擇模型</label>
                        <select
                            value={selectedModel}
                            onChange={(e) => setSelectedModel(e.target.value)}
                            className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="xgboost">XGBoost (快速高效)</option>
                            <option value="lightgbm">LightGBM (輕量級)</option>
                            <option value="transformer">Transformer (深度學習)</option>
                            <option value="lstm">LSTM (時序預測)</option>
                        </select>
                    </div>

                    {/* Hours Ahead */}
                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">
                            預測時長 ({hours} 小時)
                        </label>
                        <input
                            type="range"
                            min="1"
                            max="168"
                            value={hours}
                            onChange={(e) => setHours(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                        <div className="flex justify-between text-xs text-slate-400 mt-1">
                            <span>1h</span>
                            <span>24h</span>
                            <span>72h</span>
                            <span>168h</span>
                        </div>
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-4">
                    <button
                        onClick={handlePredict}
                        disabled={loading}
                        className="flex-1 bg-gradient-to-r from-blue-500 to-cyan-500 text-white px-6 py-3 rounded-lg font-semibold hover:shadow-lg hover:shadow-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
                    >
                        {loading ? (
                            <span className="flex items-center justify-center">
                                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                預測中...
                            </span>
                        ) : (
                            '開始預測'
                        )}
                    </button>

                    <button
                        onClick={handleTrain}
                        disabled={training}
                        className="bg-emerald-500 text-white px-6 py-3 rounded-lg font-semibold hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
                    >
                        {training ? '訓練中...' : '訓練模型'}
                    </button>
                </div>
            </div>

            {/* Prediction Results */}
            {prediction && (
                <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                    <h3 className="text-xl font-bold text-white mb-6">預測結果</h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-slate-400 text-sm mb-1">預測負載</p>
                            <p className="text-2xl font-bold text-blue-400">
                                {prediction.predicted_load?.toLocaleString()} kW
                            </p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-slate-400 text-sm mb-1">太陽能發電</p>
                            <p className="text-2xl font-bold text-yellow-400">
                                {prediction.predicted_solar?.toLocaleString()} kW
                            </p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-slate-400 text-sm mb-1">風力發電</p>
                            <p className="text-2xl font-bold text-cyan-400">
                                {prediction.predicted_wind?.toLocaleString()} kW
                            </p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-slate-400 text-sm mb-1">模型信心度</p>
                            <p className="text-2xl font-bold text-emerald-400">
                                {prediction.confidence ? `${(prediction.confidence * 100).toFixed(1)}%` : 'N/A'}
                            </p>
                        </div>
                    </div>

                    {prediction.timestamps && prediction.predictions && (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead className="text-slate-400 border-b border-slate-700">
                                    <tr>
                                        <th className="py-3 px-4">時間</th>
                                        <th className="py-3 px-4">預測負載</th>
                                        <th className="py-3 px-4">太陽能</th>
                                        <th className="py-3 px-4">風力</th>
                                    </tr>
                                </thead>
                                <tbody className="text-white">
                                    {prediction.timestamps.slice(0, 10).map((time, idx) => (
                                        <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                                            <td className="py-3 px-4">{new Date(time).toLocaleString('zh-TW')}</td>
                                            <td className="py-3 px-4">{prediction.predictions[idx]?.toLocaleString()} kW</td>
                                            <td className="py-3 px-4">{prediction.solar_predictions?.[idx]?.toLocaleString() || 'N/A'}</td>
                                            <td className="py-3 px-4">{prediction.wind_predictions?.[idx]?.toLocaleString() || 'N/A'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default Forecast
