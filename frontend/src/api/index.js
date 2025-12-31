import axios from 'axios'

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// Request interceptor
api.interceptors.request.use(
    config => {
        // Add auth token if available
        const token = localStorage.getItem('token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    error => Promise.reject(error)
)

// Response interceptor
api.interceptors.response.use(
    response => response.data,
    error => {
        console.error('API Error:', error.response?.data || error.message)
        return Promise.reject(error)
    }
)

// API endpoints
export const dashboardApi = {
    getSummary: () => api.get('/dashboard/summary'),
    getChartData: () => api.get('/dashboard/chart-data')
}

export const forecastApi = {
    predict: (data) => api.post('/forecast/predict', data),
    getStatus: () => api.get('/forecast/status'),
    getLatest: () => api.get('/forecast/latest'),
    train: () => api.post('/forecast/train')
}

export const optimizationApi = {
    optimize: (data) => api.post('/optimization/optimize', data),
    getSchedule: (params) => api.get('/optimization/schedule', { params })
}

export const auditApi = {
    generateReport: (data) => api.post('/audit/report', data),
    getHistory: (params) => api.get('/audit/history', { params })
}

export default api
