import { defineStore } from 'pinia'
import { dashboardApi } from '../api/endpoints'

export const useDashboardStore = defineStore('dashboard', {
    state: () => ({
        summary: null,
        loading: false,
        error: null
    }),

    actions: {
        async fetchSummary() {
            this.loading = true
            this.error = null
            try {
                this.summary = await dashboardApi.getSummary()
            } catch (error) {
                this.error = error.message
                console.error('Failed to fetch summary:', error)
            } finally {
                this.loading = false
            }
        }
    }
})
