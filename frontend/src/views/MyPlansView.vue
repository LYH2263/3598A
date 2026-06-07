<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessageBox, ElNotification } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const authStore = useAuthStore()

const loading = ref(true)
const plans = ref([])
const upcoming = ref([])
const selectedPlan = ref(null)
const executions = ref([])
const detailVisible = ref(false)
const detailLoading = ref(false)

const createVisible = ref(false)
const createLoading = ref(false)
const planForm = reactive({
  name: '',
  amount: null,
  period: 'weekly',
  channel: 'alipay',
  start_date: '',
  end_date: '',
  failure_action: 'skip',
})

const activeFilter = ref('')

const planStatusMap = {
  active: { label: '执行中', type: 'success' },
  paused: { label: '已暂停', type: 'warning' },
  ended: { label: '已结束', type: 'info' },
  expired: { label: '已过期', type: 'info' },
}

const periodMap = {
  daily: '每日',
  weekly: '每周',
  monthly: '每月',
}

const channelMap = {
  alipay: '支付宝',
  wechat: '微信支付',
  bank: '银行卡',
}

const failureActionMap = {
  skip: '跳过本次继续执行',
  pause: '暂停计划等待处理',
}

const execStatusMap = {
  pending: { label: '待处理', type: 'info' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  skipped: { label: '已跳过', type: 'warning' },
}

function formatMoney(value) {
  const v = Number(value ?? 0)
  if (Number.isNaN(v)) return '0.00'
  return v.toFixed(2)
}

function formatDateTime(value) {
  if (!value) return '--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(d)
}

function formatDate(value) {
  if (!value) return '--'
  return String(value)
}

function todayPlusDays(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const filteredPlans = computed(() => {
  if (!activeFilter.value) return plans.value
  return plans.value.filter(p => p.status === activeFilter.value)
})

async function loadPlans() {
  try {
    const params = {}
    if (activeFilter.value) params.status = activeFilter.value
    const { data } = await http.get('/billing/plans/', { params })
    plans.value = data
  } catch (_e) {
    plans.value = []
  }
}

async function loadUpcoming() {
  try {
    const { data } = await http.get('/billing/plans/upcoming/', { params: { days: 7 } })
    upcoming.value = data.upcoming || []
  } catch (_e) {
    upcoming.value = []
  }
}

function openCreateDialog() {
  planForm.name = ''
  planForm.amount = null
  planForm.period = 'weekly'
  planForm.channel = 'alipay'
  planForm.start_date = todayPlusDays(0)
  planForm.end_date = todayPlusDays(30)
  planForm.failure_action = 'skip'
  createVisible.value = true
}

async function confirmCreatePlan() {
  if (!planForm.amount || Number(planForm.amount) <= 0) {
    ElNotification({ title: '请填写金额', message: '请输入有效的充值金额。', type: 'warning' })
    return
  }
  if (!planForm.start_date || !planForm.end_date) {
    ElNotification({ title: '请选择日期', message: '请选择计划的起止日期。', type: 'warning' })
    return
  }
  createLoading.value = true
  try {
    await http.post('/billing/plans/', {
      name: planForm.name || '自动充值计划',
      amount: planForm.amount,
      period: planForm.period,
      channel: planForm.channel,
      start_date: planForm.start_date,
      end_date: planForm.end_date,
      failure_action: planForm.failure_action,
    })
    ElNotification({ title: '计划已创建', message: '系统将按计划自动生成充值订单。', type: 'success' })
    createVisible.value = false
    await Promise.all([loadPlans(), loadUpcoming()])
  } finally {
    createLoading.value = false
  }
}

async function pausePlan(plan) {
  try {
    await ElMessageBox.confirm(`确认暂停计划「${plan.name}」？`, '暂停计划', {
      confirmButtonText: '确认暂停', cancelButtonText: '取消', type: 'warning',
    })
  } catch (_e) { return }
  try {
    await http.post(`/billing/plans/${plan.id}/pause/`, { reason: '用户主动暂停' })
    ElNotification({ title: '已暂停', message: '计划已暂停，可随时恢复。', type: 'success' })
    await Promise.all([loadPlans(), loadUpcoming()])
  } catch (e) {
    ElNotification({ title: '暂停失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function resumePlan(plan) {
  try {
    await http.post(`/billing/plans/${plan.id}/resume/`, {})
    ElNotification({ title: '已恢复', message: '计划已恢复执行。', type: 'success' })
    await Promise.all([loadPlans(), loadUpcoming()])
  } catch (e) {
    ElNotification({ title: '恢复失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function endPlan(plan) {
  const result = await ElMessageBox.prompt(
    `请输入提前结束计划「${plan.name}」的原因（可选）`,
    '提前结束计划',
    { confirmButtonText: '确认结束', cancelButtonText: '取消', type: 'warning', inputPlaceholder: '请输入原因' }
  ).catch(() => null)
  if (!result) return
  try {
    await http.post(`/billing/plans/${plan.id}/end/`, { reason: result.value || '用户提前结束' })
    ElNotification({ title: '已结束', message: '计划已提前结束。', type: 'success' })
    await Promise.all([loadPlans(), loadUpcoming()])
  } catch (e) {
    ElNotification({ title: '结束失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function viewPlanDetail(plan) {
  selectedPlan.value = plan
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await http.get(`/billing/plans/${plan.id}/`)
    selectedPlan.value = data.plan
    executions.value = data.executions || []
  } finally {
    detailLoading.value = false
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadPlans(), loadUpcoming()])
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) {
    try { await authStore.fetchMe() } catch (_e) { return }
  }
  await refreshAll()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :span="18">
          <h2 class="section-title">我的充值计划</h2>
          <p style="margin: 0; color: var(--text-sub)">创建自动代扣计划，系统按周期自动生成充值订单进入审批流</p>
        </el-col>
        <el-col :span="6" style="text-align: right">
          <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回控制台</el-button>
          <el-button style="margin-right: 8px" @click="refreshAll">刷新</el-button>
          <el-button type="primary" @click="openCreateDialog">创建计划</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-skeleton :loading="loading" animated :rows="6">
      <template #default>
        <el-card v-if="upcoming.length > 0" class="section-card upcoming-card" shadow="never">
          <el-row justify="space-between" align="middle" :gutter="12">
            <el-col :span="18">
              <h3 class="section-title" style="margin: 0">
                <el-icon style="color: #e6a23c; margin-right: 6px"><AlarmClock /></el-icon>
                未来 7 天即将执行
              </h3>
              <p style="margin: 4px 0 0; color: var(--text-sub)">以下计划将在最近一周自动生成充值订单</p>
            </el-col>
          </el-row>
          <div class="upcoming-list" style="margin-top: 14px">
            <div v-for="u in upcoming" :key="u.plan_id" class="upcoming-item">
              <div class="upcoming-left">
                <div class="upcoming-countdown">{{ u.countdown_text }}</div>
                <div class="upcoming-date">{{ u.next_execution_date }}</div>
              </div>
              <div class="upcoming-divider" />
              <div class="upcoming-right">
                <div class="upcoming-name">{{ u.plan_name }}</div>
                <div class="upcoming-info">
                  <span>¥{{ formatMoney(u.amount) }}</span>
                  <span class="upcoming-dot">·</span>
                  <span>{{ u.period_display }}</span>
                  <span class="upcoming-dot">·</span>
                  <span>{{ channelMap[u.channel] || u.channel }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-card>

        <el-card class="section-card" shadow="never">
          <el-row :gutter="12" style="margin-bottom: 12px">
            <el-col :span="18">
              <el-radio-group v-model="activeFilter" size="default">
                <el-radio-button label="">全部</el-radio-button>
                <el-radio-button label="active">执行中</el-radio-button>
                <el-radio-button label="paused">已暂停</el-radio-button>
                <el-radio-button label="ended">已结束</el-radio-button>
                <el-radio-button label="expired">已过期</el-radio-button>
              </el-radio-group>
            </el-col>
          </el-row>

          <div v-if="filteredPlans.length === 0" style="padding: 40px 0; text-align: center">
            <el-empty description="暂无充值计划，点击右上角「创建计划」开始使用" />
          </div>

          <el-table v-else :data="filteredPlans" stripe border empty-text="暂无计划">
            <el-table-column prop="name" label="计划名称" min-width="160" />
            <el-table-column label="每次金额" min-width="110">
              <template #default="{ row }"><b>¥{{ formatMoney(row.amount) }}</b></template>
            </el-table-column>
            <el-table-column label="周期" min-width="90">
              <template #default="{ row }">{{ periodMap[row.period] || row.period }}</template>
            </el-table-column>
            <el-table-column label="渠道" min-width="100">
              <template #default="{ row }">{{ channelMap[row.channel] || row.channel }}</template>
            </el-table-column>
            <el-table-column label="起止日期" min-width="220">
              <template #default="{ row }">
                {{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}
              </template>
            </el-table-column>
            <el-table-column label="下次执行" min-width="160">
              <template #default="{ row }">
                <div v-if="row.status === 'active'" style="color: #409eff">
                  {{ formatDate(row.next_execution_date) }}
                  <div style="font-size: 12px; color: var(--text-sub); margin-top: 2px">
                    {{ row.countdown_text || '' }}
                  </div>
                </div>
                <span v-else style="color: var(--text-sub)">--</span>
              </template>
            </el-table-column>
            <el-table-column label="执行统计" min-width="180">
              <template #default="{ row }">
                共 {{ row.total_executions || 0 }} 次
                <span style="color: #67c23a">成功 {{ row.success_count || 0 }}</span>
                <span style="color: #f56c6c; margin-left: 6px">失败 {{ row.failure_count || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" min-width="100">
              <template #default="{ row }">
                <el-tag :type="planStatusMap[row.status]?.type || 'info'" effect="plain">
                  {{ planStatusMap[row.status]?.label || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" min-width="260" fixed="right">
              <template #default="{ row }">
                <el-space>
                  <el-button size="small" type="primary" plain @click="viewPlanDetail(row)">详情</el-button>
                  <el-button
                    v-if="row.status === 'active'"
                    size="small"
                    type="warning"
                    @click="pausePlan(row)"
                  >暂停</el-button>
                  <el-button
                    v-if="row.status === 'paused'"
                    size="small"
                    type="success"
                    @click="resumePlan(row)"
                  >恢复</el-button>
                  <el-button
                    v-if="row.status === 'active' || row.status === 'paused'"
                    size="small"
                    type="danger"
                    plain
                    @click="endPlan(row)"
                  >结束</el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </template>
    </el-skeleton>

    <el-dialog v-model="createVisible" title="创建充值计划" width="560px" :close-on-click-modal="false">
      <el-form :model="planForm" label-position="top" @submit.prevent>
        <el-form-item label="计划名称（可选）">
          <el-input v-model="planForm.name" placeholder="例如：每月话费充值" maxlength="100" show-word-limit />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="每次充值金额（元）" required>
              <el-input-number v-model="planForm.amount" :min="1" :precision="2" :step="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="充值渠道" required>
              <el-select v-model="planForm.channel" style="width: 100%">
                <el-option label="支付宝" value="alipay" />
                <el-option label="微信支付" value="wechat" />
                <el-option label="银行卡" value="bank" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="执行周期" required>
          <el-radio-group v-model="planForm.period">
            <el-radio-button label="daily">每日</el-radio-button>
            <el-radio-button label="weekly">每周</el-radio-button>
            <el-radio-button label="monthly">每月</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="开始日期" required>
              <el-date-picker v-model="planForm.start_date" value-format="YYYY-MM-DD" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" required>
              <el-date-picker v-model="planForm.end_date" value-format="YYYY-MM-DD" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="执行失败时">
          <el-radio-group v-model="planForm.failure_action">
            <el-radio-button label="skip">跳过本次，下次继续</el-radio-button>
            <el-radio-button label="pause">暂停计划，等待处理</el-radio-button>
          </el-radio-group>
          <div style="font-size: 12px; color: var(--text-sub); margin-top: 4px">
            账户冻结、订单被驳回等情况下按此策略处理
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="confirmCreatePlan">创建计划</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" :title="selectedPlan ? `计划详情 - ${selectedPlan.name}` : '计划详情'" width="780px">
      <el-skeleton :loading="detailLoading" animated :rows="4">
        <template #default>
          <el-descriptions v-if="selectedPlan" :column="2" border size="small" style="margin-bottom: 16px">
            <el-descriptions-item label="计划名称">{{ selectedPlan.name }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="planStatusMap[selectedPlan.status]?.type || 'info'" effect="plain">
                {{ planStatusMap[selectedPlan.status]?.label || selectedPlan.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="每次金额">¥{{ formatMoney(selectedPlan.amount) }}</el-descriptions-item>
            <el-descriptions-item label="执行周期">{{ periodMap[selectedPlan.period] || selectedPlan.period }}</el-descriptions-item>
            <el-descriptions-item label="充值渠道">{{ channelMap[selectedPlan.channel] || selectedPlan.channel }}</el-descriptions-item>
            <el-descriptions-item label="失败策略">{{ failureActionMap[selectedPlan.failure_action] || selectedPlan.failure_action }}</el-descriptions-item>
            <el-descriptions-item label="起止日期">{{ formatDate(selectedPlan.start_date) }} ~ {{ formatDate(selectedPlan.end_date) }}</el-descriptions-item>
            <el-descriptions-item label="下次执行">
              <span v-if="selectedPlan.status === 'active'" style="color: #409eff">
                {{ formatDate(selectedPlan.next_execution_date) }}（{{ selectedPlan.countdown_text || '' }}）
              </span>
              <span v-else>--</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(selectedPlan.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="执行统计">
              共 {{ selectedPlan.total_executions || 0 }} 次，
              <span style="color: #67c23a">成功 {{ selectedPlan.success_count || 0 }}</span>，
              <span style="color: #f56c6c">失败 {{ selectedPlan.failure_count || 0 }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <h4 style="margin: 0 0 10px">执行历史</h4>
          <el-table :data="executions" stripe border empty-text="暂无执行记录" size="small" max-height="360">
            <el-table-column label="计划日期" min-width="120">
              <template #default="{ row }">{{ formatDate(row.scheduled_date) }}</template>
            </el-table-column>
            <el-table-column label="实际执行" min-width="160">
              <template #default="{ row }">{{ formatDateTime(row.executed_at) }}</template>
            </el-table-column>
            <el-table-column label="金额" min-width="100">
              <template #default="{ row }">¥{{ formatMoney(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="渠道" min-width="100">
              <template #default="{ row }">{{ channelMap[row.channel] || row.channel }}</template>
            </el-table-column>
            <el-table-column label="关联订单" min-width="180">
              <template #default="{ row }">
                <span v-if="row.order_no">{{ row.order_no }}</span>
                <span v-else style="color: var(--text-sub)">--</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" min-width="90">
              <template #default="{ row }">
                <el-tag :type="execStatusMap[row.status]?.type || 'info'" size="small" effect="plain">
                  {{ execStatusMap[row.status]?.label || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="失败原因" min-width="180">
              <template #default="{ row }">
                <span v-if="row.failure_reason" style="color: #f56c6c">{{ row.failure_reason }}</span>
                <span v-else style="color: var(--text-sub)">--</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </el-skeleton>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script>
import { AlarmClock } from '@element-plus/icons-vue'
export default { components: { AlarmClock } }
</script>

<style scoped>
.upcoming-card {
  border: 1px solid #faecd8;
  background: linear-gradient(135deg, #fdf6ec, #fef9f4);
}

.upcoming-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.upcoming-item {
  display: flex;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  min-height: 72px;
}

.upcoming-left {
  width: 100px;
  background: linear-gradient(135deg, #e6a23c, #f56c6c);
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 10px;
}

.upcoming-countdown {
  font-size: 18px;
  font-weight: 700;
}

.upcoming-date {
  font-size: 12px;
  opacity: 0.9;
  margin-top: 2px;
}

.upcoming-divider {
  width: 1px;
  background: repeating-linear-gradient(
    to bottom, #ebeef5 0, #ebeef5 4px, transparent 4px, transparent 10px
  );
}

.upcoming-right {
  flex: 1;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.upcoming-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.upcoming-info {
  font-size: 12px;
  color: #606266;
}

.upcoming-dot {
  margin: 0 6px;
  color: #c0c4cc;
}
</style>
