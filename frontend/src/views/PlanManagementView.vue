<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElNotification } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const authStore = useAuthStore()

const loading = ref(true)
const plans = ref([])
const executions = ref([])
const activeTab = ref('plans')

const planFilters = reactive({
  status: '',
  user_id: '',
})

const executionFilters = reactive({
  status: '',
  user_id: '',
  plan_id: '',
  start_date: '',
  end_date: '',
})

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

async function loadPlans() {
  try {
    const params = {}
    if (planFilters.status) params.status = planFilters.status
    if (planFilters.user_id) params.user_id = planFilters.user_id
    const { data } = await http.get('/billing/admin/plans/', { params })
    plans.value = data
  } catch (_e) {
    plans.value = []
  }
}

async function loadExecutions() {
  try {
    const params = {}
    if (executionFilters.status) params.status = executionFilters.status
    if (executionFilters.user_id) params.user_id = executionFilters.user_id
    if (executionFilters.plan_id) params.plan_id = executionFilters.plan_id
    if (executionFilters.start_date) params.start_date = executionFilters.start_date
    if (executionFilters.end_date) params.end_date = executionFilters.end_date
    const { data } = await http.get('/billing/admin/plan-executions/', { params })
    executions.value = data
  } catch (_e) {
    executions.value = []
  }
}

async function pausePlan(plan) {
  try {
    await http.post(`/billing/plans/${plan.id}/pause/`, { reason: '管理员暂停' })
    ElNotification({ title: '已暂停', message: '计划已暂停。', type: 'success' })
    await loadPlans()
  } catch (e) {
    ElNotification({ title: '暂停失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function resumePlan(plan) {
  try {
    await http.post(`/billing/plans/${plan.id}/resume/`, {})
    ElNotification({ title: '已恢复', message: '计划已恢复执行。', type: 'success' })
    await loadPlans()
  } catch (e) {
    ElNotification({ title: '恢复失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function endPlan(plan) {
  try {
    await http.post(`/billing/plans/${plan.id}/end/`, { reason: '管理员提前结束' })
    ElNotification({ title: '已结束', message: '计划已结束。', type: 'success' })
    await loadPlans()
  } catch (e) {
    ElNotification({ title: '结束失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadPlans(), loadExecutions()])
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
          <h2 class="section-title">充值计划管理</h2>
          <p style="margin: 0; color: var(--text-sub)">查看、管理所有学生的自动代扣充值计划与执行记录</p>
        </el-col>
        <el-col :span="6" style="text-align: right">
          <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回控制台</el-button>
          <el-button type="primary" @click="refreshAll">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-skeleton :loading="loading" animated :rows="6">
      <template #default>
        <el-card class="section-card" shadow="never">
          <el-tabs v-model="activeTab">
            <el-tab-pane label="计划列表" name="plans">
              <el-row :gutter="12" style="margin-bottom: 12px">
                <el-col :span="6">
                  <el-select v-model="planFilters.status" style="width: 100%" placeholder="按状态筛选" clearable>
                    <el-option label="全部状态" value="" />
                    <el-option label="执行中" value="active" />
                    <el-option label="已暂停" value="paused" />
                    <el-option label="已结束" value="ended" />
                    <el-option label="已过期" value="expired" />
                  </el-select>
                </el-col>
                <el-col :span="6">
                  <el-input v-model="planFilters.user_id" placeholder="按用户ID筛选" clearable />
                </el-col>
                <el-col :span="6">
                  <el-button @click="loadPlans">查询</el-button>
                </el-col>
              </el-row>

              <el-table :data="plans" stripe border empty-text="暂无计划">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="user_name" label="用户" min-width="120" />
                <el-table-column prop="name" label="计划名称" min-width="150" />
                <el-table-column label="金额" min-width="100">
                  <template #default="{ row }"><b>¥{{ formatMoney(row.amount) }}</b></template>
                </el-table-column>
                <el-table-column label="周期" min-width="80">
                  <template #default="{ row }">{{ periodMap[row.period] || row.period }}</template>
                </el-table-column>
                <el-table-column label="渠道" min-width="90">
                  <template #default="{ row }">{{ channelMap[row.channel] || row.channel }}</template>
                </el-table-column>
                <el-table-column label="起止日期" min-width="200">
                  <template #default="{ row }">{{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}</template>
                </el-table-column>
                <el-table-column label="下次执行" min-width="120">
                  <template #default="{ row }">
                    <span v-if="row.status === 'active'" style="color: #409eff">
                      {{ formatDate(row.next_execution_date) }}
                    </span>
                    <span v-else>--</span>
                  </template>
                </el-table-column>
                <el-table-column label="统计" min-width="160">
                  <template #default="{ row }">
                    共{{ row.total_executions || 0 }}
                    <span style="color: #67c23a">成{{ row.success_count || 0 }}</span>
                    <span style="color: #f56c6c">败{{ row.failure_count || 0 }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" min-width="90">
                  <template #default="{ row }">
                    <el-tag :type="planStatusMap[row.status]?.type || 'info'" size="small" effect="plain">
                      {{ planStatusMap[row.status]?.label || row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" min-width="220" fixed="right">
                  <template #default="{ row }">
                    <el-space>
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
            </el-tab-pane>

            <el-tab-pane label="执行历史" name="executions">
              <el-row :gutter="12" style="margin-bottom: 12px">
                <el-col :span="5">
                  <el-select v-model="executionFilters.status" style="width: 100%" placeholder="按状态筛选" clearable>
                    <el-option label="全部状态" value="" />
                    <el-option label="待处理" value="pending" />
                    <el-option label="成功" value="success" />
                    <el-option label="失败" value="failed" />
                    <el-option label="已跳过" value="skipped" />
                  </el-select>
                </el-col>
                <el-col :span="5">
                  <el-input v-model="executionFilters.user_id" placeholder="用户ID" clearable />
                </el-col>
                <el-col :span="5">
                  <el-input v-model="executionFilters.plan_id" placeholder="计划ID" clearable />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="executionFilters.start_date" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" style="width: 100%" />
                </el-col>
                <el-col :span="4">
                  <el-date-picker v-model="executionFilters.end_date" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" style="width: 100%" />
                </el-col>
                <el-col :span="5">
                  <el-button @click="loadExecutions">查询</el-button>
                </el-col>
              </el-row>

              <el-table :data="executions" stripe border empty-text="暂无执行记录">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="plan_name" label="计划名称" min-width="140" />
                <el-table-column prop="user" label="用户ID" width="80" />
                <el-table-column label="计划日期" min-width="110">
                  <template #default="{ row }">{{ formatDate(row.scheduled_date) }}</template>
                </el-table-column>
                <el-table-column label="实际执行" min-width="150">
                  <template #default="{ row }">{{ formatDateTime(row.executed_at) }}</template>
                </el-table-column>
                <el-table-column label="金额" min-width="90">
                  <template #default="{ row }">¥{{ formatMoney(row.amount) }}</template>
                </el-table-column>
                <el-table-column label="渠道" min-width="90">
                  <template #default="{ row }">{{ channelMap[row.channel] || row.channel }}</template>
                </el-table-column>
                <el-table-column label="关联订单" min-width="170">
                  <template #default="{ row }">
                    <span v-if="row.order_no" style="font-family: monospace">{{ row.order_no }}</span>
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
                <el-table-column label="失败原因" min-width="200">
                  <template #default="{ row }">
                    <span v-if="row.failure_reason" style="color: #f56c6c">{{ row.failure_reason }}</span>
                    <span v-else style="color: var(--text-sub)">--</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </template>
    </el-skeleton>
  </main>
</template>
