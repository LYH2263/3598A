<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

import http from '../utils/http'

const activeTab = ref('message-types')
const loading = ref(false)

// ==================== 消息类型 ====================
const messageTypes = ref([])
const messageTypeDialogVisible = ref(false)
const editingMessageType = ref(null)
const messageTypeForm = reactive({
  code: '',
  name_zh: '',
  name_en: '',
  description_zh: '',
  description_en: '',
  category: 'system',
  is_enabled: true,
  default_channels: ['in_site'],
  quiet_hours_start: '',
  quiet_hours_end: '',
})

const categoryOptions = [
  { value: 'announcement', label: '系统公告' },
  { value: 'order', label: '订单通知' },
  { value: 'security', label: '安全通知' },
  { value: 'system', label: '系统消息' },
]

const channelOptions = [
  { value: 'in_site', label: '站内通知' },
  { value: 'email', label: '邮件' },
  { value: 'sms', label: '短信' },
]

async function loadMessageTypes() {
  loading.value = true
  try {
    const { data } = await http.get('/notices/message-types/')
    messageTypes.value = data
  } finally {
    loading.value = false
  }
}

function openMessageTypeCreate() {
  editingMessageType.value = null
  Object.assign(messageTypeForm, {
    code: '',
    name_zh: '',
    name_en: '',
    description_zh: '',
    description_en: '',
    category: 'system',
    is_enabled: true,
    default_channels: ['in_site'],
    quiet_hours_start: '',
    quiet_hours_end: '',
  })
  messageTypeDialogVisible.value = true
}

function openMessageTypeEdit(row) {
  editingMessageType.value = row
  Object.assign(messageTypeForm, {
    code: row.code,
    name_zh: row.name_zh,
    name_en: row.name_en,
    description_zh: row.description_zh,
    description_en: row.description_en,
    category: row.category,
    is_enabled: row.is_enabled,
    default_channels: [...row.default_channels],
    quiet_hours_start: row.quiet_hours_start ? row.quiet_hours_start.slice(0, 5) : '',
    quiet_hours_end: row.quiet_hours_end ? row.quiet_hours_end.slice(0, 5) : '',
  })
  messageTypeDialogVisible.value = true
}

async function saveMessageType() {
  if (!messageTypeForm.code || !messageTypeForm.name_zh || !messageTypeForm.name_en) {
    ElNotification({ title: '请填写完整', message: '编码、中文名、英文名为必填。', type: 'warning' })
    return
  }
  const payload = { ...messageTypeForm }
  if (!payload.quiet_hours_start || !payload.quiet_hours_end) {
    payload.quiet_hours_start = null
    payload.quiet_hours_end = null
  }
  try {
    if (editingMessageType.value) {
      await http.patch(`/notices/message-types/${editingMessageType.value.id}/`, payload)
      ElNotification({ title: '已更新', message: '消息类型已更新。', type: 'success' })
    } else {
      await http.post('/notices/message-types/', payload)
      ElNotification({ title: '已创建', message: '消息类型已创建。', type: 'success' })
    }
    messageTypeDialogVisible.value = false
    await loadMessageTypes()
  } catch (_e) { /* handled by interceptor */ }
}

async function deleteMessageType(row) {
  try {
    await ElMessageBox.confirm(`确认删除消息类型「${row.name_zh}」？相关模板和日志不会被删除，但关联会失效。`, '删除确认', {
      type: 'warning',
    })
    await http.delete(`/notices/message-types/${row.id}/`)
    ElNotification({ title: '已删除', message: '消息类型已删除。', type: 'success' })
    await loadMessageTypes()
  } catch (_e) { /* user cancelled or handled */ }
}

// ==================== 消息模板 ====================
const templates = ref([])
const templateDialogVisible = ref(false)
const editingTemplate = ref(null)
const templateForm = reactive({
  message_type: null,
  language: 'zh',
  title_template: '',
  content_template: '',
  variables_schema: '',
  is_active: true,
})

async function loadTemplates() {
  loading.value = true
  try {
    const { data } = await http.get('/notices/message-templates/')
    templates.value = data
  } finally {
    loading.value = false
  }
}

function openTemplateCreate() {
  editingTemplate.value = null
  Object.assign(templateForm, {
    message_type: messageTypes.value[0]?.id || null,
    language: 'zh',
    title_template: '',
    content_template: '',
    variables_schema: '',
    is_active: true,
  })
  templateDialogVisible.value = true
}

function openTemplateEdit(row) {
  editingTemplate.value = row
  Object.assign(templateForm, {
    message_type: row.message_type,
    language: row.language,
    title_template: row.title_template,
    content_template: row.content_template,
    variables_schema: typeof row.variables_schema === 'string' ? row.variables_schema : JSON.stringify(row.variables_schema, null, 2),
    is_active: row.is_active,
  })
  templateDialogVisible.value = true
}

async function saveTemplate() {
  if (!templateForm.message_type || !templateForm.title_template || !templateForm.content_template) {
    ElNotification({ title: '请填写完整', message: '消息类型、标题模板、内容模板为必填。', type: 'warning' })
    return
  }
  let schema = {}
  if (templateForm.variables_schema && templateForm.variables_schema.trim()) {
    try {
      schema = JSON.parse(templateForm.variables_schema)
    } catch (_e) {
      ElNotification({ title: '格式错误', message: '变量说明必须是合法 JSON。', type: 'warning' })
      return
    }
  }
  const payload = {
    message_type: templateForm.message_type,
    language: templateForm.language,
    title_template: templateForm.title_template,
    content_template: templateForm.content_template,
    variables_schema: schema,
    is_active: templateForm.is_active,
  }
  try {
    if (editingTemplate.value) {
      await http.patch(`/notices/message-templates/${editingTemplate.value.id}/`, payload)
      ElNotification({ title: '已更新', message: '模板已更新。', type: 'success' })
    } else {
      await http.post('/notices/message-templates/', payload)
      ElNotification({ title: '已创建', message: '模板已创建。', type: 'success' })
    }
    templateDialogVisible.value = false
    await loadTemplates()
  } catch (_e) { /* handled */ }
}

async function deleteTemplate(row) {
  try {
    await ElMessageBox.confirm(`确认删除该模板？`, '删除确认', { type: 'warning' })
    await http.delete(`/notices/message-templates/${row.id}/`)
    ElNotification({ title: '已删除', message: '模板已删除。', type: 'success' })
    await loadTemplates()
  } catch (_e) { /* handled */ }
}

// ==================== 发送日志 ====================
const deliveryLogs = ref([])
const logLoading = ref(false)
const logFilters = reactive({
  message_type_code: '',
  channel: '',
  status: '',
  start_date: '',
  end_date: '',
  keyword: '',
})

const logStatusOptions = [
  { value: 'pending', label: '待发送', type: 'info' },
  { value: 'success', label: '发送成功', type: 'success' },
  { value: 'failed', label: '发送失败', type: 'danger' },
  { value: 'quiet', label: '静默跳过', type: 'warning' },
  { value: 'skipped', label: '偏好跳过', type: 'info' },
]

const logChannelOptions = [
  { value: 'in_site', label: '站内通知' },
  { value: 'email', label: '邮件' },
  { value: 'sms', label: '短信' },
]

async function loadDeliveryLogs() {
  logLoading.value = true
  try {
    const params = {}
    if (logFilters.message_type_code) params.message_type_code = logFilters.message_type_code
    if (logFilters.channel) params.channel = logFilters.channel
    if (logFilters.status) params.status = logFilters.status
    if (logFilters.start_date) params.start_date = logFilters.start_date
    if (logFilters.end_date) params.end_date = logFilters.end_date
    if (logFilters.keyword) params.keyword = logFilters.keyword
    const { data } = await http.get('/notices/delivery-logs/', { params })
    deliveryLogs.value = data
  } finally {
    logLoading.value = false
  }
}

async function retryDelivery(log) {
  try {
    await ElMessageBox.confirm(`确认重发该条消息？渠道：${log.channel_display}，目标用户：${log.username}`, '重发确认', { type: 'warning' })
    const { data } = await http.post(`/notices/delivery-logs/${log.id}/retry/`)
    ElNotification({
      title: '重发完成',
      message: `状态：${data.status_display}${data.error_message ? `，错误：${data.error_message}` : ''}`,
      type: data.status === 'success' ? 'success' : 'warning',
    })
    await loadDeliveryLogs()
  } catch (_e) { /* handled */ }
}

function exportDeliveryLogs() {
  const params = new URLSearchParams()
  if (logFilters.message_type_code) params.set('message_type_code', logFilters.message_type_code)
  if (logFilters.channel) params.set('channel', logFilters.channel)
  if (logFilters.status) params.set('status', logFilters.status)
  if (logFilters.start_date) params.set('start_date', logFilters.start_date)
  if (logFilters.end_date) params.set('end_date', logFilters.end_date)

  http.get(`/notices/delivery-logs/export/?${params.toString()}`, { responseType: 'blob' }).then((res) => {
    const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8-sig' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    const ts = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19)
    link.download = `delivery_logs_${ts}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
    ElNotification({ title: '导出完成', message: 'CSV 已下载。', type: 'success' })
  }).catch((e) => {
    ElNotification({ title: '导出失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  })
}

function getLogStatusMeta(status) {
  return logStatusOptions.find((o) => o.value === status) || { label: status, type: 'info' }
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
    second: '2-digit',
    hour12: false,
  }).format(date)
}

// ==================== 通用 ====================
async function refreshAll() {
  const tasks = [loadMessageTypes(), loadTemplates()]
  if (activeTab.value === 'delivery-logs') tasks.push(loadDeliveryLogs())
  await Promise.all(tasks)
}

onMounted(async () => {
  await loadMessageTypes()
  await loadTemplates()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle">
        <el-col>
          <h2 class="section-title">消息中心管理</h2>
          <p style="margin: 4px 0 0; color: var(--text-sub)">配置消息类型、多语言模板，查看发送日志并支持重发与导出。</p>
        </el-col>
        <el-col>
          <el-button @click="refreshAll">刷新数据</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <el-tabs v-model="activeTab">
        <!-- ========= 消息类型 ========= -->
        <el-tab-pane label="消息类型" name="message-types">
          <el-row justify="space-between" style="margin-bottom: 12px">
            <el-col>
              <span style="color: var(--text-sub); font-size: 13px">共 {{ messageTypes.length }} 种消息类型</span>
            </el-col>
            <el-col>
              <el-button type="primary" @click="openMessageTypeCreate">新建消息类型</el-button>
            </el-col>
          </el-row>

          <el-table :data="messageTypes" stripe border empty-text="暂无消息类型" v-loading="loading">
            <el-table-column prop="code" label="编码" min-width="160" />
            <el-table-column label="名称" min-width="200">
              <template #default="{ row }">
                <div style="font-weight: 600">{{ row.name_zh }}</div>
                <div style="color: var(--text-sub); font-size: 12px">{{ row.name_en }}</div>
              </template>
            </el-table-column>
            <el-table-column label="分类" width="110">
              <template #default="{ row }">
                {{ categoryOptions.find((o) => o.value === row.category)?.label || row.category }}
              </template>
            </el-table-column>
            <el-table-column label="默认渠道" min-width="200">
              <template #default="{ row }">
                <el-tag
                  v-for="c in row.default_channels"
                  :key="c"
                  size="small"
                  type="info"
                  effect="plain"
                  style="margin-right: 4px"
                >
                  {{ channelOptions.find((o) => o.value === c)?.label || c }}
                </el-tag>
                <span v-if="!row.default_channels.length" style="color: var(--text-sub)">无</span>
              </template>
            </el-table-column>
            <el-table-column label="静默时段" width="140">
              <template #default="{ row }">
                <span v-if="row.quiet_hours_start && row.quiet_hours_end">
                  {{ row.quiet_hours_start.slice(0, 5) }} - {{ row.quiet_hours_end.slice(0, 5) }}
                </span>
                <span v-else style="color: var(--text-sub)">未设置</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled ? 'success' : 'info'" effect="plain" size="small">
                  {{ row.is_enabled ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模板" width="80" align="center">
              <template #default="{ row }">{{ row.templates?.length || 0 }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-space>
                  <el-button size="small" @click="openMessageTypeEdit(row)">编辑</el-button>
                  <el-button size="small" type="danger" plain @click="deleteMessageType(row)">删除</el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ========= 消息模板 ========= -->
        <el-tab-pane label="消息模板" name="message-templates">
          <el-row justify="space-between" style="margin-bottom: 12px">
            <el-col>
              <span style="color: var(--text-sub); font-size: 13px">共 {{ templates.length }} 个模板</span>
            </el-col>
            <el-col>
              <el-button type="primary" @click="openTemplateCreate">新建模板</el-button>
            </el-col>
          </el-row>

          <el-table :data="templates" stripe border empty-text="暂无模板" v-loading="loading">
            <el-table-column prop="message_type_code" label="消息类型" min-width="160" />
            <el-table-column label="语言" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.language === 'zh' ? 'primary' : 'success'" effect="plain">
                  {{ row.language === 'zh' ? '中文' : 'English' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title_template" label="标题模板" min-width="220" show-overflow-tooltip />
            <el-table-column prop="content_template" label="内容模板" min-width="300" show-overflow-tooltip />
            <el-table-column label="变量说明" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <code v-if="row.variables_schema && Object.keys(row.variables_schema).length" style="font-size: 12px">
                  {{ typeof row.variables_schema === 'string' ? row.variables_schema : JSON.stringify(row.variables_schema) }}
                </code>
                <span v-else style="color: var(--text-sub)">无变量</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain" size="small">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-space>
                  <el-button size="small" @click="openTemplateEdit(row)">编辑</el-button>
                  <el-button size="small" type="danger" plain @click="deleteTemplate(row)">删除</el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ========= 发送日志 ========= -->
        <el-tab-pane label="发送日志" name="delivery-logs">
          <el-row :gutter="12" style="margin-bottom: 12px">
            <el-col :span="4">
              <el-input v-model="logFilters.message_type_code" placeholder="消息类型编码" clearable />
            </el-col>
            <el-col :span="3">
              <el-select v-model="logFilters.channel" placeholder="渠道" style="width: 100%" clearable>
                <el-option v-for="o in logChannelOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-col>
            <el-col :span="3">
              <el-select v-model="logFilters.status" placeholder="状态" style="width: 100%" clearable>
                <el-option v-for="o in logStatusOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-col>
            <el-col :span="3">
              <el-date-picker v-model="logFilters.start_date" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" style="width: 100%" />
            </el-col>
            <el-col :span="3">
              <el-date-picker v-model="logFilters.end_date" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" style="width: 100%" />
            </el-col>
            <el-col :span="4">
              <el-input v-model="logFilters.keyword" placeholder="用户/标题/事件ID" clearable />
            </el-col>
            <el-col :span="4" style="text-align: right">
              <el-button @click="loadDeliveryLogs">查询</el-button>
              <el-button type="success" plain @click="exportDeliveryLogs">导出 CSV</el-button>
            </el-col>
          </el-row>

          <el-table :data="deliveryLogs" stripe border empty-text="暂无发送日志" v-loading="logLoading">
            <el-table-column prop="event_id" label="事件ID" min-width="180" show-overflow-tooltip />
            <el-table-column prop="username" label="用户" width="120" />
            <el-table-column prop="message_type_code" label="消息类型" min-width="160" />
            <el-table-column label="渠道" width="100">
              <template #default="{ row }">{{ row.channel_display }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="getLogStatusMeta(row.status).type" effect="plain" size="small">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="rendered_title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="rendered_content" label="内容" min-width="260" show-overflow-tooltip />
            <el-table-column label="重试" width="70" align="center">
              <template #default="{ row }">{{ row.retry_count }}</template>
            </el-table-column>
            <el-table-column label="发送时间" width="165">
              <template #default="{ row }">{{ formatDateTime(row.sent_at) }}</template>
            </el-table-column>
            <el-table-column label="创建时间" width="165">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="错误" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.error_message" style="color: var(--el-color-danger)">{{ row.error_message }}</span>
                <span v-else style="color: var(--text-sub)">--</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :disabled="row.status === 'success'"
                  @click="retryDelivery(row)"
                >重发</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 消息类型对话框 -->
    <el-dialog v-model="messageTypeDialogVisible" :title="editingMessageType ? '编辑消息类型' : '新建消息类型'" width="640px">
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="编码（唯一）" required>
              <el-input v-model="messageTypeForm.code" :disabled="!!editingMessageType" placeholder="如 order_approved" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类">
              <el-select v-model="messageTypeForm.category" style="width: 100%">
                <el-option v-for="o in categoryOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="中文名" required>
              <el-input v-model="messageTypeForm.name_zh" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="英文名" required>
              <el-input v-model="messageTypeForm.name_en" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="中文描述">
              <el-input v-model="messageTypeForm.description_zh" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="英文描述">
              <el-input v-model="messageTypeForm.description_en" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="默认启用渠道">
          <el-checkbox-group v-model="messageTypeForm.default_channels">
            <el-checkbox v-for="opt in channelOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="10">
            <el-form-item label="静默时段开始（邮件/短信）">
              <el-time-picker v-model="messageTypeForm.quiet_hours_start" value-format="HH:mm" placeholder="如 22:00" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="静默时段结束">
              <el-time-picker v-model="messageTypeForm.quiet_hours_end" value-format="HH:mm" placeholder="如 08:00" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="4" style="display: flex; align-items: center">
            <el-switch v-model="messageTypeForm.is_enabled" active-text="启用" inactive-text="停用" />
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="messageTypeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMessageType">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模板对话框 -->
    <el-dialog v-model="templateDialogVisible" :title="editingTemplate ? '编辑消息模板' : '新建消息模板'" width="640px">
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="消息类型" required>
              <el-select v-model="templateForm.message_type" style="width: 100%" :disabled="!!editingTemplate">
                <el-option v-for="mt in messageTypes" :key="mt.id" :label="`${mt.code} · ${mt.name_zh}`" :value="mt.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="语言">
              <el-select v-model="templateForm.language" style="width: 100%" :disabled="!!editingTemplate">
                <el-option label="中文" value="zh" />
                <el-option label="English" value="en" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6" style="display: flex; align-items: center; justify-content: flex-end">
            <el-switch v-model="templateForm.is_active" active-text="启用" inactive-text="停用" />
          </el-col>
        </el-row>
        <el-form-item label="标题模板（支持 {variable} 占位）" required>
          <el-input v-model="templateForm.title_template" placeholder="如：订单 {order_no} 审核通过" />
        </el-form-item>
        <el-form-item label="内容模板（支持 {variable} 占位）" required>
          <el-input v-model="templateForm.content_template" type="textarea" :rows="5" placeholder="如：您的订单 {order_no} 已审核通过，金额 ¥{amount} 已入账。" />
        </el-form-item>
        <el-form-item label="变量说明 JSON（可选）">
          <el-input
            v-model="templateForm.variables_schema"
            type="textarea"
            :rows="3"
            placeholder='如：{ "order_no": "订单号", "amount": "金额" }'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>
