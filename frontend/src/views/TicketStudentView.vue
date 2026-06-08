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

const filters = reactive({
  status: '',
  category: '',
  priority: '',
  keyword: '',
})

const createDialogVisible = ref(false)
const createForm = reactive({
  title: '',
  description: '',
  category: '',
  priority: 'normal',
  room_id: null,
  room_text: '',
  contact_phone: '',
  attachments: [],
})

const myStay = ref(null)

const statusMap = {
  pending: { label: '待派单', type: 'info' },
  assigned: { label: '已派单', type: 'warning' },
  processing: { label: '处理中', type: 'primary' },
  waiting_confirm: { label: '待确认', type: 'warning' },
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

const activeCount = computed(() => stats.value.total - stats.value.closed)

async function loadTickets() {
  loading.value = true
  try {
    const params = {}
    if (filters.status) params.status = filters.status
    if (filters.category) params.category = filters.category
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.keyword = filters.keyword
    const { data } = await http.get('/tickets/', { params })
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

async function loadMyStay() {
  try {
    const { data } = await http.get('/housing/stays/my/current/')
    myStay.value = data || null
    if (myStay.value?.bed?.room?.id) {
      createForm.room_id = myStay.value.bed.room.id
      createForm.room_text = myStay.value.bed.room.display_name || ''
    }
  } catch (_e) {
    myStay.value = null
  }
}

function openCreateDialog() {
  Object.assign(createForm, {
    title: '',
    description: '',
    category: '',
    priority: 'normal',
    room_id: myStay.value?.bed?.room?.id || null,
    room_text: '',
    contact_phone: '',
    attachments: [],
  })
  createDialogVisible.value = true
}

const fileInputRef = ref(null)
const uploading = ref(false)
const MAX_ATTACHMENTS = 5
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/jpg']
const ALLOWED_EXT = ['.jpg', '.jpeg', '.png']
const MAX_SIZE = 10 * 1024 * 1024

function triggerFileSelect() {
  if (createForm.attachments.length >= MAX_ATTACHMENTS) {
    ElNotification({ title: '数量超限', message: `最多上传 ${MAX_ATTACHMENTS} 张图片。`, type: 'warning' })
    return
  }
  fileInputRef.value?.click()
}

async function handleFileChange(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  for (const file of files) {
    if (createForm.attachments.length >= MAX_ATTACHMENTS) {
      ElNotification({ title: '数量超限', message: `最多上传 ${MAX_ATTACHMENTS} 张图片。`, type: 'warning' })
      break
    }
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXT.includes(ext)) {
      ElNotification({ title: '格式不支持', message: `${file.name} 不是 JPG/PNG 图片。`, type: 'warning' })
      continue
    }
    if (file.size > MAX_SIZE) {
      ElNotification({ title: '文件过大', message: `${file.name} 超过 10MB 限制。`, type: 'warning' })
      continue
    }
    await uploadFile(file)
  }
  if (fileInputRef.value) fileInputRef.value.value = ''
}

async function uploadFile(file) {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await http.post('/tickets/attachments/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    createForm.attachments.push(data)
    ElNotification({ title: '上传成功', message: `${file.name} 已添加。`, type: 'success' })
  } catch (err) {
    const msg = err?.response?.data?.detail || '上传失败，请重试。'
    ElNotification({ title: '上传失败', message: msg, type: 'error' })
  } finally {
    uploading.value = false
  }
}

async function removeAttachment(idx) {
  const att = createForm.attachments[idx]
  if (!att) return
  if (att.id) {
    try {
      await http.delete(`/tickets/attachments/${att.id}/`)
    } catch (_e) {}
  }
  createForm.attachments.splice(idx, 1)
}

async function submitCreate() {
  if (!createForm.title.trim()) {
    ElNotification({ title: '请填写标题', message: '请输入工单标题。', type: 'warning' })
    return
  }
  if (!createForm.description.trim()) {
    ElNotification({ title: '请填写描述', message: '请输入问题描述。', type: 'warning' })
    return
  }
  if (!createForm.category) {
    ElNotification({ title: '请选择类型', message: '请选择工单类型。', type: 'warning' })
    return
  }
  if (!createForm.room_id && !createForm.room_text.trim()) {
    ElNotification({ title: '请填写房间', message: '请选择房间或手填房间信息。', type: 'warning' })
    return
  }

  try {
    const payload = {
      title: createForm.title.trim(),
      description: createForm.description.trim(),
      category: createForm.category,
      priority: createForm.priority,
      room_text: createForm.room_text.trim(),
      contact_phone: createForm.contact_phone.trim(),
      attachment_ids: createForm.attachments.map((a) => a.id).filter(Boolean),
    }
    if (createForm.room_id) payload.room_id = createForm.room_id
    const { data } = await http.post('/tickets/', payload)
    ElNotification({ title: '提交成功', message: '工单已提交，请等待管理员处理。', type: 'success' })
    createDialogVisible.value = false
    await Promise.all([loadTickets(), loadStats()])
    router.push(`/tickets/${data.id}`)
  } catch (_e) {}
}

function viewTicket(row) {
  router.push(`/tickets/${row.id}`)
}

function formatBytes(bytes) {
  if (!bytes) return '0B'
  const units = ['B', 'KB', 'MB']
  let i = 0
  let size = Number(bytes)
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return size.toFixed(i === 0 ? 0 : 1) + units[i]
}

onMounted(async () => {
  await Promise.all([loadTickets(), loadStats(), loadConstants(), loadMyStay()])
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle">
        <el-col>
          <h2 class="section-title">我的工单</h2>
          <p style="margin: 4px 0 0; color: var(--text-sub)">
            提交报修和反馈问题，跟踪处理进度
          </p>
        </el-col>
        <el-col>
          <el-button @click="loadTickets">刷新</el-button>
          <el-button type="primary" style="margin-left:8px" @click="openCreateDialog">+ 发起工单</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="12" style="margin-top:16px">
      <el-col :xs="12" :sm="6">
        <div class="stat-card primary">
          <div class="stat-label">进行中</div>
          <div class="stat-value">{{ activeCount }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card warning">
          <div class="stat-label">待处理</div>
          <div class="stat-value">{{ stats.pending + stats.assigned }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card success">
          <div class="stat-label">已完成</div>
          <div class="stat-value">{{ stats.completed }}</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card danger">
          <div class="stat-label">超时</div>
          <div class="stat-value">{{ stats.sla_breached }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card class="section-card" shadow="never" style="margin-top:16px">
      <el-row :gutter="12" style="margin-bottom:12px">
        <el-col :xs="24" :sm="4">
          <el-select v-model="filters.status" style="width:100%" placeholder="全部状态" clearable @change="loadTickets">
            <el-option v-for="s in constants.statuses" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="4">
          <el-select v-model="filters.category" style="width:100%" placeholder="全部类型" clearable @change="loadTickets">
            <el-option v-for="c in constants.categories" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="4">
          <el-select v-model="filters.priority" style="width:100%" placeholder="全部紧急度" clearable @change="loadTickets">
            <el-option v-for="p in constants.priorities" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-input v-model="filters.keyword" placeholder="搜索标题或描述" clearable @change="loadTickets" />
        </el-col>
        <el-col :xs="24" :sm="4" style="text-align:right">
          <el-button @click="loadTickets">查询</el-button>
        </el-col>
      </el-row>

      <el-table :data="tickets" stripe border empty-text="暂无工单" v-loading="loading" @row-click="viewTicket" style="cursor:pointer">
        <el-table-column prop="id" label="编号" width="80">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ getCategoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="紧急程度" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityMeta(row.priority).type" effect="plain" size="small">
              {{ getPriorityMeta(row.priority).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusMeta(row.status).type" effect="plain" size="small">
              {{ getStatusMeta(row.status).label }}
            </el-tag>
            <el-tag v-if="row.is_sla_breached" type="danger" size="small" effect="dark" style="margin-left:4px">超时</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处理人" width="110">
          <template #default="{ row }">{{ row.assignee_name || '未指派' }}</template>
        </el-table-column>
        <el-table-column prop="room_display" label="房间" width="140" show-overflow-tooltip />
        <el-table-column label="评分" width="110">
          <template #default="{ row }">
            <el-rate v-if="row.rating" :model-value="row.rating" disabled size="small" />
            <span v-else style="color:var(--text-sub)">--</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="viewTicket(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建工单对话框 -->
    <el-dialog v-model="createDialogVisible" title="发起工单" width="640px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" placeholder="简要描述问题，如：302宿舍水龙头漏水" maxlength="200" show-word-limit />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="类型" required>
              <el-select v-model="createForm.category" style="width:100%" placeholder="请选择类型">
                <el-option v-for="c in constants.categories" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="紧急程度" required>
              <el-select v-model="createForm.priority" style="width:100%">
                <el-option v-for="p in constants.priorities" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="联系电话">
              <el-input v-model="createForm.contact_phone" placeholder="可选，方便处理人联系" maxlength="20" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="所在房间">
              <el-select v-if="myStay?.bed?.room" v-model="createForm.room_id" style="width:100%" placeholder="从入住信息选择" clearable>
                <el-option :label="myStay.bed.room.building_name + ' ' + myStay.bed.room.room_no + ' (' + myStay.bed.bed_no + ')'" :value="myStay.bed.room.id" />
              </el-select>
              <el-input v-else model-value="(无入住信息，请手填)" disabled />
              <div v-if="myStay" style="margin-top:4px; font-size:12px; color:var(--text-sub)">
                当前入住：{{ myStay.bed?.room?.building_name || '' }} {{ myStay.bed?.room?.room_no || '' }} {{ myStay.bed?.bed_no || '' }}
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="或手填房间信息">
              <el-input v-model="createForm.room_text" placeholder="如未绑定入住，手填楼栋和房间号" maxlength="128" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="问题描述" required>
          <el-input v-model="createForm.description" type="textarea" :rows="5" placeholder="请详细描述问题情况..." maxlength="2000" show-word-limit />
        </el-form-item>

        <el-form-item label="图片附件">
          <input
            ref="fileInputRef"
            type="file"
            accept="image/jpeg,image/png,image/jpg"
            multiple
            style="display:none"
            @change="handleFileChange"
          />
          <div v-if="createForm.attachments.length" class="attachment-grid" style="margin-bottom:12px">
            <div v-for="(att, idx) in createForm.attachments" :key="att.id || idx" class="attachment-item">
              <img v-if="att.mime_type?.startsWith('image/')" :src="att.file_url" style="cursor:pointer" @click="window.open(att.file_url, '_blank')" />
              <div class="attachment-name" :title="att.file_name">{{ att.file_name }}</div>
              <div class="attachment-size">{{ formatBytes(att.file_size) }}</div>
              <el-button link type="danger" size="small" @click="removeAttachment(idx)">移除</el-button>
            </div>
          </div>
          <el-button type="success" plain :loading="uploading" @click="triggerFileSelect">
            📷 选择图片上传
          </el-button>
          <span style="margin-left:12px; font-size:12px; color:var(--text-sub)">
            支持 JPG/PNG，最多 {{ MAX_ATTACHMENTS }} 张，单张不超过 10MB（{{ createForm.attachments.length }}/{{ MAX_ATTACHMENTS }}）
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">提交工单</el-button>
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
.stat-card.success { background: linear-gradient(135deg, #67c23a, #95d475); }
.stat-card.danger { background: linear-gradient(135deg, #f56c6c, #f89898); }
.stat-label { font-size: 13px; opacity: 0.9; }
.stat-value { font-size: 28px; font-weight: 700; margin-top: 4px; }
.attachment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 10px;
}
.attachment-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 6px;
  text-align: center;
  background: #fafafa;
}
.attachment-item img {
  width: 100%;
  height: 70px;
  object-fit: cover;
  border-radius: 4px;
  margin-bottom: 4px;
}
.attachment-name {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-size {
  font-size: 11px;
  color: var(--text-sub);
}
</style>
