import api from './index'

export const dashboardApi = {
    getSummary: () => api.get('/dashboard/summary'),
    getChartData: (data) => api.post('/dashboard/chart-data', data)
}

export const forecastApi = {
    predict: (data) => api.post('/forecast/predict', data),
    getStatus: (taskId) => api.get(`/forecast/predict/${taskId}`),
    getLatest: () => api.get('/forecast/latest'),
    train: (data) => api.post('/forecast/train', null, { params: data })
}

export const optimizationApi = {
    optimize: (data) => api.post('/optimization/optimize', data),
    getStatus: (taskId) => api.get(`/optimization/optimize/${taskId}`),
    getPlan: (planId) => api.get(`/optimization/plan/${planId}`),
    getLatest: () => api.get('/optimization/latest')
}

export const auditApi = {
    generate: (data) => api.post('/audit/generate', data),
    getReport: (reportId) => api.get(`/audit/report/${reportId}`),
    getLatest: () => api.get('/audit/latest'),
    query: (question) => api.post('/audit/query', { question })
}
