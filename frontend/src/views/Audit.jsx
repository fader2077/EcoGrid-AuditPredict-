import React, { useState } from 'react'
import { auditApi } from '../api'
import { marked } from 'marked'

function Audit() {
    const [dateRange, setDateRange] = useState({
        start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end: new Date().toISOString().split('T')[0]
    })
    const [reportType, setReportType] = useState('comprehensive')
    const [report, setReport] = useState(null)
    const [loading, setLoading] = useState(false)

    const handleGenerateReport = async () => {
        setLoading(true)
        try {
            const response = await auditApi.generateReport({
                start_date: dateRange.start,
                end_date: dateRange.end,
                report_type: reportType
            })
            setReport(response)
        } catch (error) {
            console.error('Failed to generate report:', error)
            alert('報告生成失敗: ' + (error.response?.data?.detail || error.message))
        } finally {
            setLoading(false)
        }
    }

    const renderMarkdown = (markdown) => {
        return { __html: marked(markdown || '') }
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl p-8 shadow-2xl">
                <h2 className="text-3xl font-bold text-white mb-2">AI 能源審計系統</h2>
                <p className="text-purple-100">使用 Ollama 本地 LLM 生成專業用電分析報告</p>
            </div>

            {/* Report Generation Controls */}
            <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                <h3 className="text-xl font-bold text-white mb-6">報告生成設定</h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    {/* Date Range */}
                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">開始日期</label>
                        <input
                            type="date"
                            value={dateRange.start}
                            onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
                            className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                        />
                    </div>

                    <div>
                        <label className="block text-slate-300 text-sm font-medium mb-2">結束日期</label>
                        <input
                            type="date"
                            value={dateRange.end}
                            onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
                            className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                        />
                    </div>

                    {/* Report Type */}
                    <div className="md:col-span-2">
                        <label className="block text-slate-300 text-sm font-medium mb-2">報告類型</label>
                        <select
                            value={reportType}
                            onChange={(e) => setReportType(e.target.value)}
                            className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                        >
                            <option value="comprehensive">綜合分析報告</option>
                            <option value="efficiency">能源效率報告</option>
                            <option value="cost">成本分析報告</option>
                            <option value="renewable">再生能源報告</option>
                        </select>
                    </div>
                </div>

                {/* Generate Button */}
                <button
                    onClick={handleGenerateReport}
                    disabled={loading}
                    className="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-4 rounded-lg font-semibold hover:shadow-lg hover:shadow-purple-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
                >
                    {loading ? (
                        <span className="flex items-center justify-center">
                            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            AI 正在分析數據並生成報告...
                        </span>
                    ) : (
                        <span className="flex items-center justify-center">
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            生成 AI 審計報告
                        </span>
                    )}
                </button>
            </div>

            {/* AI Information Card */}
            <div className="bg-gradient-to-r from-indigo-500/20 to-purple-500/20 backdrop-blur-xl rounded-2xl p-6 border border-indigo-500/30 shadow-xl">
                <div className="flex items-start">
                    <div className="flex-shrink-0">
                        <svg className="w-12 h-12 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                    </div>
                    <div className="ml-4 flex-1">
                        <h3 className="text-lg font-semibold text-white mb-2">使用 Ollama 本地 LLM</h3>
                        <p className="text-slate-300 text-sm mb-3">
                            本系統使用 Ollama 在本地運行大型語言模型，確保數據隱私與安全性。AI 會分析您的用電數據，提供專業的能源審計建議。
                        </p>
                        <div className="flex flex-wrap gap-2">
                            <span className="px-3 py-1 bg-indigo-500/20 border border-indigo-500/30 rounded-full text-indigo-300 text-xs font-medium">
                                🔒 本地運算
                            </span>
                            <span className="px-3 py-1 bg-purple-500/20 border border-purple-500/30 rounded-full text-purple-300 text-xs font-medium">
                                🤖 智能分析
                            </span>
                            <span className="px-3 py-1 bg-pink-500/20 border border-pink-500/30 rounded-full text-pink-300 text-xs font-medium">
                                📊 專業建議
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Report Display */}
            {report && (
                <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50 shadow-xl">
                    <div className="flex items-center justify-between mb-6">
                        <h3 className="text-2xl font-bold text-white">審計報告</h3>
                        <button
                            onClick={() => {
                                const element = document.createElement('a')
                                const file = new Blob([report.report_content || ''], { type: 'text/markdown' })
                                element.href = URL.createObjectURL(file)
                                element.download = `audit_report_${dateRange.start}_${dateRange.end}.md`
                                document.body.appendChild(element)
                                element.click()
                                document.body.removeChild(element)
                            }}
                            className="px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg transition-colors duration-300 flex items-center"
                        >
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            下載報告
                        </button>
                    </div>

                    {/* Report Metadata */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-slate-400 text-sm mb-1">報告類型</p>
                            <p className="text-white font-semibold">{report.report_type || reportType}</p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-slate-400 text-sm mb-1">分析期間</p>
                            <p className="text-white font-semibold">{dateRange.start} ~ {dateRange.end}</p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-slate-400 text-sm mb-1">生成時間</p>
                            <p className="text-white font-semibold">
                                {report.generated_at ? new Date(report.generated_at).toLocaleString('zh-TW') : '剛剛'}
                            </p>
                        </div>
                    </div>

                    {/* Report Content */}
                    <div
                        className="prose prose-invert prose-slate max-w-none
              prose-headings:text-white prose-headings:font-bold
              prose-h1:text-3xl prose-h2:text-2xl prose-h3:text-xl
              prose-p:text-slate-300 prose-p:leading-relaxed
              prose-strong:text-white prose-strong:font-semibold
              prose-ul:text-slate-300 prose-ol:text-slate-300
              prose-li:text-slate-300
              prose-a:text-purple-400 prose-a:no-underline hover:prose-a:text-purple-300
              prose-code:text-emerald-400 prose-code:bg-slate-900/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
              prose-pre:bg-slate-900/50 prose-pre:border prose-pre:border-slate-700
              prose-blockquote:border-l-purple-500 prose-blockquote:text-slate-300
              prose-table:text-slate-300
              prose-th:text-white prose-th:bg-slate-700/50
              prose-td:border-slate-700"
                        dangerouslySetInnerHTML={renderMarkdown(report.report_content)}
                    />
                </div>
            )}

            {/* Empty State */}
            {!report && !loading && (
                <div className="bg-slate-800/30 backdrop-blur-xl rounded-2xl p-12 border border-slate-700/30 text-center">
                    <svg className="w-20 h-20 text-slate-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <h3 className="text-xl font-semibold text-slate-400 mb-2">尚未生成報告</h3>
                    <p className="text-slate-500">設定參數後點擊按鈕，AI 將為您生成專業的能源審計報告</p>
                </div>
            )}
        </div>
    )
}

export default Audit
