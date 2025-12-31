import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'

const routes = [
    {
        path: '/',
        name: 'Dashboard',
        component: Dashboard
    },
    {
        path: '/forecast',
        name: 'Forecast',
        component: () => import('../views/Forecast.vue')
    },
    {
        path: '/optimization',
        name: 'Optimization',
        component: () => import('../views/Optimization.vue')
    },
    {
        path: '/audit',
        name: 'Audit',
        component: () => import('../views/Audit.vue')
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router
