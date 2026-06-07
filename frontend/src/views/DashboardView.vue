<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElNotification } from 'element-plus'

import SimpleBarChart from '../components/SimpleBarChart.vue'
import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(true)
const actionLoading = ref(false)
const activeTab = ref('overview')
const topBuildings = ref([])

const dashboard = reactive({
  wallet: { balance: '0.00', is_frozen: false, frozen_reason: '' },
  summary: { total_recharge: '0.00', total_consumption: '0.00', pending_recharge_orders: 0 },
  recent_recharges: [],
  recent_consumptions: [],
})

const orderForm = reactive({
  amount: null,
  channel: 'alipay',
  submit_remark: '',
  coupon_id: null,
})

const availableCoupons = ref([])
const promoCalc = reactive({
  original_amount: '0.00',
  payable_amount: '0.00',
  credited_amount: '0.00',
  discount_amount: '0.00',
  bonus_amount: '0.00',
  stacking_policy: 'allow',
  applied_promotions: [],
  applied_coupon_id: null,
  applied_coupon_name: '',
  coupon_discount_amount: '0.00',
  error: '',
})
let promoCalcTimer = null

async function loadAvailableCoupons() {
  try {
    const { data } = await http.get('/marketing/user-coupons/available/')
    availableCoupons.value = data
  } catch (_e) {
    availableCoupons.value = []
  }
}

async function recalcPromotion() {
  if (!orderForm.amount || Number(orderForm.amount) <= 0) {
    Object.assign(promoCalc, {
      original_amount: '0.00', payable_amount: '0.00', credited_amount: '0.00',
      discount_amount: '0.00', bonus_amount: '0.00', stacking_policy: 'allow',
      applied_promotions: [], applied_coupon_id: null, applied_coupon_name: '',
      coupon_discount_amount: '0.00', error: '',
    })
    return
  }
  if (promoCalcTimer) clearTimeout(promoCalcTimer)
  promoCalcTimer = setTimeout(async () => {
    try {
      const params = { amount: Number(orderForm.amount) }
      if (orderForm.coupon_id) params.coupon_id = orderForm.coupon_id
      const { data } = await http.get('/marketing/calculate/', { params })
      Object.assign(promoCalc, data)
    } catch (_e) { /* ignore */ }
  }, 200)
}

const orderFilters = reactive({
  status: '',
  user_id: '',
})

const orders = ref([])
const selectedOrders = ref([])
const batchReviewVisible = ref(false)
const batchReviewAction = ref('approved')
const batchReviewRemark = ref('')
const batchReviewLoading = ref(false)
const batchReviewResult = ref(null)

const MAX_BATCH_SIZE = 50

const pendingSelectedOrders = computed(() =>
  selectedOrders.value.filter((o) => o.status === 'pending')
)

function handleSelectionChange(selection) {
  selectedOrders.value = selection
}

function toggleSelectAllPending() {
  const table = document.querySelector('.orders-table .el-checkbox')
  if (table) {
    const pendingOrders = orders.value.filter((o) => o.status === 'pending')
    if (pendingSelectedOrders.value.length === pendingOrders.length) {
      selectedOrders.value = []
    } else {
      selectedOrders.value = pendingOrders
    }
  }
}

function openBatchReview(action) {
  if (pendingSelectedOrders.value.length === 0) {
    ElNotification({ title: '请选择订单', message: '请先勾选待审核的订单。', type: 'warning' })
    return
  }
  if (pendingSelectedOrders.value.length > MAX_BATCH_SIZE) {
    ElNotification({
      title: '超出数量限制',
      message: `单次最多审核 ${MAX_BATCH_SIZE} 条订单，当前已选 ${pendingSelectedOrders.value.length} 条。`,
      type: 'warning',
    })
    return
  }
  batchReviewAction.value = action
  batchReviewRemark.value = ''
  batchReviewResult.value = null
  batchReviewVisible.value = true
}

async function confirmBatchReview() {
  batchReviewLoading.value = true
  try {
    const orderIds = pendingSelectedOrders.value.map((o) => o.id)
    const { data } = await http.post('/billing/recharge-orders/batch-review/', {
      order_ids: orderIds,
      action: batchReviewAction.value,
      review_remark: batchReviewRemark.value,
    })
    batchReviewResult.value = data
    selectedOrders.value = []
    await Promise.all([loadOrders(), loadDashboard(), loadNotifications()])
  } finally {
    batchReviewLoading.value = false
  }
}

function closeBatchReviewDialog() {
  batchReviewVisible.value = false
  batchReviewResult.value = null
}

const consumptionFilters = reactive({
  category: '',
  start_date: '',
  end_date: '',
})
const consumptions = ref([])
const consumptionStats = reactive({
  category_stats: [],
  daily_trend: [],
})

const walletLogs = ref([])
const announcements = ref([])
const notifications = reactive({
  unread_count: 0,
  items: [],
})

// ========= 月结管理（管理员） =========
const settlementFilters = reactive({
  period: '',
  user_id: '',
  status: '',
})
const statements = ref([])
const settlementRuns = ref([])
const reconciliationDiffs = ref([])
const reconciliationSummary = reactive({
  run_id: '',
  total_users: 0,
  diff_count: 0,
})

const runSettlementForm = reactive({
  period: '',
  auto_publish: true,
  user_id: null,
})
const runSettlementVisible = ref(false)
const runSettlementLoading = ref(false)

const crossMonthAdjustForm = reactive({
  user_id: null,
  source_period: '',
  target_period: '',
  amount: null,
  remark: '',
})
const crossMonthAdjustVisible = ref(false)
const crossMonthAdjustLoading = ref(false)

const reconciliationLoading = ref(false)

// ========= 我的账单（学生） =========
const myStatements = ref([])
const selectedStatementPeriod = ref('')
const statementDetail = reactive({
  statement: null,
  logs: [],
})
const statementDetailVisible = ref(false)
const statementDetailLoading = ref(false)

const adminUsers = ref([])
const adminUserFilters = reactive({
  keyword: '',
  role: '',
  is_active: '',
})

const announcementForm = reactive({
  title: '',
  content: '',
  is_active: true,
})

const isAdmin = computed(() => authStore.user?.profile?.role === 'admin')

const channelMap = {
  alipay: '支付宝',
  wechat: '微信支付',
  bank: '银行卡',
}

const orderStatusMap = {
  pending: { label: '待审核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
}

const categoryMap = {
  water: '水费',
  electricity: '电费',
}

const statementStatusMap = {
  draft: { label: '草稿', type: 'info' },
  published: { label: '已发布', type: 'success' },
  rolled_back: { label: '已回滚', type: 'danger' },
}

const settlementRunStatusMap = {
  running: { label: '运行中', type: 'warning' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

const settlementRunModeMap = {
  month: '按月跑批',
  user: '按用户重跑',
}

const changeTypeMap = {
  recharge: '充值入账',
  consumption: '消费扣费',
  freeze: '账户冻结',
  unfreeze: '账户解冻',
  adjust: '余额调整',
  refund: '退款',
  cross_month_adjust: '跨月调整',
}

function formatMoney(value) {
  const amount = Number(value ?? 0)
  if (Number.isNaN(amount)) return '0.00'
  return amount.toFixed(2)
}

function formatDateTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function stackingPolicyText(policy) {
  return {
    allow: '活动与优惠券可同时使用',
    exclusive: '活动与优惠券择优生效',
    coupon_only: '仅优惠券生效',
    promo_only: '仅活动生效',
  }[policy] || policy
}

function consumeStatsForCategory() {
  return consumptionStats.category_stats.map((item) => ({
    label: categoryMap[item.category] || item.category,
    value: formatMoney(item.total_cost),
  }))
}

function consumeStatsForTrend() {
  return consumptionStats.daily_trend.map((item) => ({
    label: item.day,
    value: formatMoney(item.total_cost),
  }))
}

async function loadDashboard() {
  const { data } = await http.get('/billing/dashboard/')
  Object.assign(dashboard, data)
}

async function loadOrders() {
  const params = {}
  if (orderFilters.status) params.status = orderFilters.status
  if (isAdmin.value && orderFilters.user_id) params.user_id = orderFilters.user_id
  const { data } = await http.get('/billing/recharge-orders/', { params })
  orders.value = data
}

async function submitRechargeOrder() {
  if (!orderForm.amount || Number(orderForm.amount) <= 0) {
    ElNotification({ title: '提交失败', message: '请输入有效金额。', type: 'warning' })
    return
  }

  actionLoading.value = true
  try {
    const payload = {
      amount: orderForm.amount,
      channel: orderForm.channel,
      submit_remark: orderForm.submit_remark,
      coupon_id: orderForm.coupon_id || null,
    }
    await http.post('/billing/recharge-orders/', payload)
    ElNotification({ title: '订单已提交', message: '请等待管理员审核。', type: 'success' })
    orderForm.amount = null
    orderForm.submit_remark = ''
    orderForm.coupon_id = null
    Object.assign(promoCalc, {
      original_amount: '0.00', payable_amount: '0.00', credited_amount: '0.00',
      discount_amount: '0.00', bonus_amount: '0.00', stacking_policy: 'allow',
      applied_promotions: [], applied_coupon_id: null, applied_coupon_name: '',
      coupon_discount_amount: '0.00', error: '',
    })
    await Promise.all([loadOrders(), loadDashboard(), loadNotifications(), loadAvailableCoupons()])
  } finally {
    actionLoading.value = false
  }
}

async function reviewOrder(order, action) {
  const result = await ElMessageBox.prompt(
    action === 'approved' ? '请输入通过备注（可选）' : '请输入驳回原因',
    action === 'approved' ? '通过订单' : '驳回订单',
    {
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入审核备注',
    }
  ).catch(() => null)

  if (!result) return

  actionLoading.value = true
  try {
    await http.post(`/billing/recharge-orders/${order.id}/review/`, {
      action,
      review_remark: result.value || '',
    })
    ElNotification({ title: '审核完成', message: '订单状态已更新。', type: 'success' })
    await Promise.all([loadOrders(), loadDashboard(), loadNotifications()])
  } finally {
    actionLoading.value = false
  }
}

async function loadConsumptions() {
  const params = {}
  if (consumptionFilters.category) params.category = consumptionFilters.category
  if (consumptionFilters.start_date) params.start_date = consumptionFilters.start_date
  if (consumptionFilters.end_date) params.end_date = consumptionFilters.end_date

  const { data } = await http.get('/billing/consumptions/', { params })
  consumptions.value = data
}

async function loadConsumptionStats() {
  const params = {}
  if (consumptionFilters.start_date) params.start_date = consumptionFilters.start_date
  if (consumptionFilters.end_date) params.end_date = consumptionFilters.end_date
  const { data } = await http.get('/billing/consumptions/stats/', { params })
  Object.assign(consumptionStats, data)
}

async function loadWalletLogs() {
  const { data } = await http.get('/billing/wallet-logs/')
  walletLogs.value = data
}

// ========= 月结管理 =========
async function loadStatements() {
  const params = {}
  if (settlementFilters.period) params.period = settlementFilters.period
  if (settlementFilters.user_id) params.user_id = settlementFilters.user_id
  if (settlementFilters.status) params.status = settlementFilters.status
  const { data } = await http.get('/billing/admin/statements/', { params })
  statements.value = data
}

async function loadSettlementRuns() {
  const { data } = await http.get('/billing/admin/settlement-runs/')
  settlementRuns.value = data
}

async function loadReconciliationDiffs() {
  const { data } = await http.get('/billing/admin/reconciliation/')
  reconciliationDiffs.value = data
}

function openRunSettlementDialog() {
  runSettlementForm.period = ''
  runSettlementForm.auto_publish = true
  runSettlementForm.user_id = null
  runSettlementVisible.value = true
}

async function confirmRunSettlement() {
  if (!runSettlementForm.period) {
    ElNotification({ title: '请填写账期', message: '账期格式为 YYYY-MM。', type: 'warning' })
    return
  }
  runSettlementLoading.value = true
  try {
    const payload = {
      period: runSettlementForm.period,
      auto_publish: runSettlementForm.auto_publish,
    }
    if (runSettlementForm.user_id) payload.user_id = runSettlementForm.user_id
    const { data } = await http.post('/billing/admin/settlement-runs/', payload)
    ElNotification({
      title: '月结跑批已启动',
      message: `状态：${settlementRunStatusMap[data.status]?.label || data.status}，共 ${data.total_users} 个用户。`,
      type: 'success',
    })
    runSettlementVisible.value = false
    await Promise.all([loadStatements(), loadSettlementRuns()])
  } finally {
    runSettlementLoading.value = false
  }
}

async function publishStatement(row) {
  try {
    await http.post(`/billing/admin/statements/${row.id}/`, { action: 'publish' })
    ElNotification({ title: '已发布', message: `${row.user_name} ${row.period} 月结单已发布。`, type: 'success' })
    await loadStatements()
  } catch (e) {
    ElNotification({ title: '发布失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function rollbackStatement(row) {
  try {
    await http.post(`/billing/admin/statements/${row.id}/`, { action: 'rollback' })
    ElNotification({ title: '已回滚', message: `${row.user_name} ${row.period} 月结单已回滚。`, type: 'success' })
    await loadStatements()
  } catch (e) {
    ElNotification({ title: '回滚失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function runReconciliation() {
  reconciliationLoading.value = true
  try {
    const { data } = await http.post('/billing/admin/reconciliation/')
    Object.assign(reconciliationSummary, data)
    await loadReconciliationDiffs()
    ElNotification({
      title: '账实校验完成',
      message: `总用户 ${data.total_users}，差异账户 ${data.diff_count}。`,
      type: data.diff_count === 0 ? 'success' : 'warning',
    })
  } finally {
    reconciliationLoading.value = false
  }
}

function openCrossMonthAdjustDialog() {
  crossMonthAdjustForm.user_id = null
  crossMonthAdjustForm.source_period = ''
  crossMonthAdjustForm.target_period = ''
  crossMonthAdjustForm.amount = null
  crossMonthAdjustForm.remark = ''
  crossMonthAdjustVisible.value = true
}

async function confirmCrossMonthAdjust() {
  if (!crossMonthAdjustForm.user_id || !crossMonthAdjustForm.source_period || !crossMonthAdjustForm.target_period || crossMonthAdjustForm.amount == null) {
    ElNotification({ title: '请填写完整', message: '用户、来源账期、目标账期、金额均为必填。', type: 'warning' })
    return
  }
  crossMonthAdjustLoading.value = true
  try {
    await http.post('/billing/admin/cross-month-adjust/', {
      user_id: crossMonthAdjustForm.user_id,
      source_period: crossMonthAdjustForm.source_period,
      target_period: crossMonthAdjustForm.target_period,
      amount: crossMonthAdjustForm.amount,
      remark: crossMonthAdjustForm.remark,
    })
    ElNotification({ title: '已完成', message: '跨月调整已入账至目标账期。', type: 'success' })
    crossMonthAdjustVisible.value = false
    await loadWalletLogs()
  } catch (e) {
    ElNotification({ title: '调整失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  } finally {
    crossMonthAdjustLoading.value = false
  }
}

// ========= 学生：我的账单 =========
async function loadMyStatements() {
  const { data } = await http.get('/billing/statements/')
  myStatements.value = data
}

async function viewStatementDetail(period: string) {
  selectedStatementPeriod.value = period
  statementDetailLoading.value = true
  try {
    const { data } = await http.get(`/billing/statements/${period}/`)
    statementDetail.statement = data.statement
    statementDetail.logs = data.logs
    statementDetailVisible.value = true
  } finally {
    statementDetailLoading.value = false
  }
}

function downloadStatementCSV(period) {
  const url = `/billing/statements/${period}/csv/`
  http.get(url, { responseType: 'blob' }).then((res) => {
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8-sig' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `statement_${authStore.user?.username || 'me'}_${period}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }).catch((e) => {
    ElNotification({ title: '下载失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  })
}

async function loadAnnouncements() {
  const params = isAdmin.value ? { include_inactive: true } : {}
  const { data } = await http.get('/notices/announcements/', { params })
  announcements.value = data
}

async function publishAnnouncement() {
  if (!announcementForm.title.trim() || !announcementForm.content.trim()) {
    ElNotification({ title: '发布失败', message: '请填写公告标题和内容。', type: 'warning' })
    return
  }

  actionLoading.value = true
  try {
    const { data } = await http.post('/notices/announcements/', announcementForm)
    ElNotification({ title: '公告已发布', message: `已推送 ${data.push_count} 位用户。`, type: 'success' })
    announcementForm.title = ''
    announcementForm.content = ''
    announcementForm.is_active = true
    await loadAnnouncements()
  } finally {
    actionLoading.value = false
  }
}

async function loadNotifications() {
  const { data } = await http.get('/notices/notifications/')
  notifications.unread_count = data.unread_count
  notifications.items = data.items
}

async function markNotificationRead(notification) {
  await http.post('/notices/notifications/read/', { notification_id: notification.id })
  await loadNotifications()
}

async function markAllNotificationsRead() {
  await http.post('/notices/notifications/read/', { mark_all: true })
  await loadNotifications()
}

async function loadAdminUsers() {
  const params = {}
  if (adminUserFilters.keyword) params.keyword = adminUserFilters.keyword
  if (adminUserFilters.role) params.role = adminUserFilters.role
  if (adminUserFilters.is_active) params.is_active = adminUserFilters.is_active
  const { data } = await http.get('/auth/admin/users/', { params })
  adminUsers.value = data
}

async function updateUserRole(row, role) {
  await http.patch(`/auth/admin/users/${row.id}/`, { role })
  ElNotification({ title: '角色已更新', message: '用户角色修改成功。', type: 'success' })
  await loadAdminUsers()
}

async function updateUserStatus(row, value) {
  await http.patch(`/auth/admin/users/${row.id}/`, { is_active: value })
  ElNotification({ title: '账号状态已更新', message: '启用状态修改成功。', type: 'success' })
  await loadAdminUsers()
}

async function walletAction(row, action) {
  const result = await ElMessageBox.prompt(
    action === 'freeze' ? '请输入冻结原因' : '请输入解冻备注（可选）',
    action === 'freeze' ? '冻结账户' : '解冻账户',
    {
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入说明',
    }
  ).catch(() => null)

  if (!result) return

  await http.post(`/billing/wallets/${row.id}/action/`, {
    action,
    reason: result.value || '',
  })
  ElNotification({
    title: action === 'freeze' ? '账户已冻结' : '账户已解冻',
    message: '钱包状态更新成功。',
    type: 'success',
  })
  await Promise.all([loadAdminUsers(), loadWalletLogs()])
}

async function loadTopBuildings() {
  try {
    const { data } = await http.get('/housing/energy/top-buildings/')
    topBuildings.value = data
  } catch (_e) {
    topBuildings.value = []
  }
}

const topBuildingsChart = computed(() => {
  return topBuildings.value.slice(0, 10).map((item) => ({
    label: item.building_name || `楼栋#${item.building_id}`,
    value: formatMoney(item.total_cost),
  }))
})

async function refreshAll() {
  loading.value = true
  try {
    const tasks = [loadDashboard(), loadOrders(), loadConsumptions(), loadConsumptionStats(), loadWalletLogs(), loadAnnouncements(), loadNotifications()]
    if (isAdmin.value) {
      tasks.push(loadAdminUsers(), loadStatements(), loadSettlementRuns(), loadReconciliationDiffs(), loadTopBuildings())
    } else {
      tasks.push(loadMyStatements(), loadAvailableCoupons())
    }
    await Promise.all(tasks)
  } finally {
    loading.value = false
  }
}

async function logout() {
  authStore.clearSession()
  await router.push('/login')
}

onMounted(async () => {
  if (!authStore.user) {
    try {
      await authStore.fetchMe()
    } catch (_error) {
      authStore.clearSession()
      await router.push('/login')
      return
    }
  }

  activeTab.value = isAdmin.value ? 'orders' : 'overview'
  await refreshAll()
})
</script>

<template>
  <main class="page-shell animated-in">
    <section class="dashboard-wrap">
      <el-card class="section-card" shadow="never">
        <el-row justify="space-between" align="middle" :gutter="12">
          <el-col :xs="24" :sm="18">
            <h2 class="section-title">学生水电充值管理系统</h2>
            <p style="margin: 0; color: var(--text-sub)">
              当前身份：{{ isAdmin ? '管理员' : '学生' }} ｜ 未读通知：{{ notifications.unread_count }}
            </p>
          </el-col>
          <el-col :xs="24" :sm="6" style="text-align: right">
            <el-button style="margin-right: 8px" @click="$router.push('/notification-preferences')">通知偏好</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" plain @click="$router.push('/building-management')">楼宇管理</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" plain @click="$router.push('/energy-analytics')">能耗视图</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" plain @click="$router.push('/message-center')">消息中心</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" plain @click="$router.push('/marketing-center')">营销中心</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" plain @click="$router.push('/ticket-pool')">工单池</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" plain @click="$router.push('/ticket-workbench')">我的待办</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" @click="$router.push('/consumption-analytics')">消费分析</el-button>
            <el-button v-if="isAdmin" style="margin-right: 8px" type="primary" plain @click="$router.push('/plan-management')">计划管理</el-button>
            <el-button v-else style="margin-right: 8px" type="primary" plain @click="$router.push('/my-stay')">我的入住</el-button>
            <el-button v-else style="margin-right: 8px" type="primary" plain @click="$router.push('/my-coupons')">我的优惠券</el-button>
            <el-button v-else style="margin-right: 8px" type="primary" plain @click="$router.push('/my-plans')">我的计划</el-button>
            <el-button v-else style="margin-right: 8px" type="primary" @click="$router.push('/my-tickets')">报修/工单</el-button>
            <el-button v-else style="margin-right: 8px" type="primary" @click="$router.push('/my-analytics')">我的分析</el-button>
            <el-button style="margin-right: 8px" @click="refreshAll">刷新数据</el-button>
            <el-button type="danger" plain @click="logout">退出登录</el-button>
          </el-col>
        </el-row>
      </el-card>

      <el-skeleton :loading="loading" animated :rows="8">
        <template #template>
          <el-card class="section-card" shadow="never">
            <el-skeleton-item variant="h3" style="width: 40%" />
            <el-skeleton-item variant="text" style="width: 100%" />
            <el-skeleton-item variant="text" style="width: 100%" />
          </el-card>
        </template>

        <template #default>
          <section class="summary-grid">
            <article class="summary-card">
              <div class="label">账户余额</div>
              <div class="value">¥ {{ formatMoney(dashboard.wallet.balance) }}</div>
              <div class="summary-note">{{ dashboard.wallet.is_frozen ? '账户已冻结' : '账户可正常使用' }}</div>
            </article>
            <article class="summary-card">
              <div class="label">累计充值</div>
              <div class="value">¥ {{ formatMoney(dashboard.summary.total_recharge) }}</div>
              <div class="summary-note">待审核充值单：{{ dashboard.summary.pending_recharge_orders || 0 }}</div>
            </article>
            <article class="summary-card">
              <div class="label">累计消费</div>
              <div class="value">¥ {{ formatMoney(dashboard.summary.total_consumption) }}</div>
              <div class="summary-note">消息中心支持公告与订单提醒</div>
            </article>
          </section>

          <el-card v-if="isAdmin" class="section-card" shadow="never">
            <el-row justify="space-between" align="middle" :gutter="12">
              <el-col :span="18">
                <h3 class="section-title" style="margin: 0">全校能耗 Top10 楼栋（最近30天）</h3>
              </el-col>
              <el-col :span="6" style="text-align: right">
                <el-button size="small" type="primary" plain @click="$router.push('/energy-analytics')">查看完整能耗分析</el-button>
              </el-col>
            </el-row>
            <div style="margin-top: 12px">
              <SimpleBarChart v-if="topBuildingsChart.length" title="消费金额（元）" :items="topBuildingsChart" color="#e67e22" />
              <el-empty v-else description="暂无能耗数据" :image-size="80" />
            </div>
          </el-card>

          <el-card class="section-card" shadow="never">
            <el-tabs v-model="activeTab">
              <el-tab-pane v-if="!isAdmin" label="总览" name="overview">
                <div class="form-grid">
                  <el-card class="section-card" shadow="never">
                    <h3 class="section-title">快速提交充值订单</h3>
                    <el-form label-position="top" @submit.prevent>
                      <el-form-item label="充值金额（元）">
                        <el-input-number v-model="orderForm.amount" :min="0" :precision="2" :step="10" style="width: 100%" @change="recalcPromotion" />
                      </el-form-item>
                      <el-form-item label="充值渠道">
                        <el-select v-model="orderForm.channel" style="width: 100%">
                          <el-option label="支付宝" value="alipay" />
                          <el-option label="微信支付" value="wechat" />
                          <el-option label="银行卡" value="bank" />
                        </el-select>
                      </el-form-item>
                      <el-form-item label="选择优惠券">
                        <el-select v-model="orderForm.coupon_id" :placeholder="availableCoupons.length ? '不使用优惠券' : '暂无可使用优惠券'" style="width: 100%" clearable @change="recalcPromotion">
                          <el-option
                            v-for="uc in availableCoupons"
                            :key="uc.id"
                            :label="uc.coupon_detail?.coupon_type === 'fixed' ? `满${Number(uc.coupon_detail.min_amount||0).toFixed(2)}减${Number(uc.coupon_detail.face_value).toFixed(2)}` : `${(Number(uc.coupon_detail.discount_rate)*10).toFixed(1)}折券` + (uc.coupon_detail?.name ? ` - ${uc.coupon_detail.name}` : '')"
                            :value="uc.id"
                          />
                        </el-select>
                      </el-form-item>
                      <el-form-item label="备注">
                        <el-input v-model="orderForm.submit_remark" placeholder="请输入订单备注（可选）" />
                      </el-form-item>

                      <el-descriptions v-if="orderForm.amount && Number(orderForm.amount) > 0" :column="1" border size="small" style="margin-bottom: 12px">
                        <el-descriptions-item label="面值">{{ formatMoney(promoCalc.original_amount) }} 元</el-descriptions-item>
                        <el-descriptions-item label="活动优惠" :span="1">
                          <span style="color:#f56c6c">- {{ formatMoney(Number(promoCalc.discount_amount) - Number(promoCalc.coupon_discount_amount)) }} 元</span>
                          <template v-if="promoCalc.applied_promotions && promoCalc.applied_promotions.length">
                            <div style="font-size:12px;color:#909399;margin-top:4px">
                              <div v-for="p in promoCalc.applied_promotions" :key="p.promotion_id">{{ p.promotion_name }}（{{ p.rule_display }}）</div>
                            </div>
                          </template>
                        </el-descriptions-item>
                        <el-descriptions-item label="优惠券优惠" v-if="promoCalc.applied_coupon_name || promoCalc.coupon_discount_amount > 0">
                          <span style="color:#f56c6c">- {{ formatMoney(promoCalc.coupon_discount_amount) }} 元</span>
                          <div style="font-size:12px;color:#909399;margin-top:4px" v-if="promoCalc.applied_coupon_name">{{ promoCalc.applied_coupon_name }}</div>
                        </el-descriptions-item>
                        <el-descriptions-item label="赠送金额">
                          <span style="color:#67c23a">+ {{ formatMoney(promoCalc.bonus_amount) }} 元</span>
                        </el-descriptions-item>
                        <el-descriptions-item label="应付金额">
                          <span style="font-weight:700;color:#e6a23c;font-size:16px">{{ formatMoney(promoCalc.payable_amount) }} 元</span>
                        </el-descriptions-item>
                        <el-descriptions-item label="到账金额">
                          <span style="font-weight:700;color:#409eff;font-size:16px">{{ formatMoney(promoCalc.credited_amount) }} 元</span>
                        </el-descriptions-item>
                        <el-descriptions-item v-if="promoCalc.stacking_policy && promoCalc.stacking_policy !== 'allow'" label="叠加策略">
                          {{ stackingPolicyText(promoCalc.stacking_policy) }}
                        </el-descriptions-item>
                      </el-descriptions>

                      <el-button type="primary" :loading="actionLoading" style="width: 100%" @click="submitRechargeOrder">提交充值订单</el-button>
                    </el-form>
                  </el-card>

                  <el-card class="section-card" shadow="never">
                    <h3 class="section-title">余额变动日志</h3>
                    <el-table :data="walletLogs.slice(0, 8)" stripe border empty-text="暂无余额日志">
                      <el-table-column label="时间" min-width="165">
                        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                      </el-table-column>
                      <el-table-column prop="change_type" label="类型" min-width="100" />
                      <el-table-column label="变动" min-width="110">
                        <template #default="{ row }">{{ formatMoney(row.amount_delta) }}</template>
                      </el-table-column>
                    </el-table>
                  </el-card>
                </div>
              </el-tab-pane>

              <el-tab-pane :label="isAdmin ? '订单审核' : '充值订单'" name="orders">
                <el-row :gutter="12" style="margin-bottom: 12px">
                  <el-col :span="6">
                    <el-select v-model="orderFilters.status" style="width: 100%" placeholder="按状态筛选">
                      <el-option label="全部状态" value="" />
                      <el-option label="待审核" value="pending" />
                      <el-option label="已通过" value="approved" />
                      <el-option label="已驳回" value="rejected" />
                    </el-select>
                  </el-col>
                  <el-col v-if="isAdmin" :span="6">
                    <el-input v-model="orderFilters.user_id" placeholder="按用户ID筛选" clearable />
                  </el-col>
                  <el-col :span="isAdmin ? 6 : 12">
                    <el-button @click="loadOrders">查询订单</el-button>
                  </el-col>
                  <el-col v-if="isAdmin" :span="6" style="text-align: right">
                    <el-button
                      type="success"
                      plain
                      :disabled="pendingSelectedOrders.length === 0"
                      @click="openBatchReview('approved')"
                    >
                      批量通过（{{ pendingSelectedOrders.length }}）
                    </el-button>
                    <el-button
                      type="danger"
                      plain
                      :disabled="pendingSelectedOrders.length === 0"
                      style="margin-left: 8px"
                      @click="openBatchReview('rejected')"
                    >
                      批量驳回（{{ pendingSelectedOrders.length }}）
                    </el-button>
                  </el-col>
                </el-row>

                <el-table
                  :data="orders"
                  stripe
                  border
                  empty-text="暂无订单记录"
                  class="orders-table"
                  @selection-change="handleSelectionChange"
                >
                  <el-table-column v-if="isAdmin" type="selection" width="55" :selectable="(row) => row.status === 'pending'" />
                  <el-table-column prop="order_no" label="订单号" min-width="180" />
                  <el-table-column prop="user_name" label="用户" min-width="120" />
                  <el-table-column label="面值" min-width="90">
                    <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
                  </el-table-column>
                  <el-table-column label="应付" min-width="90">
                    <template #default="{ row }">
                      <span v-if="row.final_payable !== null && row.final_payable !== undefined">¥ {{ formatMoney(row.final_payable) }}</span>
                      <span v-else>¥ {{ formatMoney(row.amount) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="到账" min-width="90">
                    <template #default="{ row }">
                      <span style="color:#409eff;font-weight:600" v-if="row.final_credited !== null && row.final_credited !== undefined">¥ {{ formatMoney(row.final_credited) }}</span>
                      <span v-else>¥ {{ formatMoney(row.amount) }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="优惠" min-width="90">
                    <template #default="{ row }">
                      <span v-if="Number(row.discount_amount || 0) > 0" style="color:#f56c6c">-¥{{ formatMoney(row.discount_amount) }}</span>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="赠送" min-width="90">
                    <template #default="{ row }">
                      <span v-if="Number(row.bonus_amount || 0) > 0" style="color:#67c23a">+¥{{ formatMoney(row.bonus_amount) }}</span>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="优惠券" min-width="110">
                    <template #default="{ row }">
                      <el-tag v-if="row.coupon_id" size="small" type="warning" effect="plain">已用券</el-tag>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="渠道" min-width="100">
                    <template #default="{ row }">{{ channelMap[row.channel] || row.channel }}</template>
                  </el-table-column>
                  <el-table-column label="状态" min-width="110">
                    <template #default="{ row }">
                      <el-tag :type="orderStatusMap[row.status]?.type || 'info'" effect="plain">
                        {{ orderStatusMap[row.status]?.label || row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="提交时间" min-width="165">
                    <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                  </el-table-column>
                  <el-table-column v-if="isAdmin" label="操作" min-width="180" fixed="right">
                    <template #default="{ row }">
                      <el-space>
                        <el-button size="small" type="success" :disabled="row.status !== 'pending'" @click="reviewOrder(row, 'approved')">通过</el-button>
                        <el-button size="small" type="danger" :disabled="row.status !== 'pending'" @click="reviewOrder(row, 'rejected')">驳回</el-button>
                      </el-space>
                    </template>
                  </el-table-column>
                </el-table>

                <el-dialog
                  v-model="batchReviewVisible"
                  :title="batchReviewAction === 'approved' ? '批量通过订单' : '批量驳回订单'"
                  width="640px"
                  :close-on-click-modal="false"
                  @close="closeBatchReviewDialog"
                >
                  <template v-if="!batchReviewResult">
                    <el-alert
                      :title="`即将对 ${pendingSelectedOrders.length} 条待审核订单执行${batchReviewAction === 'approved' ? '通过' : '驳回'}操作`"
                      type="info"
                      :closable="false"
                      show-icon
                      style="margin-bottom: 16px"
                    />
                    <el-form label-position="top">
                      <el-form-item :label="batchReviewAction === 'approved' ? '审核备注（可选）' : '驳回原因'">
                        <el-input
                          v-model="batchReviewRemark"
                          type="textarea"
                          :rows="3"
                          :placeholder="batchReviewAction === 'approved' ? '请输入统一审核备注' : '请输入统一驳回原因'"
                          maxlength="255"
                          show-word-limit
                        />
                      </el-form-item>
                    </el-form>
                    <div style="margin-top: 8px">
                      <div style="margin-bottom: 8px; font-weight: 600">已选订单预览（前 10 条）：</div>
                      <el-table :data="pendingSelectedOrders.slice(0, 10)" size="small" border max-height="240">
                        <el-table-column prop="order_no" label="订单号" min-width="160" />
                        <el-table-column prop="user_name" label="用户" min-width="100" />
                        <el-table-column label="金额" width="100">
                          <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
                        </el-table-column>
                      </el-table>
                      <div v-if="pendingSelectedOrders.length > 10" style="margin-top: 6px; color: var(--text-sub); font-size: 13px">
                        ... 还有 {{ pendingSelectedOrders.length - 10 }} 条订单未显示
                      </div>
                    </div>
                  </template>

                  <template v-else>
                    <el-result
                      :icon="batchReviewResult.failure_count === 0 ? 'success' : 'warning'"
                      :title="batchReviewResult.failure_count === 0 ? '全部处理成功' : '部分处理成功'"
                      :sub-title="`共 ${batchReviewResult.total} 条，成功 ${batchReviewResult.success_count} 条，失败 ${batchReviewResult.failure_count} 条`"
                    />
                    <el-table v-if="batchReviewResult.results.length" :data="batchReviewResult.results" size="small" border max-height="320">
                      <el-table-column prop="order_no" label="订单号" min-width="160">
                        <template #default="{ row }">
                          {{ row.order_no || `#${row.order_id}` }}
                        </template>
                      </el-table-column>
                      <el-table-column label="结果" width="90">
                        <template #default="{ row }">
                          <el-tag :type="row.success ? 'success' : 'danger'" effect="plain" size="small">
                            {{ row.success ? '成功' : '失败' }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column label="失败原因" min-width="260">
                        <template #default="{ row }">
                          <span v-if="!row.success" style="color: var(--el-color-danger)">{{ row.reason }}</span>
                          <span v-else style="color: var(--text-sub)">--</span>
                        </template>
                      </el-table-column>
                    </el-table>
                  </template>

                  <template #footer>
                    <template v-if="!batchReviewResult">
                      <el-button @click="closeBatchReviewDialog">取消</el-button>
                      <el-button :type="batchReviewAction === 'approved' ? 'success' : 'danger'" :loading="batchReviewLoading" @click="confirmBatchReview">
                        确认{{ batchReviewAction === 'approved' ? '通过' : '驳回' }}
                      </el-button>
                    </template>
                    <template v-else>
                      <el-button type="primary" @click="closeBatchReviewDialog">关闭</el-button>
                    </template>
                  </template>
                </el-dialog>
              </el-tab-pane>

              <el-tab-pane v-if="isAdmin" label="用户管理" name="users">
                <el-row :gutter="12" style="margin-bottom: 12px">
                  <el-col :span="8">
                    <el-input v-model="adminUserFilters.keyword" placeholder="搜索用户名/学号/手机号" clearable />
                  </el-col>
                  <el-col :span="6">
                    <el-select v-model="adminUserFilters.role" style="width: 100%" placeholder="角色筛选">
                      <el-option label="全部角色" value="" />
                      <el-option label="学生" value="student" />
                      <el-option label="管理员" value="admin" />
                    </el-select>
                  </el-col>
                  <el-col :span="6">
                    <el-select v-model="adminUserFilters.is_active" style="width: 100%" placeholder="状态筛选">
                      <el-option label="全部状态" value="" />
                      <el-option label="启用" value="true" />
                      <el-option label="禁用" value="false" />
                    </el-select>
                  </el-col>
                  <el-col :span="4"><el-button @click="loadAdminUsers">查询用户</el-button></el-col>
                </el-row>

                <el-table :data="adminUsers" stripe border empty-text="暂无用户数据">
                  <el-table-column prop="id" label="ID" width="70" />
                  <el-table-column prop="username" label="用户名" min-width="120" />
                  <el-table-column prop="email" label="邮箱" min-width="180" />
                  <el-table-column label="角色" min-width="140">
                    <template #default="{ row }">
                      <el-select :model-value="row.profile.role" size="small" @change="(val) => updateUserRole(row, val)">
                        <el-option label="学生" value="student" />
                        <el-option label="管理员" value="admin" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="启用" min-width="90">
                    <template #default="{ row }">
                      <el-switch :model-value="row.is_active" @change="(val) => updateUserStatus(row, val)" />
                    </template>
                  </el-table-column>
                  <el-table-column label="钱包余额" min-width="110">
                    <template #default="{ row }">¥ {{ formatMoney(row.balance) }}</template>
                  </el-table-column>
                  <el-table-column label="冻结状态" min-width="130">
                    <template #default="{ row }">
                      <el-tag :type="row.wallet_frozen ? 'danger' : 'success'" effect="plain">
                        {{ row.wallet_frozen ? '已冻结' : '正常' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="钱包操作" min-width="170" fixed="right">
                    <template #default="{ row }">
                      <el-space>
                        <el-button size="small" type="danger" plain :disabled="row.wallet_frozen" @click="walletAction(row, 'freeze')">冻结</el-button>
                        <el-button size="small" type="success" plain :disabled="!row.wallet_frozen" @click="walletAction(row, 'unfreeze')">解冻</el-button>
                      </el-space>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane :label="isAdmin ? '消费统计' : '消费统计'" :name="isAdmin ? 'consumption-admin' : 'users'">
                <el-row :gutter="12" style="margin-bottom: 12px">
                  <el-col :span="6">
                    <el-select v-model="consumptionFilters.category" style="width: 100%" placeholder="按类别筛选">
                      <el-option label="全部类别" value="" />
                      <el-option label="水费" value="water" />
                      <el-option label="电费" value="electricity" />
                    </el-select>
                  </el-col>
                  <el-col :span="6">
                    <el-date-picker v-model="consumptionFilters.start_date" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" style="width: 100%" />
                  </el-col>
                  <el-col :span="6">
                    <el-date-picker v-model="consumptionFilters.end_date" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" style="width: 100%" />
                  </el-col>
                  <el-col :span="6">
                    <el-button @click="() => Promise.all([loadConsumptions(), loadConsumptionStats()])">查询统计</el-button>
                  </el-col>
                </el-row>

                <div class="form-grid" style="margin-bottom: 14px">
                  <SimpleBarChart title="分类消费金额（元）" :items="consumeStatsForCategory()" />
                  <SimpleBarChart title="每日消费趋势（元）" :items="consumeStatsForTrend()" color="#2b9f6c" />
                </div>

                <el-table :data="consumptions" stripe border empty-text="暂无消费记录">
                  <el-table-column label="时间" min-width="165">
                    <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                  </el-table-column>
                  <el-table-column label="类别" min-width="100">
                    <template #default="{ row }">{{ categoryMap[row.category] || row.category }}</template>
                  </el-table-column>
                  <el-table-column label="用量" min-width="90">
                    <template #default="{ row }">{{ formatMoney(row.usage) }}</template>
                  </el-table-column>
                  <el-table-column label="金额" min-width="100">
                    <template #default="{ row }">¥ {{ formatMoney(row.cost_amount) }}</template>
                  </el-table-column>
                  <el-table-column prop="user_name" label="用户" min-width="120" />
                  <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
                </el-table>
              </el-tab-pane>

              <el-tab-pane :label="isAdmin ? '公告发布' : '公告通知'" name="announcements">
                <template v-if="isAdmin">
                  <el-form label-position="top" class="section-card" shadow="never" @submit.prevent>
                    <el-form-item label="公告标题">
                      <el-input v-model="announcementForm.title" placeholder="请输入公告标题" clearable />
                    </el-form-item>
                    <el-form-item label="公告内容">
                      <el-input v-model="announcementForm.content" type="textarea" :rows="4" placeholder="请输入公告内容" />
                    </el-form-item>
                    <el-form-item>
                      <el-switch v-model="announcementForm.is_active" active-text="立即生效" inactive-text="仅保存" />
                    </el-form-item>
                    <el-button type="primary" :loading="actionLoading" @click="publishAnnouncement">发布公告并推送通知</el-button>
                  </el-form>
                </template>

                <div class="table-grid" style="margin-top: 14px">
                  <el-card class="section-card" shadow="never">
                    <h3 class="section-title">公告历史</h3>
                    <el-timeline>
                      <el-timeline-item v-for="item in announcements" :key="item.id" :timestamp="formatDateTime(item.published_at)">
                        <h4 style="margin: 0 0 6px">{{ item.title }}</h4>
                        <p style="margin: 0; color: var(--text-sub)">{{ item.content }}</p>
                      </el-timeline-item>
                    </el-timeline>
                  </el-card>

                  <el-card class="section-card" shadow="never">
                    <h3 class="section-title">我的通知</h3>
                    <el-button size="small" style="margin-bottom: 8px" @click="markAllNotificationsRead">全部标记已读</el-button>
                    <el-table :data="notifications.items" stripe border empty-text="暂无通知">
                      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
                      <el-table-column label="类型" min-width="100">
                        <template #default="{ row }">{{ row.notice_type_display }}</template>
                      </el-table-column>
                      <el-table-column label="时间" min-width="165">
                        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                      </el-table-column>
                      <el-table-column label="状态" min-width="100">
                        <template #default="{ row }">
                          <el-tag :type="row.is_read ? 'info' : 'warning'" effect="plain">{{ row.is_read ? '已读' : '未读' }}</el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" min-width="90">
                        <template #default="{ row }">
                          <el-button size="small" :disabled="row.is_read" @click="markNotificationRead(row)">已读</el-button>
                        </template>
                      </el-table-column>
                    </el-table>
                  </el-card>
                </div>
              </el-tab-pane>

              <!-- ========= 月结管理（管理员） ========= -->
              <el-tab-pane v-if="isAdmin" label="月结管理" name="settlement">
                <el-card class="section-card" shadow="never" style="margin-bottom: 14px">
                  <el-row :gutter="12" align="middle">
                    <el-col :span="18">
                      <h3 class="section-title" style="margin: 0">财务月结管理</h3>
                      <p style="margin: 4px 0 0; color: var(--text-sub); font-size: 13px">
                        支持按月全量跑批、按用户重跑、发布/回滚、账实校验与跨月调整
                      </p>
                    </el-col>
                    <el-col :span="6" style="text-align: right">
                      <el-button type="primary" @click="openRunSettlementDialog">执行月结跑批</el-button>
                      <el-button type="success" plain style="margin-left: 8px" @click="openCrossMonthAdjustDialog">跨月调整</el-button>
                      <el-button type="warning" plain style="margin-left: 8px" :loading="reconciliationLoading" @click="runReconciliation">账实校验</el-button>
                    </el-col>
                  </el-row>
                </el-card>

                <el-tabs tab-position="top">
                  <el-tab-pane label="月结单列表" name="statements-list">
                    <el-row :gutter="12" style="margin-bottom: 12px">
                      <el-col :span="5">
                        <el-input v-model="settlementFilters.period" placeholder="账期 YYYY-MM" clearable />
                      </el-col>
                      <el-col :span="5">
                        <el-input v-model="settlementFilters.user_id" placeholder="用户ID" clearable />
                      </el-col>
                      <el-col :span="5">
                        <el-select v-model="settlementFilters.status" placeholder="按状态" style="width: 100%" clearable>
                          <el-option label="草稿" value="draft" />
                          <el-option label="已发布" value="published" />
                          <el-option label="已回滚" value="rolled_back" />
                        </el-select>
                      </el-col>
                      <el-col :span="9">
                        <el-button @click="loadStatements">查询</el-button>
                        <el-button plain style="margin-left: 8px" @click="() => { settlementFilters.period = ''; settlementFilters.user_id = ''; settlementFilters.status = ''; loadStatements() }">重置</el-button>
                      </el-col>
                    </el-row>

                    <el-table :data="statements" stripe border empty-text="暂无月结数据" max-height="520">
                      <el-table-column prop="user_name" label="用户" min-width="120" />
                      <el-table-column prop="period" label="账期" min-width="100" />
                      <el-table-column label="期初余额" min-width="110">
                        <template #default="{ row }">¥ {{ formatMoney(row.opening_balance) }}</template>
                      </el-table-column>
                      <el-table-column label="本月充值" min-width="110">
                        <template #default="{ row }">¥ {{ formatMoney(row.recharge_total) }} ({{ row.recharge_count }}笔)</template>
                      </el-table-column>
                      <el-table-column label="水费" min-width="100">
                        <template #default="{ row }">¥ {{ formatMoney(row.water_total) }} ({{ row.water_count }}笔)</template>
                      </el-table-column>
                      <el-table-column label="电费" min-width="100">
                        <template #default="{ row }">¥ {{ formatMoney(row.electricity_total) }} ({{ row.electricity_count }}笔)</template>
                      </el-table-column>
                      <el-table-column label="退款" min-width="100">
                        <template #default="{ row }">¥ {{ formatMoney(row.refund_total) }}</template>
                      </el-table-column>
                      <el-table-column label="跨月调整" min-width="100">
                        <template #default="{ row }">¥ {{ formatMoney(row.cross_month_adjust_total) }}</template>
                      </el-table-column>
                      <el-table-column label="期末余额" min-width="110">
                        <template #default="{ row }">¥ {{ formatMoney(row.closing_balance) }}</template>
                      </el-table-column>
                      <el-table-column label="状态" min-width="100">
                        <template #default="{ row }">
                          <el-tag :type="statementStatusMap[row.status]?.type || 'info'" effect="plain">
                            {{ statementStatusMap[row.status]?.label || row.status }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="generated_by" label="操作人" min-width="100" />
                      <el-table-column label="操作" min-width="180" fixed="right">
                        <template #default="{ row }">
                          <el-space>
                            <el-button
                              size="small"
                              type="success"
                              :disabled="row.status !== 'draft'"
                              @click="publishStatement(row)"
                            >发布</el-button>
                            <el-button
                              size="small"
                              type="danger"
                              plain
                              :disabled="row.status !== 'published'"
                              @click="rollbackStatement(row)"
                            >回滚</el-button>
                          </el-space>
                        </template>
                      </el-table-column>
                    </el-table>
                  </el-tab-pane>

                  <el-tab-pane label="跑批记录" name="runs-list">
                    <el-table :data="settlementRuns" stripe border empty-text="暂无跑批记录">
                      <el-table-column prop="id" label="ID" width="70" />
                      <el-table-column prop="period" label="账期" min-width="100" />
                      <el-table-column label="模式" min-width="110">
                        <template #default="{ row }">{{ settlementRunModeMap[row.mode] || row.mode }}</template>
                      </el-table-column>
                      <el-table-column prop="target_user_id" label="目标用户ID" min-width="110">
                        <template #default="{ row }">{{ row.target_user_id || '--' }}</template>
                      </el-table-column>
                      <el-table-column label="状态" min-width="100">
                        <template #default="{ row }">
                          <el-tag :type="settlementRunStatusMap[row.status]?.type || 'info'" effect="plain">
                            {{ settlementRunStatusMap[row.status]?.label || row.status }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="total_users" label="总数" width="80" />
                      <el-table-column prop="success_count" label="成功" width="80" />
                      <el-table-column prop="failed_count" label="失败" width="80" />
                      <el-table-column prop="triggered_by" label="触发者" min-width="110" />
                      <el-table-column label="开始时间" min-width="165">
                        <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
                      </el-table-column>
                      <el-table-column label="结束时间" min-width="165">
                        <template #default="{ row }">{{ formatDateTime(row.finished_at) }}</template>
                      </el-table-column>
                      <el-table-column prop="message" label="错误信息" min-width="240" show-overflow-tooltip />
                    </el-table>
                  </el-tab-pane>

                  <el-tab-pane label="账实校验差异" name="reconciliation-list">
                    <el-alert
                      v-if="reconciliationSummary.run_id"
                      type="info"
                      :closable="false"
                      show-icon
                      style="margin-bottom: 12px"
                    >
                      最近一次校验 run_id={{ reconciliationSummary.run_id }}，总用户 {{ reconciliationSummary.total_users }}，差异账户 {{ reconciliationSummary.diff_count }}
                    </el-alert>
                    <el-table :data="reconciliationDiffs" stripe border empty-text="暂无差异记录，可点击「账实校验」按钮执行">
                      <el-table-column prop="run_id" label="校验ID" min-width="160" />
                      <el-table-column prop="user_name" label="用户" min-width="120" />
                      <el-table-column label="钱包余额" min-width="120">
                        <template #default="{ row }">¥ {{ formatMoney(row.wallet_balance) }}</template>
                      </el-table-column>
                      <el-table-column label="重算余额" min-width="120">
                        <template #default="{ row }">¥ {{ formatMoney(row.recalculated_balance) }}</template>
                      </el-table-column>
                      <el-table-column label="差额" min-width="110">
                        <template #default="{ row }">
                          <span style="color: var(--el-color-danger); font-weight: 600">¥ {{ formatMoney(row.difference) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column prop="detail" label="详情" min-width="300" show-overflow-tooltip />
                      <el-table-column label="时间" min-width="165">
                        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                      </el-table-column>
                    </el-table>
                  </el-tab-pane>
                </el-tabs>

                <!-- 月结跑批弹窗 -->
                <el-dialog v-model="runSettlementVisible" title="执行月结跑批" width="520px" :close-on-click-modal="false">
                  <el-form label-position="top">
                    <el-form-item label="账期（YYYY-MM）" required>
                      <el-input v-model="runSettlementForm.period" placeholder="例如 2026-05" />
                    </el-form-item>
                    <el-form-item label="是否自动发布">
                      <el-switch v-model="runSettlementForm.auto_publish" active-text="生成后直接发布" inactive-text="仅生成草稿" />
                    </el-form-item>
                    <el-form-item label="指定用户ID（可选，留空则全量跑批）">
                      <el-input-number v-model="runSettlementForm.user_id" :min="1" :controls="false" style="width: 100%" placeholder="按用户重跑时填写" />
                    </el-form-item>
                  </el-form>
                  <template #footer>
                    <el-button @click="runSettlementVisible = false">取消</el-button>
                    <el-button type="primary" :loading="runSettlementLoading" @click="confirmRunSettlement">确认跑批</el-button>
                  </template>
                </el-dialog>

                <!-- 跨月调整弹窗 -->
                <el-dialog v-model="crossMonthAdjustVisible" title="跨月调整" width="520px" :close-on-click-modal="false">
                  <el-alert type="warning" :closable="false" show-icon style="margin-bottom: 14px">
                    当来源账期已发布后，若需要对该月进行退款或调整，请通过此入口将金额写入目标账期（需晚于来源账期）。
                  </el-alert>
                  <el-form label-position="top">
                    <el-form-item label="用户ID" required>
                      <el-input-number v-model="crossMonthAdjustForm.user_id" :min="1" :controls="false" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="来源账期（YYYY-MM）" required>
                      <el-input v-model="crossMonthAdjustForm.source_period" placeholder="已发布的账期，例如 2026-05" />
                    </el-form-item>
                    <el-form-item label="目标账期（YYYY-MM）" required>
                      <el-input v-model="crossMonthAdjustForm.target_period" placeholder="必须晚于来源账期，例如 2026-06" />
                    </el-form-item>
                    <el-form-item label="调整金额（元）" required>
                      <el-input-number v-model="crossMonthAdjustForm.amount" :precision="2" :step="10" style="width: 100%" placeholder="正数为补款，负数为扣款" />
                    </el-form-item>
                    <el-form-item label="调整原因">
                      <el-input v-model="crossMonthAdjustForm.remark" type="textarea" :rows="2" maxlength="255" show-word-limit />
                    </el-form-item>
                  </el-form>
                  <template #footer>
                    <el-button @click="crossMonthAdjustVisible = false">取消</el-button>
                    <el-button type="primary" :loading="crossMonthAdjustLoading" @click="confirmCrossMonthAdjust">确认调整</el-button>
                  </template>
                </el-dialog>
              </el-tab-pane>

              <!-- ========= 我的账单（学生） ========= -->
              <el-tab-pane v-if="!isAdmin" label="我的账单" name="my-statements">
                <el-card class="section-card" shadow="never">
                  <h3 class="section-title">我的月结账单</h3>
                  <p style="margin: 4px 0 14px; color: var(--text-sub); font-size: 13px">按月展示财务快照，可下载 CSV 明细</p>

                  <el-table :data="myStatements" stripe border empty-text="暂无账单记录">
                    <el-table-column prop="period" label="账期" min-width="110" />
                    <el-table-column label="期初余额" min-width="110">
                      <template #default="{ row }">¥ {{ formatMoney(row.opening_balance) }}</template>
                    </el-table-column>
                    <el-table-column label="本月充值" min-width="120">
                      <template #default="{ row }">¥ {{ formatMoney(row.recharge_total) }} ({{ row.recharge_count }}笔)</template>
                    </el-table-column>
                    <el-table-column label="水费" min-width="100">
                      <template #default="{ row }">¥ {{ formatMoney(row.water_total) }} ({{ row.water_count }}笔)</template>
                    </el-table-column>
                    <el-table-column label="电费" min-width="100">
                      <template #default="{ row }">¥ {{ formatMoney(row.electricity_total) }} ({{ row.electricity_count }}笔)</template>
                    </el-table-column>
                    <el-table-column label="退款/调整" min-width="120">
                      <template #default="{ row }">
                        ¥ {{ formatMoney(Number(row.refund_total) + Number(row.adjust_total) + Number(row.cross_month_adjust_total)) }}
                      </template>
                    </el-table-column>
                    <el-table-column label="期末余额" min-width="110">
                      <template #default="{ row }">¥ {{ formatMoney(row.closing_balance) }}</template>
                    </el-table-column>
                    <el-table-column label="状态" min-width="100">
                      <template #default="{ row }">
                        <el-tag :type="statementStatusMap[row.status]?.type || 'info'" effect="plain">
                          {{ statementStatusMap[row.status]?.label || row.status }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" min-width="200" fixed="right">
                      <template #default="{ row }">
                        <el-space>
                          <el-button size="small" type="primary" plain @click="viewStatementDetail(row.period)">查看明细</el-button>
                          <el-button size="small" type="success" :disabled="row.status !== 'published'" @click="downloadStatementCSV(row.period)">下载 CSV</el-button>
                        </el-space>
                      </template>
                    </el-table-column>
                  </el-table>
                </el-card>

                <el-dialog v-model="statementDetailVisible" :title="`账单明细 - ${selectedStatementPeriod}`" width="960px">
                  <el-skeleton :loading="statementDetailLoading" animated :rows="6">
                    <template #default>
                      <el-descriptions v-if="statementDetail.statement" :column="3" border style="margin-bottom: 16px">
                        <el-descriptions-item label="账期">{{ statementDetail.statement.period }}</el-descriptions-item>
                        <el-descriptions-item label="状态">
                          <el-tag :type="statementStatusMap[statementDetail.statement.status]?.type || 'info'" effect="plain">
                            {{ statementStatusMap[statementDetail.statement.status]?.label }}
                          </el-tag>
                        </el-descriptions-item>
                        <el-descriptions-item label="操作人">{{ statementDetail.statement.generated_by || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="期初余额">¥ {{ formatMoney(statementDetail.statement.opening_balance) }}</el-descriptions-item>
                        <el-descriptions-item label="期末余额">¥ {{ formatMoney(statementDetail.statement.closing_balance) }}</el-descriptions-item>
                        <el-descriptions-item label="流水笔数">{{ statementDetail.logs.length }}</el-descriptions-item>
                      </el-descriptions>

                      <h4 style="margin: 0 0 8px">流水明细</h4>
                      <el-table :data="statementDetail.logs" stripe border empty-text="暂无流水" max-height="380">
                        <el-table-column label="时间" min-width="165">
                          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                        </el-table-column>
                        <el-table-column label="类型" min-width="110">
                          <template #default="{ row }">{{ row.change_type_display || changeTypeMap[row.change_type] || row.change_type }}</template>
                        </el-table-column>
                        <el-table-column label="变动金额" min-width="110">
                          <template #default="{ row }">
                            <span :style="{ color: Number(row.amount_delta) >= 0 ? 'var(--el-color-success)' : 'var(--el-color-danger)' }">
                              {{ Number(row.amount_delta) >= 0 ? '+' : '' }}{{ formatMoney(row.amount_delta) }}
                            </span>
                          </template>
                        </el-table-column>
                        <el-table-column label="变动前" min-width="110">
                          <template #default="{ row }">¥ {{ formatMoney(row.balance_before) }}</template>
                        </el-table-column>
                        <el-table-column label="变动后" min-width="110">
                          <template #default="{ row }">¥ {{ formatMoney(row.balance_after) }}</template>
                        </el-table-column>
                        <el-table-column prop="operator" label="操作人" min-width="100" />
                        <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
                        <el-table-column label="已结账" min-width="80">
                          <template #default="{ row }">
                            <el-tag :type="row.is_settled ? 'success' : 'info'" effect="plain" size="small">
                              {{ row.is_settled ? '是' : '否' }}
                            </el-tag>
                          </template>
                        </el-table-column>
                      </el-table>
                    </template>
                  </el-skeleton>
                  <template #footer>
                    <el-button @click="statementDetailVisible = false">关闭</el-button>
                    <el-button
                      v-if="statementDetail.statement?.status === 'published'"
                      type="primary"
                      @click="() => downloadStatementCSV(selectedStatementPeriod)"
                    >下载 CSV</el-button>
                  </template>
                </el-dialog>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </template>
      </el-skeleton>
    </section>
  </main>
</template>
