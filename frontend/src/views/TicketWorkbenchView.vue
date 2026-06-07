<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

import http from '../utils/http'

const router = useRouter()

const loading = ref(true)
const todos = ref([])
const constants = ref({ categories: [], priorities: [], statuses: [] })

const filters = reactive({
  status: '',
  category: '',
  priority: '',
  keyword: '',
})

const statusMap = {
  pending: { label: '待派单', type: 'info' },
  assigned: { label: '已派单', type: 'warning' },
  processing: { label: '处理中', type: 'primary' },
  waiting_confirm: { label: '待学生确认', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
}

const priorityMap = {
  low: { label: '低', type: 'info' },
  normal: { label: '普通', type: '' },
  high: { label: '高', type: 'warning' },
  urgent: { label: '紧急', type: 'danger' },
}

const categoryMap = {
  water: '水',
  electricity: '电',
  network: '网络',
  account: '账户',
  other: '其它',
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

function getStatusMeta(status) {
  return statusMap[status] || { label: status, type: 'info' }
}

function getPriorityMeta(priority) {
  return priorityMap[priority] || { label: priority, type: '' }
}

function getCategoryLabel(category) {
  return categoryMap[category] || category
}

const urgentCount = computed(() => todos.value.filter((t) => t.priority === 'urgent' || t.is_sla_breached).length)
const processingCount = computed(() => todos.value.filter((t) => t.status === 'processing').length)
const waitingCount = computed(() => todos.value.filter((t) => t.status === 'waiting_confirm').length)
const assignedCount = computed(() => todos.value.filter((t) => t.status === 'assigned').length)

async function loadTodos() {
  loading.value = true
  try {
    const params = {}
    if (filters.status) params.status = filters.status
    if (filters.category) params.category = filters.category
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.keyword = filters.keyword
    const { data } = await http.get('/tickets/my-todos/', { params })
    todos.value = data
  } finally {
    loading.value = false
  }
}

async function loadConstants() {
  try {
    const { data } = await http.get('/tickets/constants/')
    constants.value = data
  } catch (_e) {}
}

function viewTicket(row) {
  router.push(`/tickets/${row.id}`)
}

async function startProcessing(row) {
  try {
    await http.post(`/tickets/${row.id}/action/`, { action: 'start_processing' })
    ElNotification({ title: '已开始处理', message: '工单状态已更新。', type: 'success' })
    await loadTodos()
  } catch (_e) {}
}

async function requestConfirm(row) {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入处理说明（可选）',
      '请求学生确认',
      {
        confirmButtonText: '提交',
        cancelButtonText: '取消',
        inputPlaceholder: '请描述处理情况...',
        inputType: 'textarea',
      }
    ).catch(() => null)
    const payload = { action: 'request_confirmation' }
    if (value) payload.remark = value
    await http.post(`/tickets/${row.id}/action/`, payload)
    ElNotification({ title: '已请求确认', message: '已通知学生确认处理结果。', type: 'success' })
    await loadTodos()
  } catch (_e) {}
}

onMounted(async () => {
  await Promise.all([loadTodos(), loadConstants()])
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle">
        <el-col>
          <h2 class="section-title">我的待办</h2>
          <p style="margin: 4px 0 0; color: var(--text-sub)">
            指派给我处理的工单
          </p>
        </el-col>
        <el-col>
          <el-button @click="loadTodos">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="12" style="margin-top:16px">
      <el-col :xs="12" :sm="6">
        <div class="stat-card primary">
          <div class="stat-label">待办总数</div>
          <div class="stat-value">{{ todos.length }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card warning">
          <div class="stat-label">已派单待开始</div>
          <div class="stat-value">{{ assignedCount }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card info">
          <div class="stat-label">处理中</div>
          <div class="stat-value">{{ processingCount }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card danger">
          <div class="stat-label">紧急/超时</div>
          <div class="stat-value">{{ urgentCount }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card class="section-card" shadow="never" style="margin-top:16px">
      <el-row :gutter="12" style="margin-bottom:12px">
        <el-col :xs="24" :sm="4">
          <el-select v-model="filters.status" style="width:100%" placeholder="全部状态" clearable @change="loadTodos">
            <el-option label="已派单" value="assigned" />
            <el-option label="处理中" value="processing" />
            <el-option label="待学生确认" value="waiting_confirm" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="4">
          <el-select v-model="filters.category" style="width:100%" placeholder="全部类型" clearable @change="loadTodos">
            <el-option v-for="c in constants.categories" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="4">
          <el-select v-model="filters.priority" style="width:100%" placeholder="全部紧急度" clearable @change="loadTodos">
            <el-option v-for="p in constants.priorities" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-input v-model="filters.keyword" placeholder="搜索标题或描述" clearable @change="loadTodos" />
        </el-col>
        <el-col :xs="24" :sm="4" style="text-align:right">
          <el-button type="primary" @click="loadTodos">查询</el-button>
        </el-col>
      </el-row>

      <el-table :data="todos" stripe border empty-text="暂无待办工单" v-loading="loading" @row-click="viewTicket" style="cursor:pointer">
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="getPriorityMeta(row.priority).type" effect="plain" size="small">
              {{ getPriorityMeta(row.priority).label }}
            </el-tag>
            <el-tag v-if="row.is_sla_breached" type="danger" size="small" effect="dark" style="margin-left:4px">超时</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="编号" width="80">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ getCategoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusMeta(row.status).type" effect="plain" size="small">
              {{ getStatusMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="student_name" label="提交学生" width="110" />
        <el-table-column prop="room_display" label="房间" min-width="140" show-overflow-tooltip />
        <el-table-column label="SLA截止" width="150">
          <template #default="{ row }">
            <span :style="{ color: row.is_sla_breached ? '#f56c6c' : '' }">
              {{ formatDateTime(row.sla_deadline) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewTicket(row)">详情</el-button>
            <el-button
              v-if="row.status === 'assigned' || row.status === 'waiting_confirm'"
              type="success"
              link
              size="small"
              @click.stop="startProcessing(row)"
            >开始处理</el-button>
            <el-button
              v-if="row.status === 'processing'"
              type="warning"
              link
              size="small"
              @click.stop="requestConfirm(row)"
            >请求确认</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </main>
</template>

<style scoped>
.stat-card {
  padding: 16px;
  border-radius: 8px;
  color: #fff;
}
.stat-card.primary { background: linear-gradient(135deg, #409eff, #66b1ff); }
.stat-card.warning { background: linear-gradient(135deg, #e6a23c, #f3d19e); }
.stat-card.info { background: linear-gradient(135deg, #409eff, #79bbff); }
.stat-card.danger { background: linear-gradient(135deg, #f56c6c, #f89898); }
.stat-label { font-size: 13px; opacity: 0.9; }
.stat-value { font-size: 28px; font-weight: 700; margin-top: 4px; }
</style>
