<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const authStore = useAuthStore()

const loading = ref(true)
const activeTab = ref('strategies')
const strategies = ref([])
const housingTree = ref([])

const filters = reactive({
  category: '',
  scope_type: '',
  is_active: '',
})

const strategyTypeMap = {
  fixed: { label: '固定单价', type: '' },
  tiered: { label: '阶梯单价', type: 'warning' },
  timeslot: { label: '时段单价', type: 'success' },
}

const categoryMap = {
  water: '水费',
  electricity: '电费',
}

const scopeTypeMap = {
  global: '全校默认',
  campus: '校区',
  building: '楼栋',
  room: '房间',
}

const effectiveStatusMap = {
  active: { label: '生效中', type: 'success' },
  pending: { label: '未生效', type: 'warning' },
  expired: { label: '已过期', type: 'info' },
  inactive: { label: '已停用', type: 'danger' },
}

const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

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
  if (!value) return '长期'
  return String(value)
}

function weekdayMaskToText(mask) {
  if (!mask || mask.length !== 7) return '每天'
  const days = []
  for (let i = 0; i < 7; i++) {
    if (mask[i] === '1') days.push(weekdayLabels[i])
  }
  if (days.length === 7) return '每天'
  return days.join('、')
}

async function loadHousingTree() {
  try {
    const { data } = await http.get('/housing/tree/')
    housingTree.value = data
  } catch (_e) {
    housingTree.value = []
  }
}

async function loadStrategies() {
  try {
    const params = {}
    if (filters.category) params.category = filters.category
    if (filters.scope_type) params.scope_type = filters.scope_type
    if (filters.is_active) params.is_active = filters.is_active
    const { data } = await http.get('/billing/pricing/strategies/', { params })
    strategies.value = data
  } catch (_e) {
    strategies.value = []
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadStrategies(), loadHousingTree()])
  } finally {
    loading.value = false
  }
}

// ============= 策略编辑弹窗 =============
const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingId = ref(null)
const form = reactive({
  name: '',
  description: '',
  strategy_type: 'fixed',
  category: 'electricity',
  scope_type: 'global',
  campus: null,
  building: null,
  room: null,
  effective_from: '',
  effective_to: null,
  is_active: true,
  priority: 0,
  tiers: [{ min_usage: '0.00', max_usage: null, unit_price: '0.00', sort_order: 0 }],
  timeslots: [{ name: '默认', weekday_mask: '1111111', start_time: '00:00:00', end_time: '23:59:59', unit_price: '0.00', sort_order: 0 }],
})

const formRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择适用类目', trigger: 'change' }],
  strategy_type: [{ required: true, message: '请选择策略类型', trigger: 'change' }],
  scope_type: [{ required: true, message: '请选择生效维度', trigger: 'change' }],
  effective_from: [{ required: true, message: '请选择生效开始日期', trigger: 'change' }],
}

function resetForm() {
  Object.assign(form, {
    name: '',
    description: '',
    strategy_type: 'fixed',
    category: 'electricity',
    scope_type: 'global',
    campus: null,
    building: null,
    room: null,
    effective_from: new Date().toISOString().slice(0, 10),
    effective_to: null,
    is_active: true,
    priority: 0,
    tiers: [{ min_usage: '0.00', max_usage: null, unit_price: '0.00', sort_order: 0 }],
    timeslots: [{ name: '默认', weekday_mask: '1111111', start_time: '00:00:00', end_time: '23:59:59', unit_price: '0.00', sort_order: 0 }],
  })
}

function openCreateDialog() {
  dialogMode.value = 'create'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(row) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    strategy_type: row.strategy_type,
    category: row.category,
    scope_type: row.scope_type,
    campus: row.campus,
    building: row.building,
    room: row.room,
    effective_from: row.effective_from,
    effective_to: row.effective_to,
    is_active: row.is_active,
    priority: row.priority,
    tiers: row.tiers?.length ? row.tiers.map((t) => ({ ...t })) : [{ min_usage: '0.00', max_usage: null, unit_price: '0.00', sort_order: 0 }],
    timeslots: row.timeslots?.length ? row.timeslots.map((s) => ({ ...s })) : [{ name: '默认', weekday_mask: '1111111', start_time: '00:00:00', end_time: '23:59:59', unit_price: '0.00', sort_order: 0 }],
  })
  dialogVisible.value = true
}

function addTier() {
  const last = form.tiers[form.tiers.length - 1]
  form.tiers.push({
    min_usage: last?.max_usage || '0.00',
    max_usage: null,
    unit_price: last?.unit_price || '0.00',
    sort_order: form.tiers.length,
  })
}

function removeTier(idx) {
  if (form.tiers.length <= 1) {
    ElMessage.warning('至少保留一个分段')
    return
  }
  form.tiers.splice(idx, 1)
}

function addTimeslot() {
  form.timeslots.push({
    name: `时段${form.timeslots.length + 1}`,
    weekday_mask: '1111111',
    start_time: '08:00:00',
    end_time: '18:00:00',
    unit_price: '0.00',
    sort_order: form.timeslots.length,
  })
}

function removeTimeslot(idx) {
  if (form.timeslots.length <= 1) {
    ElMessage.warning('至少保留一个时段')
    return
  }
  form.timeslots.splice(idx, 1)
}

function toggleWeekday(slot, idx) {
  const arr = slot.weekday_mask.split('')
  arr[idx] = arr[idx] === '1' ? '0' : '1'
  slot.weekday_mask = arr.join('')
}

async function submitForm(formRef) {
  if (!formRef) return
  await formRef.validate()
  try {
    const payload = { ...form }
    if (form.strategy_type === 'timeslot') {
      delete payload.tiers
    } else {
      delete payload.timeslots
    }
    if (dialogMode.value === 'create') {
      await http.post('/billing/pricing/strategies/', payload)
      ElNotification({ title: '创建成功', message: '价格策略已创建。', type: 'success' })
    } else {
      await http.put(`/billing/pricing/strategies/${editingId.value}/`, payload)
      ElNotification({ title: '更新成功', message: '价格策略已更新。', type: 'success' })
    }
    dialogVisible.value = false
    await loadStrategies()
  } catch (e) {
    // error handled by interceptor
  }
}

async function deleteStrategy(row) {
  try {
    await ElMessageBox.confirm(`确认删除策略「${row.name}」？此操作不可恢复。`, '删除确认', { type: 'warning' })
    await http.delete(`/billing/pricing/strategies/${row.id}/`)
    ElNotification({ title: '已删除', message: '价格策略已删除。', type: 'success' })
    await loadStrategies()
  } catch (_e) {
    // cancelled
  }
}

// ============= 价格预览工具 =============
const previewForm = reactive({
  user_id: null,
  room_id: null,
  category: 'electricity',
  usage: null,
  at_time: null,
})
const previewResult = ref(null)
const previewLoading = ref(false)

const campusOptions = ref([])
const buildingOptions = ref([])
const roomOptions = ref([])

function buildSpaceOptions() {
  const campuses = []
  const buildings = []
  const rooms = []
  for (const c of housingTree.value) {
    campuses.push({ value: c.id, label: c.name })
    for (const b of c.children || []) {
      buildings.push({ value: b.id, label: `${c.name} - ${b.name}`, campus_id: c.id })
      for (const f of b.children || []) {
        for (const r of f.children || []) {
          rooms.push({ value: r.id, label: `${b.name} - ${r.room_no}`, building_id: b.id })
        }
      }
    }
  }
  campusOptions.value = campuses
  buildingOptions.value = buildings
  roomOptions.value = rooms
}

function displayCategory(cat) {
  return categoryMap[cat] || cat
}
function displayUnit(cat) {
  return cat === 'water' ? '吨' : (cat === 'electricity' ? '度' : '')
}
function resultTypeLabel(type) {
  return strategyTypeMap[type]?.label || type
}
function resultTypeTagType(type) {
  return strategyTypeMap[type]?.type || 'info'
}

async function runPreview() {
  if (!previewForm.usage || Number(previewForm.usage) <= 0) {
    ElMessage.warning('请输入有效用量')
    return
  }
  previewLoading.value = true
  previewResult.value = null
  try {
    const payload = {
      category: previewForm.category,
      usage: Number(previewForm.usage),
      compare: true,
    }
    if (previewForm.user_id) payload.user_id = previewForm.user_id
    if (previewForm.room_id) payload.room_id = previewForm.room_id
    if (previewForm.at_time) payload.at_time = previewForm.at_time
    const { data } = await http.post('/billing/pricing/preview/', payload)
    previewResult.value = data
  } catch (_e) {
    previewResult.value = null
  } finally {
    previewLoading.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) {
    try { await authStore.fetchMe() } catch (_e) { return }
  }
  await refreshAll()
  buildSpaceOptions()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :span="18">
          <h2 class="section-title">价格管理中心</h2>
          <p style="margin: 0; color: var(--text-sub)">维护水电价格策略（固定/阶梯/时段），支持按校区/楼栋/房间维度生效，及价格预览工具</p>
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
            <!-- ============= 策略列表 ============= -->
            <el-tab-pane label="价格策略" name="strategies">
              <el-row :gutter="12" style="margin-bottom: 12px">
                <el-col :span="5">
                  <el-select v-model="filters.category" style="width: 100%" placeholder="按类目筛选" clearable>
                    <el-option label="全部类目" value="" />
                    <el-option label="水费" value="water" />
                    <el-option label="电费" value="electricity" />
                  </el-select>
                </el-col>
                <el-col :span="5">
                  <el-select v-model="filters.scope_type" style="width: 100%" placeholder="按生效维度" clearable>
                    <el-option label="全部维度" value="" />
                    <el-option label="全校默认" value="global" />
                    <el-option label="校区" value="campus" />
                    <el-option label="楼栋" value="building" />
                    <el-option label="房间" value="room" />
                  </el-select>
                </el-col>
                <el-col :span="5">
                  <el-select v-model="filters.is_active" style="width: 100%" placeholder="按状态" clearable>
                    <el-option label="全部状态" value="" />
                    <el-option label="已启用" value="true" />
                    <el-option label="已停用" value="false" />
                  </el-select>
                </el-col>
                <el-col :span="9" style="text-align: right">
                  <el-button @click="loadStrategies">查询</el-button>
                  <el-button type="primary" style="margin-left: 8px" @click="openCreateDialog">+ 新建策略</el-button>
                </el-col>
              </el-row>

              <el-table :data="strategies" stripe border empty-text="暂无策略">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="name" label="策略名称" min-width="160" show-overflow-tooltip />
                <el-table-column label="类型" min-width="100">
                  <template #default="{ row }">
                    <el-tag :type="strategyTypeMap[row.strategy_type]?.type || 'info'" size="small" effect="plain">
                      {{ strategyTypeMap[row.strategy_type]?.label || row.strategy_type }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="类目" min-width="80">
                  <template #default="{ row }">{{ categoryMap[row.category] || row.category }}</template>
                </el-table-column>
                <el-table-column label="生效维度" min-width="160">
                  <template #default="{ row }">
                    {{ row.scope_label || scopeTypeMap[row.scope_type] || row.scope_type }}
                  </template>
                </el-table-column>
                <el-table-column label="生效时间" min-width="200">
                  <template #default="{ row }">
                    {{ formatDate(row.effective_from) }} ~ {{ formatDate(row.effective_to) }}
                  </template>
                </el-table-column>
                <el-table-column prop="priority" label="优先级" width="80" />
                <el-table-column label="启停" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
                      {{ row.is_active ? '启用' : '停用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="生效状态" min-width="100">
                  <template #default="{ row }">
                    <el-tag
                      :type="(effectiveStatusMap[row.effective_status] || effectiveStatusMap.inactive).type"
                      size="small" effect="dark">
                      {{ row.effective_status_label || (effectiveStatusMap[row.effective_status] || effectiveStatusMap.inactive).label }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="详情" min-width="240">
                  <template #default="{ row }">
                    <template v-if="row.strategy_type === 'fixed' && row.tiers?.length">
                      单价：¥{{ formatMoney(row.tiers[0].unit_price) }}
                    </template>
                    <template v-else-if="row.strategy_type === 'tiered' && row.tiers?.length">
                      <div v-for="(t, idx) in row.tiers" :key="idx" style="font-size: 12px">
                        [{{ formatMoney(t.min_usage) }}, {{ t.max_usage ? formatMoney(t.max_usage) : '∞' }})
                        @ ¥{{ formatMoney(t.unit_price) }}
                      </div>
                    </template>
                    <template v-else-if="row.strategy_type === 'timeslot' && row.timeslots?.length">
                      <div v-for="(s, idx) in row.timeslots" :key="idx" style="font-size: 12px">
                        {{ s.name }}({{ s.start_time?.slice(0, 5) }}-{{ s.end_time?.slice(0, 5) }})
                        @ ¥{{ formatMoney(s.unit_price) }}
                      </div>
                    </template>
                  </template>
                </el-table-column>
                <el-table-column label="操作" min-width="160" fixed="right">
                  <template #default="{ row }">
                    <el-space>
                      <el-button size="small" type="primary" plain @click="openEditDialog(row)">编辑</el-button>
                      <el-button size="small" type="danger" plain @click="deleteStrategy(row)">删除</el-button>
                    </el-space>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- ============= 价格预览 ============= -->
            <el-tab-pane label="价格预览工具" name="preview">
              <el-card shadow="never" style="margin-bottom: 14px">
                <h3 class="section-title" style="margin: 0 0 12px">计费预演</h3>
                <p style="margin: 0 0 14px; color: var(--text-sub); font-size: 13px">
                  输入用户、房间、时间和用量，可预演系统将如何计算最终金额
                </p>
                <el-form :inline="true" label-position="top">
                  <el-form-item label="目标用户ID（可选）">
                    <el-input-number v-model="previewForm.user_id" :min="1" :controls="false" style="width: 180px" placeholder="学生ID，用于阶梯计算" />
                  </el-form-item>
                  <el-form-item label="房间（可选）">
                    <el-select v-model="previewForm.room_id" style="width: 220px" placeholder="选择房间，不选按用户所在床位推断" clearable filterable>
                      <el-option v-for="r in roomOptions" :key="r.value" :label="r.label" :value="r.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="消费类目" required>
                    <el-select v-model="previewForm.category" style="width: 140px">
                      <el-option label="水费" value="water" />
                      <el-option label="电费" value="electricity" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="用量" required>
                    <el-input-number v-model="previewForm.usage" :min="0" :precision="2" :step="1" style="width: 140px" placeholder="度/吨" />
                  </el-form-item>
                  <el-form-item label="消费时间（可选）">
                    <el-date-picker
                      v-model="previewForm.at_time"
                      type="datetime"
                      value-format="YYYY-MM-DDTHH:mm:ss"
                      placeholder="不填则使用当前时间"
                      style="width: 240px"
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" :loading="previewLoading" @click="runPreview">计算预览</el-button>
                  </el-form-item>
                </el-form>
              </el-card>

              <el-skeleton :loading="previewLoading" animated :rows="4">
                <template #default>
                  <template v-if="previewResult && previewResult.matched">
                    <el-alert
                      :title="`当前命中策略：${previewResult.matched.strategy_name || '默认价格'}（${resultTypeLabel(previewResult.matched.strategy_type)}）`"
                      :type="previewResult.matched.success ? 'success' : 'error'"
                      :closable="false"
                      show-icon
                      style="margin-bottom: 14px"
                    >
                      <template v-if="!previewResult.matched.success">
                        {{ previewResult.matched.error_message || previewResult.matched.error }}
                      </template>
                    </el-alert>

                    <el-row :gutter="12">
                      <el-col :span="8" v-for="key in ['fixed', 'tiered', 'timeslot']" :key="key">
                        <el-card
                          shadow="never"
                          :body-style="{ padding: '12px' }"
                          :style="{
                            border: previewResult.matched.strategy_type === key
                              ? '2px solid var(--el-color-primary)'
                              : '1px solid var(--el-border-color-lighter)',
                          }"
                        >
                          <template #header>
                            <div style="display: flex; justify-content: space-between; align-items: center">
                              <span style="font-weight: 600">{{ resultTypeLabel(key) }}试算</span>
                              <el-tag
                                v-if="previewResult.matched.strategy_type === key"
                                type="primary" size="small" effect="dark">
                                当前命中
                              </el-tag>
                              <el-tag
                                v-else
                                :type="resultTypeTagType(key)" size="small" effect="plain">
                                参考对比
                              </el-tag>
                            </div>
                          </template>
                          <template v-if="previewResult[key] && previewResult[key].success">
                            <el-descriptions :column="1" border size="small" style="margin-bottom: 10px">
                              <el-descriptions-item label="策略">
                                {{ previewResult[key].strategy_name || '--' }}
                              </el-descriptions-item>
                              <el-descriptions-item label="生效维度">
                                {{ previewResult[key].scope_label || '--' }}
                              </el-descriptions-item>
                              <el-descriptions-item label="总用量">
                                {{ formatMoney(previewResult[key].total_usage) }} {{ displayUnit(previewForm.category) }}
                              </el-descriptions-item>
                              <el-descriptions-item label="总金额">
                                <span style="color: var(--el-color-danger); font-weight: 700; font-size: 16px">
                                  ¥ {{ formatMoney(previewResult[key].total_amount) }}
                                </span>
                              </el-descriptions-item>
                              <el-descriptions-item v-if="previewResult[key].prior_monthly_usage !== undefined" label="当月累计">
                                {{ formatMoney(previewResult[key].prior_monthly_usage) }} {{ displayUnit(previewForm.category) }}
                              </el-descriptions-item>
                            </el-descriptions>
                            <div style="font-size: 12px; color: var(--text-sub); margin-bottom: 4px">计费构成</div>
                            <el-table :data="previewResult[key].breakdown || []" size="small" stripe border empty-text="无明细">
                              <el-table-column prop="label" label="分段/时段" min-width="110" show-overflow-tooltip />
                              <el-table-column label="用量" min-width="70">
                                <template #default="{ row }">{{ formatMoney(row.usage) }}</template>
                              </el-table-column>
                              <el-table-column label="单价" min-width="70">
                                <template #default="{ row }">¥{{ formatMoney(row.unit_price) }}</template>
                              </el-table-column>
                              <el-table-column label="小计" min-width="75">
                                <template #default="{ row }">
                                  <b>¥{{ formatMoney(row.amount) }}</b>
                                </template>
                              </el-table-column>
                            </el-table>
                          </template>
                          <template v-else>
                            <el-empty
                              :description="previewResult[key]?.error_message || previewResult[key]?.error || '试算失败'"
                              :image-size="60"
                            />
                          </template>
                        </el-card>
                      </el-col>
                    </el-row>
                  </template>
                  <el-empty v-else description="请点击「计算预览」按钮查看三种计费方式对比结果" />
                </template>
              </el-skeleton>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </template>
    </el-skeleton>

    <!-- ============= 策略编辑弹窗 ============= -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建价格策略' : '编辑价格策略'"
      width="880px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="110px"
        label-position="right"
      >
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="策略名称" prop="name">
              <el-input v-model="form.name" maxlength="128" show-word-limit placeholder="例如：学生宿舍电费平峰谷" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="策略描述">
              <el-input v-model="form.description" maxlength="500" show-word-limit placeholder="选填，补充说明" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="适用类目" prop="category">
              <el-select v-model="form.category" style="width: 100%">
                <el-option label="水费" value="water" />
                <el-option label="电费" value="electricity" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="策略类型" prop="strategy_type">
              <el-select v-model="form.strategy_type" style="width: 100%">
                <el-option label="固定单价" value="fixed" />
                <el-option label="阶梯单价" value="tiered" />
                <el-option label="时段单价" value="timeslot" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="form.priority" :min="0" :max="999" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="生效维度" prop="scope_type">
              <el-select v-model="form.scope_type" style="width: 100%">
                <el-option label="全校默认" value="global" />
                <el-option label="校区" value="campus" />
                <el-option label="楼栋" value="building" />
                <el-option label="房间" value="room" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.scope_type === 'campus'" :span="16">
            <el-form-item label="校区" required>
              <el-select v-model="form.campus" style="width: 100%" filterable>
                <el-option v-for="c in campusOptions" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.scope_type === 'building'" :span="16">
            <el-form-item label="楼栋" required>
              <el-select v-model="form.building" style="width: 100%" filterable>
                <el-option v-for="b in buildingOptions" :key="b.value" :label="b.label" :value="b.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.scope_type === 'room'" :span="16">
            <el-form-item label="房间" required>
              <el-select v-model="form.room" style="width: 100%" filterable>
                <el-option v-for="r in roomOptions" :key="r.value" :label="r.label" :value="r.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="生效开始" prop="effective_from">
              <el-date-picker v-model="form.effective_from" value-format="YYYY-MM-DD" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="生效结束">
              <el-date-picker v-model="form.effective_to" value-format="YYYY-MM-DD" type="date" style="width: 100%" placeholder="不填表示长期" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="是否启用">
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 固定/阶梯单价 -->
        <el-card v-if="form.strategy_type !== 'timeslot'" shadow="never" style="margin-top: 6px">
          <template #header>
            <el-row justify="space-between" align="middle">
              <span>阶梯分段配置（{{ form.strategy_type === 'fixed' ? '固定单价仅需 1 段' : '可多段，按累计用量从低到高' }}）</span>
              <el-button v-if="form.strategy_type === 'tiered'" size="small" type="primary" plain @click="addTier">+ 添加分段</el-button>
            </el-row>
          </template>
          <el-table :data="form.tiers" border>
            <el-table-column label="排序" width="80">
              <template #default="{ $index }">{{ $index + 1 }}</template>
            </el-table-column>
            <el-table-column label="起始用量（含）" min-width="180">
              <template #default="{ row }">
                <el-input-number v-model="row.min_usage" :precision="2" :min="0" :step="10" controls-position="right" style="width: 100%" />
              </template>
            </el-table-column>
            <el-table-column label="结束用量（不含）" min-width="180">
              <template #default="{ row }">
                <el-input-number v-model="row.max_usage" :precision="2" :min="0" :step="10" controls-position="right" style="width: 100%" placeholder="留空表示不限" :disabled="form.strategy_type === 'fixed'" />
              </template>
            </el-table-column>
            <el-table-column label="单价（元）" min-width="180">
              <template #default="{ row }">
                <el-input-number v-model="row.unit_price" :precision="2" :min="0" :step="0.1" controls-position="right" style="width: 100%" />
              </template>
            </el-table-column>
            <el-table-column v-if="form.strategy_type === 'tiered'" label="操作" width="80" align="center">
              <template #default="{ $index }">
                <el-button size="small" type="danger" text @click="removeTier($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 时段单价 -->
        <el-card v-else shadow="never" style="margin-top: 6px">
          <template #header>
            <el-row justify="space-between" align="middle">
              <span>时段配置（按消费发生时间匹配，可多时段）</span>
              <el-button size="small" type="primary" plain @click="addTimeslot">+ 添加时段</el-button>
            </el-row>
          </template>
          <div v-for="(slot, idx) in form.timeslots" :key="idx" class="timeslot-block">
            <el-row :gutter="12" align="middle">
              <el-col :span="3">
                <b>时段 {{ idx + 1 }}</b>
              </el-col>
              <el-col :span="5">
                <el-input v-model="slot.name" placeholder="如：峰/平/谷" maxlength="32" />
              </el-col>
              <el-col :span="4">
                <el-time-picker v-model="slot.start_time" value-format="HH:mm:ss" format="HH:mm" placeholder="开始" style="width: 100%" />
              </el-col>
              <el-col :span="4">
                <el-time-picker v-model="slot.end_time" value-format="HH:mm:ss" format="HH:mm" placeholder="结束" style="width: 100%" />
              </el-col>
              <el-col :span="5">
                <el-input-number v-model="slot.unit_price" :precision="2" :min="0" :step="0.1" controls-position="right" style="width: 100%" placeholder="单价（元）" />
              </el-col>
              <el-col :span="4" style="text-align: right">
                <el-button size="small" type="danger" text @click="removeTimeslot(idx)" :disabled="form.timeslots.length <= 1">删除</el-button>
              </el-col>
            </el-row>
            <el-row :gutter="12" style="margin-top: 6px">
              <el-col :span="3"><span style="color: var(--text-sub)">适用星期：</span></el-col>
              <el-col :span="21">
                <el-checkbox-group>
                  <el-checkbox
                    v-for="(label, wIdx) in weekdayLabels"
                    :key="wIdx"
                    :checked="slot.weekday_mask[wIdx] === '1'"
                    @change="toggleWeekday(slot, wIdx)"
                  >{{ label }}</el-checkbox>
                </el-checkbox-group>
                <span style="margin-left: 12px; color: var(--text-sub)">({{ weekdayMaskToText(slot.weekday_mask) }})</span>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm($refs.formRef)">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<style scoped>
.timeslot-block {
  padding: 10px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.timeslot-block:last-child {
  border-bottom: none;
}
</style>
