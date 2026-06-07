import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('../views/ResetPasswordView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/notification-preferences',
      name: 'notification-preferences',
      component: () => import('../views/NotificationPreferencesView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/message-center',
      name: 'message-center',
      component: () => import('../views/MessageCenterView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/consumption-analytics',
      name: 'consumption-analytics',
      component: () => import('../views/ConsumptionAnalyticsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/my-analytics',
      name: 'my-analytics',
      component: () => import('../views/MyAnalyticsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/building-management',
      name: 'building-management',
      component: () => import('../views/BuildingManagementView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/my-stay',
      name: 'my-stay',
      component: () => import('../views/MyStayView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/energy-analytics',
      name: 'energy-analytics',
      component: () => import('../views/EnergyAnalyticsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/marketing-center',
      name: 'marketing-center',
      component: () => import('../views/MarketingCenterView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/my-coupons',
      name: 'my-coupons',
      component: () => import('../views/MyCouponsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/my-plans',
      name: 'my-plans',
      component: () => import('../views/MyPlansView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/plan-management',
      name: 'plan-management',
      component: () => import('../views/PlanManagementView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/price-management',
      name: 'price-management',
      component: () => import('../views/PriceManagementView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/my-tickets',
      name: 'my-tickets',
      component: () => import('../views/TicketStudentView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/ticket-pool',
      name: 'ticket-pool',
      component: () => import('../views/TicketPoolView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/ticket-workbench',
      name: 'ticket-workbench',
      component: () => import('../views/TicketWorkbenchView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/tickets/:id',
      name: 'ticket-detail',
      component: () => import('../views/TicketDetailView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  authStore.hydrate()

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return { name: 'login' }
  }

  if (to.meta.guestOnly && authStore.isLoggedIn) {
    return { name: 'dashboard' }
  }

  if (to.meta.requiresAdmin && authStore.user?.profile?.role !== 'admin') {
    return { name: 'dashboard' }
  }

  return true
})

export default router
