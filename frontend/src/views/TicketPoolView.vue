<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

import http from '../utils/http'

const router = useRouter()

const loading = ref(true)
const tickets = ref([])
const stats = ref({ total: 0, pending: 0, assigned: 0, processing: 0, waiting_confirm: 0, completed: 0, closed: 0, sla_breached: 0 })
const constants = ref({ categories: [], priorities: [], statuses: [] })
const buildings = ref([])
const adminUsers = ref([])

const filters = reactive({
  status: '',
  category: '',
  priority: '',
  building_id: '',
  keyword: '',
  unassigned_only: false,
})

const batchAssignVisible = ref(false)
const selectedTickets = ref([])
const batchAssigneeId = ref(null)

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

async function loadTickets() {
  loading.value = true
  try {
    const params = {}
    if (filters.status) params.status = filters.status
    if (filters.category) params.category = filters.category
    if (filters.priority) params.priority = filters.priority
    if (filters.building_id) params.building_id = filters.building_id
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.unassigned_only) params.unassigned_only = 'true'
    const { data } = await http.get('/tickets/pool/', { params })
    tickets.value = data
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const { data } = await http.get('/tickets/stats/')
    stats.value = data
  } catch (_e) {}
}

async function loadConstants() {
  try {
    const { data } = await http.get('/tickets/constants/')
    constants.value = data
  } catch (_e) {}
}

async function loadBuildings() {
  try {
    const { data } = await http.get('/housing/buildings/')
    buildings.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (_e) {
    buildings.value = []
  }
}

async function loadAdminUsers() {
  try {
    const { data } = await http.get('/tickets/assignees/')
    adminUsers.value = data
  } catch (_e) {
    adminUsers.value = []
  }
}

async function runSLACheck() {
  try {
    const { data } = await http.post('/tickets/sla-check/')
    ElNotification({ title: 'SLA检查完成', message: data.detail || `已升级 ${data.checked_count} 个工单。`, type: 'success' })
    await Promise.all([loadTickets(), loadStats()])
  } catch (_e) {}
}

function viewTicket(row) {
  router.push(`/tickets/${row.id}`)
}

async function quickAssign(row) {
  try {
    const { value } = await ElMessageBox.prompt(
      `请选择要指派工单 #${row.id}「${row.title}」的处理人`,
      '指派处理人',
      {
        confirmButtonText: '确认指派',
        cancelButtonText: '取消',
        inputPattern: /\d+/,
        inputErrorMessage: '请输入处理人ID',
        inputPlaceholder: '输入处理人ID，或直接打开详情页指派',
      }
    ).catch(() => null)
    if (!value) return
    await http.post(`/tickets/${row.id}/assign/`, { assignee_id: Number(value) })
    ElNotification({ title: '指派成功', message: '工单已指派。', type: 'success' })
    await loadTickets()
  } catch (_e) {}
}

function handleSelectionChange(selection) {
  selectedTickets.value = selection.filter((t) => t.status === 'pending' || t.status === 'assigned')
}

function openBatchAssign() {
  if (selectedTickets.value.length === 0) {
    ElNotification({ title: '请选择工单', message: '请先勾选要批量指派的工单。', type: 'warning' })
    return
  }
  batchAssigneeId.value = null
  batchAssignVisible.value = true
}

async function confirmBatchAssign() {
  if (!batchAssigneeId.value) {
    ElNotification({ title: '请选择处理人', message: '请选择要指派的处理人。', type: 'warning' })
    return
  }
  const results = { success: 0, failed: 0 }
  for (const t of selectedTickets.value) {
    try {
      await http.post(`/tickets/${t.id}/assign/`, { assignee_id: batchAssigneeId.value })
      results.success++
    } catch (_e) {
      results.failed++
    }
  }
  ElNotification({
    title: '批量指派完成',
    message: `成功 ${results.success} 条，失败 ${results.failed} 条。`,
    type: results.failed === 0 ? 'success' : 'warning',
  })
  batchAssignVisible.value = false
  selectedTickets.value = []
  await loadTickets()
}

onMounted(async () => {
  await Promise.all([loadTickets(), loadStats(), loadConstants(), loadBuildings(), loadAdminUsers()])
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle">
        <el-col>
          <h2 class="section-title">工单池</h2>
          <p style="margin: 4px 0 0; color: var(--text-sub)">
            全部工单管理，支持多维度筛选与批量指派
          </p>
        </el-col>
        <el-col>
          <el-button @click="loadTickets">刷新</el-button>
          <el-button type="warning" plain style="margin-left:8px" @click="runSLACheck">SLA 检查</el-button>
          <el-button type="primary" style="margin-left:8px" :disabled="selectedTickets.length === 0" @click="openBatchAssign">
            批量指派（{{ selectedTickets.length }}）
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="12" style="margin-top:16px">
      <el-col :xs="12" :sm="4">
        <div class="stat-card primary">
          <div class="stat-label">工单总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="4">
        <div class="stat-card warning">
          <div class="stat-label">待派单</div>
          <div class="stat-value">{{ stats.pending }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="4">
        <div class="stat-card info">
          <div class="stat-label">处理中</div>
          <div class="stat-value">{{ stats.assigned + stats.processing }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="4">
        <div class="stat-card success">
          <div class="stat-label">已完成</div>
          <div class="stat-value">{{ stats.completed }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="4">
        <div class="stat-card info-2">
          <div class="stat-label">待确认</div>
          <div class="stat-value">{{ stats.waiting_confirm }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="4">
        <div class="stat-card danger">
          <div class="stat-label">超时工单</div>
          <div class="stat-value">{{ stats.sla_breached }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card class="section-card" shadow="never" style="margin-top:16px">
      <el-row :gutter="12" style="margin-bottom:12px">
        <el-col :xs="24" :sm="4">
          <el-select v-model="filters.status" style="width:100%" placeholder="全部状态" clearable @change="loadTickets" multiple collapse-tags collapse-tags-tooltip>
            <el-option v-for="s in constants.statuses" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="3">
          <el-select v-model="filters.category" style="width:100%" placeholder="全部类型" clearable @change="loadTickets">
            <el-option v-for="c in constants.categories" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="3">
          <el-select v-model="filters.priority" style="width:100%" placeholder="全部紧急度" clearable @change="loadTickets">
            <el-option v-for="p in constants.priorities" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="3">
          <el-select v-model="filters.building_id" style="width:100%" placeholder="全部楼栋" clearable @change="loadTickets">
            <el-option v-for="b in buildings" :key="b.id" :label="b.campus_name + ' - ' + b.name" :value="String(b.id)" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="5">
          <el-input v-model="filters.keyword" placeholder="搜索标题/描述/学生" clearable @change="loadTickets" />
        </el-col>
        <el-col :xs="24" :sm="6" style="text-align:right">
          <el-checkbox v-model="filters.unassigned_only" style="margin-right:12px" @change="loadTickets">仅看未派单</el-checkbox>
          <el-button type="primary" @click="loadTickets">查询</el-button>
        </el-col>
      </el-row>

      <el-table
        :data="tickets"
        stripe
        border
        empty-text="暂无工单"
        v-loading="loading"
        @row-click="viewTicket"
        style="cursor:pointer"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" :selectable="(row) => row.status === 'pending' || row.status === 'assigned'" />
        <el-table-column prop="id" label="编号" width="80">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column label="紧急程度" width="90">
          <template #default="{ row }">
            <el-tag :type="getPriorityMeta(row.priority).type" effect="plain" size="small">
              {{ getPriorityMeta(row.priority).label }}
            </el-tag>
            <el-tag v-if="row.escalation_level > 0" type="warning" size="small" effect="dark" style="margin-left:4px">Lv.{{ row.escalation_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ getCategoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusMeta(row.status).type" effect="plain" size="small">
              {{ getStatusMeta(row.status).label }}
            </el-tag>
            <el-tag v-if="row.is_sla_breached" type="danger" size="small" effect="dark" style="margin-left:4px">超时</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="student_name" label="学生" width="110" />
        <el-table-column label="处理人" width="110">
          <template #default="{ row }">
            <span v-if="row.assignee_name">{{ row.assignee_name }}</span>
            <el-tag v-else type="info" size="small" effect="plain">未指派</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="room_display" label="房间" min-width="140" show-overflow-tooltip />
        <el-table-column label="回复" width="70" align="center">
          <template #default="{ row }">{{ row.reply_count || 0 }}</template>
        </el-table-column>
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
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewTicket(row)">详情</el-button>
            <el-button
              v-if="row.status === 'pending' || row.status === 'assigned'"
              type="success"
              link
              size="small"
              @click.stop="quickAssign(row)"
            >指派</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 批量指派对话框 -->
    <el-dialog v-model="batchAssignVisible" title="批量指派处理人" width="480px">
      <el-alert
        :title="`已选 ${selectedTickets.length} 条工单，将统一指派给以下处理人`"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-form label-position="top">
        <el-form-item label="选择处理人" required>
          <el-select v-model="batchAssigneeId" style="width:100%" placeholder="请选择处理人">
            <el-option v-for="u in adminUsers" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchAssignVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!batchAssigneeId" @click="confirmBatchAssign">确认指派</el-button>
      </template>
    </el-dialog>
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
.stat-card.info-2 { background: linear-gradient(135deg, #909399, #a6a9ad); }
.stat-card.success { background: linear-gradient(135deg, #67c23a, #95d475); }
.stat-card.danger { background: linear-gradient(135deg, #f56c6c, #f89898); }
.stat-label { font-size: 13px; opacity: 0.9; }
.stat-value { font-size: 28px; font-weight: 700; margin-top: 4px; }
</style>
