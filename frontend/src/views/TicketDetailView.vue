<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const ticketId = computed(() => Number(route.params.id))
const isAdmin = computed(() => authStore.user?.profile?.role === 'admin')
const isStudent = computed(() => authStore.user?.profile?.role === 'student')

const loading = ref(true)
const ticket = ref(null)
const constants = ref({ categories: [], priorities: [], statuses: [] })

const replyForm = reactive({
  content: '',
  is_internal: false,
  attachments: [],
})

const ratingForm = reactive({
  rating: 0,
  comment: '',
})
const ratingDialogVisible = ref(false)

const assignDialogVisible = ref(false)
const adminUsers = ref([])
const selectedAssigneeId = ref(null)

const actionDialogVisible = ref(false)
const currentAction = ref('')
const actionRemark = ref('')

const statusMap = {
  pending: { label: '待派单', type: 'info', color: '#909399' },
  assigned: { label: '已派单', type: 'warning', color: '#e6a23c' },
  processing: { label: '处理中', type: 'primary', color: '#409eff' },
  waiting_confirm: { label: '待学生确认', type: 'warning', color: '#f56c6c' },
  completed: { label: '已完成', type: 'success', color: '#67c23a' },
  closed: { label: '已关闭', type: 'info', color: '#606266' },
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
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function formatBytes(bytes) {
  if (!bytes) return '0B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = Number(bytes)
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return size.toFixed(i === 0 ? 0 : 1) + units[i]
}

async function loadTicket() {
  loading.value = true
  try {
    const { data } = await http.get(`/tickets/${ticketId.value}/`)
    ticket.value = data
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

async function loadAdminUsers() {
  try {
    const { data } = await http.get('/tickets/assignees/')
    adminUsers.value = data
  } catch (_e) {
    adminUsers.value = []
  }
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

function getReplyIcon(actionType) {
  if (actionType === 'create') return 'Plus'
  if (actionType === 'assign') return 'User'
  if (actionType === 'status_change') return 'RefreshRight'
  if (actionType === 'rating') return 'Star'
  return 'ChatDotRound'
}

function getReplyColor(reply) {
  if (reply.action_type === 'create') return '#67c23a'
  if (reply.action_type === 'assign') return '#e6a23c'
  if (reply.action_type === 'status_change') return '#409eff'
  if (reply.action_type === 'rating') return '#f56c6c'
  if (reply.is_internal) return '#909399'
  return reply.author_role === 'admin' ? '#409eff' : '#67c23a'
}

function isReplyAction(reply) {
  return reply.action_type !== 'reply'
}

const canAssign = computed(() => isAdmin.value && ['pending', 'assigned'].includes(ticket.value?.status))
const canStartProcessing = computed(() => {
  if (!ticket.value) return false
  if (!isAdmin.value) return false
  if (!['assigned', 'waiting_confirm'].includes(ticket.value.status)) return false
  if (ticket.value.assignee && ticket.value.assignee !== authStore.user?.id) return false
  return true
})
const canRequestConfirm = computed(() => isAdmin.value && ticket.value?.status === 'processing')
const canStudentConfirm = computed(() =>
  isStudent.value && ticket.value?.status === 'waiting_confirm' && ticket.value?.student === authStore.user?.id
)
const canClose = computed(() => isAdmin.value && ticket.value?.status !== 'closed')
const canReply = computed(() => ticket.value?.status !== 'closed')
const canRate = computed(() =>
  isStudent.value && ticket.value?.status === 'completed' && ticket.value?.student === authStore.user?.id && !ticket.value?.rating
)

function openAssignDialog() {
  selectedAssigneeId.value = ticket.value?.assignee || null
  assignDialogVisible.value = true
  loadAdminUsers()
}

async function confirmAssign() {
  if (!selectedAssigneeId.value) {
    ElNotification({ title: '请选择处理人', message: '请选择要指派的处理人。', type: 'warning' })
    return
  }
  try {
    await http.post(`/tickets/${ticketId.value}/assign/`, { assignee_id: selectedAssigneeId.value })
    ElNotification({ title: '派单成功', message: '工单已指派。', type: 'success' })
    assignDialogVisible.value = false
    await loadTicket()
  } catch (_e) {}
}

function openActionDialog(action) {
  currentAction.value = action
  actionRemark.value = ''
  actionDialogVisible.value = true
}

async function confirmAction() {
  try {
    const payload = { action: currentAction.value }
    if (actionRemark.value) payload.remark = actionRemark.value
    await http.post(`/tickets/${ticketId.value}/action/`, payload)
    ElNotification({ title: '操作成功', message: '工单状态已更新。', type: 'success' })
    actionDialogVisible.value = false
    await loadTicket()
  } catch (_e) {}
}

function openRatingDialog() {
  ratingForm.rating = 0
  ratingForm.comment = ''
  ratingDialogVisible.value = true
}

async function confirmRating() {
  if (!ratingForm.rating || ratingForm.rating < 1) {
    ElNotification({ title: '请选择评分', message: '请选择 1-5 星评分。', type: 'warning' })
    return
  }
  try {
    await http.post(`/tickets/${ticketId.value}/rate/`, ratingForm)
    ElNotification({ title: '评价成功', message: '感谢您的评价！', type: 'success' })
    ratingDialogVisible.value = false
    await loadTicket()
  } catch (_e) {}
}

async function submitReply() {
  if (!replyForm.content.trim()) {
    ElNotification({ title: '请输入内容', message: '回复内容不能为空。', type: 'warning' })
    return
  }
  try {
    await http.post(`/tickets/${ticketId.value}/reply/`, {
      content: replyForm.content,
      is_internal: replyForm.is_internal,
      attachments: replyForm.attachments,
    })
    replyForm.content = ''
    replyForm.is_internal = false
    replyForm.attachments = []
    ElNotification({ title: '回复成功', message: '回复已发送。', type: 'success' })
    await loadTicket()
  } catch (_e) {}
}

function simulateImageUpload() {
  const mockImages = [
    'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=400&h=300&fit=crop',
  ]
  const url = mockImages[Math.floor(Math.random() * mockImages.length)]
  replyForm.attachments.push({
    file_name: `image_${Date.now()}.jpg`,
    file_url: url,
    file_size: Math.floor(Math.random() * 500000) + 10000,
    mime_type: 'image/jpeg',
  })
  ElNotification({ title: '已添加附件', message: '演示环境：已模拟添加图片附件。', type: 'success' })
}

function removeAttachment(idx) {
  replyForm.attachments.splice(idx, 1)
}

onMounted(async () => {
  await Promise.all([loadTicket(), loadConstants()])
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :xs="24" :sm="18">
          <h2 class="section-title">
            <el-button link type="primary" @click="router.back()" style="padding-left:0">← 返回</el-button>
            工单详情 #{{ ticketId }}
          </h2>
          <p style="margin: 4px 0 0; color: var(--text-sub)" v-if="ticket">
            {{ ticket.title }}
            <el-tag v-if="ticket.is_sla_breached" type="danger" size="small" effect="dark" style="margin-left:8px">SLA已超时</el-tag>
            <el-tag v-if="ticket.escalation_level > 0" type="warning" size="small" style="margin-left:4px">已升级 Lv.{{ ticket.escalation_level }}</el-tag>
          </p>
        </el-col>
        <el-col :xs="24" :sm="6" style="text-align: right">
          <el-button @click="loadTicket">刷新</el-button>
          <el-button v-if="canAssign" type="primary" style="margin-left:8px" @click="openAssignDialog">指派处理人</el-button>
          <el-button v-if="canStartProcessing" type="primary" style="margin-left:8px" @click="openActionDialog('start_processing')">开始处理</el-button>
          <el-button v-if="canRequestConfirm" type="success" style="margin-left:8px" @click="openActionDialog('request_confirmation')">请求学生确认</el-button>
          <el-button v-if="canStudentConfirm" type="success" style="margin-left:8px" @click="openActionDialog('student_confirm')">确认完成</el-button>
          <el-button v-if="canStudentConfirm" type="warning" style="margin-left:8px" @click="openActionDialog('student_reject')">不认可</el-button>
          <el-button v-if="canRate" type="warning" style="margin-left:8px" @click="openRatingDialog">评价工单</el-button>
          <el-button v-if="canClose" type="danger" plain style="margin-left:8px" @click="openActionDialog('close')">关闭工单</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-skeleton :loading="loading" animated :rows="12" style="margin-top:16px">
      <template #default>
        <el-row :gutter="16" style="margin-top:16px" v-if="ticket">
          <el-col :xs="24" :md="8">
            <el-card class="section-card" shadow="never">
              <h3 class="section-title" style="margin-top:0">工单信息</h3>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="状态">
                  <el-tag :type="getStatusMeta(ticket.status).type" effect="plain">
                    {{ getStatusMeta(ticket.status).label }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="类型">
                  {{ getCategoryLabel(ticket.category) }}
                </el-descriptions-item>
                <el-descriptions-item label="紧急程度">
                  <el-tag :type="getPriorityMeta(ticket.priority).type" effect="plain">
                    {{ getPriorityMeta(ticket.priority).label }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="提交学生">{{ ticket.student_name }}</el-descriptions-item>
                <el-descriptions-item label="处理人">{{ ticket.assignee_name || '未指派' }}</el-descriptions-item>
                <el-descriptions-item label="所在房间">{{ ticket.room_display }}</el-descriptions-item>
                <el-descriptions-item label="联系电话">{{ ticket.contact_phone || '--' }}</el-descriptions-item>
                <el-descriptions-item label="创建时间">{{ formatDateTime(ticket.created_at) }}</el-descriptions-item>
                <el-descriptions-item label="SLA截止">
                  <span :style="{ color: ticket.is_sla_breached ? '#f56c6c' : '' }">
                    {{ formatDateTime(ticket.sla_deadline) }}
                  </span>
                </el-descriptions-item>
                <el-descriptions-item label="派单时间" v-if="ticket.assigned_at">{{ formatDateTime(ticket.assigned_at) }}</el-descriptions-item>
                <el-descriptions-item label="处理时间" v-if="ticket.started_at">{{ formatDateTime(ticket.started_at) }}</el-descriptions-item>
                <el-descriptions-item label="解决时间" v-if="ticket.resolved_at">{{ formatDateTime(ticket.resolved_at) }}</el-descriptions-item>
                <el-descriptions-item label="关闭时间" v-if="ticket.closed_at">{{ formatDateTime(ticket.closed_at) }}</el-descriptions-item>
                <el-descriptions-item label="评分" v-if="ticket.rating">
                  <el-rate :model-value="ticket.rating" disabled size="small" />
                  <div v-if="ticket.rating_comment" style="margin-top:4px; font-size:12px; color:var(--text-sub)">{{ ticket.rating_comment }}</div>
                </el-descriptions-item>
              </el-descriptions>

              <el-divider content-position="left">问题描述</el-divider>
              <p style="white-space: pre-wrap; margin: 0; color: var(--text-regular)">{{ ticket.description }}</p>

              <template v-if="ticket.attachments && ticket.attachments.length">
                <el-divider content-position="left">附件 ({{ ticket.attachments.length }})</el-divider>
                <div class="attachment-grid">
                  <div v-for="att in ticket.attachments" :key="att.id" class="attachment-item">
                    <img v-if="att.mime_type?.startsWith('image/')" :src="att.file_url" />
                    <div v-else class="attachment-icon">📎</div>
                    <div class="attachment-name" :title="att.file_name">{{ att.file_name }}</div>
                    <div class="attachment-size">{{ formatBytes(att.file_size) }}</div>
                  </div>
                </div>
              </template>
            </el-card>
          </el-col>

          <el-col :xs="24" :md="16">
            <el-card class="section-card" shadow="never">
              <h3 class="section-title" style="margin-top:0">处理时间线</h3>
              <el-timeline style="padding-left: 8px">
                <el-timeline-item
                  v-for="reply in ticket.replies"
                  :key="reply.id"
                  :timestamp="formatDateTime(reply.created_at)"
                  placement="top"
                  :color="getReplyColor(reply)"
                >
                  <div class="timeline-header">
                    <span class="timeline-author">
                      {{ reply.author_name }}
                      <el-tag size="small" effect="plain" style="margin-left: 6px">
                        {{ reply.author_role === 'admin' ? '管理员' : '学生' }}
                      </el-tag>
                      <el-tag v-if="reply.is_internal" size="small" type="info" style="margin-left:6px">内部备注</el-tag>
                    </span>
                  </div>
                  <div class="timeline-content" :class="{ 'timeline-action': isReplyAction(reply) }">
                    <p v-if="!isReplyAction(reply)" style="white-space:pre-wrap; margin:0">{{ reply.content }}</p>
                    <p v-else style="margin:0; font-weight:500">{{ reply.content }}</p>
                  </div>
                  <div v-if="reply.attachments && reply.attachments.length" class="timeline-attachments">
                    <div v-for="att in reply.attachments" :key="att.id" class="attachment-item small">
                      <img v-if="att.mime_type?.startsWith('image/')" :src="att.file_url" />
                      <div v-else class="attachment-icon">📎</div>
                      <div class="attachment-name">{{ att.file_name }}</div>
                    </div>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </el-card>

            <el-card class="section-card" shadow="never" style="margin-top:16px" v-if="canReply">
              <h3 class="section-title" style="margin-top:0">回复</h3>
              <el-form label-position="top">
                <el-form-item>
                  <el-input
                    v-model="replyForm.content"
                    type="textarea"
                    :rows="4"
                    placeholder="请输入回复内容..."
                    maxlength="2000"
                    show-word-limit
                  />
                </el-form-item>
                <div v-if="replyForm.attachments.length" style="margin-bottom: 12px">
                  <div class="attachment-grid">
                    <div v-for="(att, idx) in replyForm.attachments" :key="idx" class="attachment-item">
                      <img v-if="att.mime_type?.startsWith('image/')" :src="att.file_url" />
                      <div v-else class="attachment-icon">📎</div>
                      <div class="attachment-name">{{ att.file_name }}</div>
                      <el-button link type="danger" size="small" @click="removeAttachment(idx)">移除</el-button>
                    </div>
                  </div>
                </div>
                <el-row justify="space-between" align="middle">
                  <el-col>
                    <el-button type="success" plain @click="simulateImageUpload">📷 添加图片（演示）</el-button>
                    <el-checkbox v-if="isAdmin" v-model="replyForm.is_internal" style="margin-left: 12px">内部备注（学生不可见）</el-checkbox>
                  </el-col>
                  <el-col>
                    <el-button type="primary" :disabled="!replyForm.content.trim()" @click="submitReply">发送回复</el-button>
                  </el-col>
                </el-row>
              </el-form>
            </el-card>
          </el-col>
        </el-row>
      </template>
    </el-skeleton>

    <!-- 指派处理人 -->
    <el-dialog v-model="assignDialogVisible" title="指派处理人" width="480px">
      <el-form label-position="top">
        <el-form-item label="选择处理人" required>
          <el-select v-model="selectedAssigneeId" style="width:100%" placeholder="请选择处理人">
            <el-option v-for="u in adminUsers" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAssign">确认指派</el-button>
      </template>
    </el-dialog>

    <!-- 通用动作对话框 -->
    <el-dialog v-model="actionDialogVisible" :title="{
      start_processing: '开始处理工单',
      request_confirmation: '请求学生确认',
      student_confirm: '确认工单已完成',
      student_reject: '不认可处理结果',
      close: '关闭工单',
    }[currentAction]" width="480px">
      <el-form label-position="top">
        <el-form-item v-if="['request_confirmation', 'student_reject', 'close'].includes(currentAction)" :label="currentAction === 'student_reject' ? '请说明不认可的原因' : (currentAction === 'close' ? '关闭原因（可选）' : '处理说明（可选）')">
          <el-input v-model="actionRemark" type="textarea" :rows="3" placeholder="请输入说明" maxlength="500" show-word-limit />
        </el-form-item>
        <el-alert v-else type="info" :closable="false" show-icon>
          确认要{{ {
            start_processing: '开始处理此工单',
            student_confirm: '确认工单已解决',
          }[currentAction] }}吗？
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAction">确认</el-button>
      </template>
    </el-dialog>

    <!-- 评分对话框 -->
    <el-dialog v-model="ratingDialogVisible" title="评价工单" width="480px">
      <el-form label-position="top">
        <el-form-item label="评分" required>
          <el-rate v-model="ratingForm.rating" size="large" />
        </el-form-item>
        <el-form-item label="评价留言（可选）">
          <el-input v-model="ratingForm.comment" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="请分享您的使用体验..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ratingDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!ratingForm.rating" @click="confirmRating">提交评价</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<style scoped>
.timeline-header {
  margin-bottom: 4px;
}
.timeline-author {
  font-weight: 600;
  color: var(--text-primary);
}
.timeline-content {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 14px;
  color: var(--text-regular);
}
.timeline-content.timeline-action {
  background: #ecf5ff;
  color: #409eff;
}
.timeline-attachments {
  margin-top: 8px;
}
.attachment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}
.attachment-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
  background: #fafafa;
  text-align: center;
  padding: 8px;
}
.attachment-item img {
  width: 100%;
  height: 80px;
  object-fit: cover;
  border-radius: 4px;
  margin-bottom: 6px;
}
.attachment-item.small img {
  height: 60px;
}
.attachment-icon {
  font-size: 40px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.attachment-name {
  font-size: 12px;
  color: var(--text-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-size {
  font-size: 11px;
  color: var(--text-sub);
}
</style>
