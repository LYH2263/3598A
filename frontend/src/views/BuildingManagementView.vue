<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElNotification } from 'element-plus'

import http from '../utils/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(true)
const treeData = ref([])
const activeTab = ref('tree')

const campusList = ref([])
const buildingList = ref([])
const stayRecords = ref([])
const changeLogs = ref([])

const defaultProps = {
  children: 'children',
  label: 'name',
}

const typeIconMap = {
  campus: '🏫',
  building: '🏢',
  floor: '📐',
  room: '🚪',
  bed: '🛏️',
}

const typeNameMap = {
  campus: '校区',
  building: '楼栋',
  floor: '楼层',
  room: '房间',
  bed: '床位',
}

const stayStatusMap = {
  active: { label: '在住', type: 'success' },
  ended: { label: '已退宿', type: 'info' },
  cancelled: { label: '已取消', type: 'danger' },
}

const changeTypeMap = {
  checkin: '入住',
  checkout: '退宿',
  transfer: '调床',
  adjust: '管理员调整',
}

const stayFilters = reactive({
  user_id: '',
  status: '',
})

const dialogVisible = ref(false)
const dialogMode = ref('create')
const dialogEntity = reactive({
  type: '',
  entity: null,
  parent: null,
})

const campusForm = reactive({
  name: '',
  code: '',
  address: '',
  description: '',
  is_active: true,
  sort_order: 0,
})

const buildingForm = reactive({
  campus_id: null,
  name: '',
  code: '',
  building_type: 'dorm',
  gender_limit: 'mixed',
  total_floors: 0,
  description: '',
  is_active: true,
  sort_order: 0,
})

const floorForm = reactive({
  building_id: null,
  name: '',
  number: 1,
  description: '',
  is_active: true,
  sort_order: 0,
})

const roomForm = reactive({
  floor_id: null,
  name: '',
  room_no: '',
  room_type: 'standard',
  capacity: 4,
  area: null,
  has_bathroom: true,
  has_aircon: true,
  description: '',
  is_active: true,
  sort_order: 0,
})

const bedForm = reactive({
  room_id: null,
  bed_no: '',
  description: '',
  is_active: true,
  sort_order: 0,
})

const assignForm = reactive({
  user_id: null,
  bed_id: null,
  start_date: '',
  remark: '',
  reason: '',
})

const checkoutForm = reactive({
  user_id: null,
  end_date: '',
  reason: '',
})

const assignDialogVisible = ref(false)
const checkoutDialogVisible = ref(false)

function backToDashboard() {
  router.push('/dashboard')
}

function formatDateTime(value) {
  if (!value) return '--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d)
}

function formatDate(value) {
  if (!value) return '--'
  return value
}

function nodeLabel(node) {
  const icon = typeIconMap[node.type] || '📁'
  const extra = []
  if (node.type === 'room') {
    extra.push(`${node.occupied_count || 0}${node.capacity ? '/' + node.capacity : ''}`)
  }
  if (node.type === 'bed') {
    extra.push(node.is_occupied ? '已住' : '空闲')
  }
  return `${icon} ${node.name}${extra.length ? ' (' + extra.join(' ') + ')' : ''}`
}

function openCreateDialog(type, parentNode) {
  dialogEntity.type = type
  dialogMode.value = 'create'
  dialogEntity.entity = null
  dialogEntity.parent = parentNode || null
  dialogVisible.value = true

  if (type === 'campus') {
    Object.assign(campusForm, { name: '', code: '', address: '', description: '', is_active: true, sort_order: 0 })
  } else if (type === 'building') {
    Object.assign(buildingForm, {
      campus_id: parentNode?.id || null,
      name: '', code: '', building_type: 'dorm', gender_limit: 'mixed',
      total_floors: 0, description: '', is_active: true, sort_order: 0,
    })
  } else if (type === 'floor') {
    Object.assign(floorForm, {
      building_id: parentNode?.id || null, name: '', number: 1, description: '', is_active: true, sort_order: 0,
    })
  } else if (type === 'room') {
    Object.assign(roomForm, {
      floor_id: parentNode?.id || null,
      name: '', room_no: '', room_type: 'standard', capacity: 4,
      area: null, has_bathroom: true, has_aircon: true,
      description: '', is_active: true, sort_order: 0,
    })
  } else if (type === 'bed') {
    Object.assign(bedForm, { room_id: parentNode?.id || null, bed_no: '', description: '', is_active: true, sort_order: 0, })
  }
}

function openEditDialog(type, node) {
  dialogEntity.type = type
  dialogMode.value = 'edit'
  dialogEntity.entity = node
  dialogEntity.parent = null
  dialogVisible.value = true
  if (type === 'campus') {
    Object.assign(campusForm, node)
  }
}

async function loadTree() {
  loading.value = true
  try {
    const { data } = await http.get('/housing/tree/')
    treeData.value = data
  } finally {
    loading.value = false
  }
}

async function loadLists() {
  try {
    const resCampus = await http.get('/housing/campus/')
    campusList.value = resCampus.data
    const resBuilding = await http.get('/housing/buildings/')
    buildingList.value = resBuilding.data
  } catch (_e) {
    // ignore
  }
}

async function submitForm() {
  const type = dialogEntity.type
  try {
    if (type === 'campus') {
      if (dialogMode.value === 'create') {
        await http.post('/housing/campus/', campusForm)
      } else {
        await http.put(`/housing/campus/${dialogEntity.entity.id}/`, campusForm)
      }
    } else if (type === 'building') {
        const payload = { ...buildingForm, campus: buildingForm.campus_id }
        if (dialogMode.value === 'create') {
          await http.post('/housing/buildings/', payload)
        } else {
          await http.put(`/housing/buildings/${dialogEntity.entity.id}/`, payload)
        }
    } else if (type === 'floor') {
        const payload = { ...floorForm, building: floorForm.building_id }
        if (dialogMode.value === 'create') {
          await http.post('/housing/floors/', payload)
        } else {
          await http.put(`/housing/floors/${dialogEntity.entity.id}/`, payload)
        }
    } else if (type === 'room') {
        const payload = { ...roomForm, floor: roomForm.floor_id }
        if (dialogMode.value === 'create') {
          await http.post('/housing/rooms/', payload)
        } else {
          await http.put(`/housing/rooms/${dialogEntity.entity.id}/`, payload)
        }
    } else if (type === 'bed') {
        const payload = { ...bedForm, room: bedForm.room_id }
        if (dialogMode.value === 'create') {
          await http.post('/housing/beds/', payload)
        } else {
          await http.put(`/housing/beds/${dialogEntity.entity.id}/`, payload)
        }
    }
    ElNotification({ title: '操作成功', message: `${typeNameMap[type]}${dialogMode.value === 'create' ? '创建' : '更新'}成功`, type: 'success' })
    dialogVisible.value = false
    await Promise.all([loadTree(), loadLists()])
  } catch (_e) {
    // handled by interceptor
  }
}

async function deleteNode(type, node) {
  try {
    await ElMessageBox.confirm(`确定删除 ${node.name}？此操作不可恢复。`, '确认删除', { type: 'warning' })
  } catch (_e) {
    return
  }
  try {
    let url
    if (type === 'campus') url = `/housing/campus/${node.id}/`
    else if (type === 'building') url = `/housing/buildings/${node.id}/`
    else if (type === 'floor') url = `/housing/floors/${node.id}/`
    else if (type === 'room') url = `/housing/rooms/${node.id}/`
    else url = `/housing/beds/${node.id}/`
    await http.delete(url)
    ElNotification({ title: '删除成功', message: `${typeNameMap[type]}已删除`, type: 'success' })
    await loadTree()
  } catch (_e) {
    // handled
  }
}

function openAssignDialog(bedNode) {
  Object.assign(assignForm, { user_id: null, bed_id: bedNode?.id || null, start_date: new Date().toISOString().slice(0, 10), remark: '', reason: '' })
  assignDialogVisible.value = true
}

async function submitAssign() {
  if (!assignForm.user_id || !assignForm.bed_id) {
    ElNotification({ title: '请填写完整', type: 'warning' })
    return
  }
  try {
    await http.post('/housing/stays/assign/', assignForm)
    ElNotification({ title: '入住成功', type: 'success' })
    assignDialogVisible.value = false
    await loadTree()
  } catch (_e) {
    // handled
  }
}

function openCheckoutDialog() {
  Object.assign(checkoutForm, { user_id: null, end_date: new Date().toISOString().slice(0, 10), reason: '' })
  checkoutDialogVisible.value = true
}

async function submitCheckout() {
  if (!checkoutForm.user_id) {
    ElNotification({ title: '请选择学生', type: 'warning' })
    return
  }
  try {
    await http.post('/housing/stays/checkout/', checkoutForm)
    ElNotification({ title: '退宿成功', type: 'success' })
    checkoutDialogVisible.value = false
    await loadTree()
  } catch (_e) {
    // handled
  }
}

async function loadStayRecords() {
  const params = {}
  if (stayFilters.user_id) params.user_id = stayFilters.user_id
  if (stayFilters.status) params.status = stayFilters.status
  const { data } = await http.get('/housing/stays/', { params })
  stayRecords.value = data
}

async function loadChangeLogs() {
  const params = {}
  if (stayFilters.user_id) params.user_id = stayFilters.user_id
  const { data } = await http.get('/housing/stays/change-logs/', { params })
  changeLogs.value = data
}

onMounted(async () => {
  if (!authStore.user) {
    try {
      await authStore.fetchMe()
    } catch (_e) {
      authStore.clearSession()
      await router.push('/login')
      return
    }
  }
  await Promise.all([loadTree(), loadLists()])
})
</script>

<template>
  <main class="page-shell animated-in">
    <section class="dashboard-wrap">
      <el-card class="section-card" shadow="never">
        <el-row justify="space-between" align="middle" :gutter="12">
          <el-col :xs="24" :sm="18">
            <h2 class="section-title">楼宇管理</h2>
            <p style="margin: 0; color: var(--text-sub)">
              校区→楼栋→楼层→房间→床位 五级结构可视化维护
            </p>
          </el-col>
          <el-col :xs="24" :sm="6" style="text-align: right">
            <el-button style="margin-right: 8px" @click="backToDashboard">返回首页</el-button>
            <el-button type="primary" @click="loadTree">刷新数据</el-button>
          </el-col>
        </el-row>
      </el-card>

      <el-skeleton :loading="loading" animated :rows="12">
        <template #default>
          <el-card class="section-card" shadow="never">
            <el-tabs v-model="activeTab">
              <el-tab-pane label="树状结构" name="tree">
                <el-row :gutter="16">
                  <el-col :span="6">
                    <div style="margin-bottom: 12px">
                      <el-button size="small" type="primary" @click="openCreateDialog('campus')">➕ 新建校区</el-button>
                    </div>
                    <el-tree
                      :data="treeData"
                      :props="defaultProps"
                      node-key="id"
                      default-expand-all
                      highlight-current
                      style="background: var(--card-bg); border-radius: 12px; padding: 8px"
                    >
                      <template #default="{ node, data }">
                        <span style="display: flex; justify-content: space-between; align-items: center; width: 100%">
                          <span>{{ nodeLabel(data) }}</span>
                          <span>
                            <el-dropdown trigger="click">
                              <el-button size="small" text>操作</el-button>
                              <template #dropdown>
                                <el-dropdown-menu>
                                  <el-dropdown-item v-if="data.type === 'campus'" @click="openCreateDialog('building', data)">新建楼栋</el-dropdown-item>
                                  <el-dropdown-item v-if="data.type === 'building'" @click="openCreateDialog('floor', data)">新建楼层</el-dropdown-item>
                                  <el-dropdown-item v-if="data.type === 'floor'" @click="openCreateDialog('room', data)">新建房间</el-dropdown-item>
                                  <el-dropdown-item v-if="data.type === 'room'" @click="openCreateDialog('bed', data)">新建床位</el-dropdown-item>
                                  <el-dropdown-item divided @click="deleteNode(data.type, data)">删除</el-dropdown-item>
                                </el-dropdown-menu>
                              </template>
                            </el-dropdown>
                          </span>
                        </span>
                      </template>
                    </el-tree>
                  </el-col>
                  <el-col :span="18">
                    <el-card class="section-card" shadow="never" style="min-height: 600px">
                      <template v-if="treeData.length === 0">
                        <el-empty description="暂无数据，请先创建校区" />
                      </template>
                      <template v-else>
                        <h3 class="section-title">操作提示</h3>
                        <p style="color: var(--text-sub)">
                          在左侧树中点击节点操作菜单可快速新建下级或删除
                        </p>
                        <el-divider />
                        <div class="form-grid" style="margin-top: 16px">
                          <el-card class="section-card" shadow="never">
                            <h3 class="section-title">快捷入口</h3>
                            <el-space wrap>
                              <el-button type="primary" @click="openAssignDialog()">指派学生入住</el-button>
                              <el-button type="danger" @click="openCheckoutDialog()">办理学生退宿</el-button>
                            </el-space>
                          </el-card>
                          <el-card class="section-card" shadow="never">
                            <h3 class="section-title">学生入住查询</h3>
                            <el-form :inline="true">
                              <el-form-item label="用户ID">
                                <el-input v-model="stayFilters.user_id" placeholder="请输入" clearable />
                              </el-form-item>
                              <el-form-item label="状态">
                                <el-select v-model="stayFilters.status" placeholder="全部" clearable>
                                  <el-option label="在住" value="active" />
                                  <el-option label="已退宿" value="ended" />
                                </el-select>
                              </el-form-item>
                              <el-form-item>
                                <el-button @click="loadStayRecords">查询</el-button>
                              </el-form-item>
                            </el-form>
                          </el-card>
                        </div>
                      </template>
                    </el-card>
                  </el-col>
                </el-row>
              </el-tab-pane>

              <el-tab-pane label="入住记录" name="stays">
                <el-button type="primary" style="margin-bottom: 12px" @click="loadStayRecords">刷新记录</el-button>
                <el-table :data="stayRecords" stripe border empty-text="暂无入住记录" max-height="600px">
                  <el-table-column prop="user_name" label="学生" min-width="120" />
                  <el-table-column prop="student_id" label="学号" min-width="120" />
                  <el-table-column prop="building_name" label="楼栋" min-width="120" />
                  <el-table-column prop="floor_number" label="楼层" width="80" />
                  <el-table-column prop="room_no" label="房间" min-width="100" />
                  <el-table-column prop="bed_no" label="床位" min-width="100" />
                  <el-table-column label="状态" min-width="100">
                    <template #default="{ row }">
                      <el-tag :type="stayStatusMap[row.status]?.type || 'info'" effect="plain">
                        {{ stayStatusMap[row.status]?.label || row.status }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="入住日期" min-width="120">
                    <template #default="{ row }">{{ formatDate(row.start_date) }}</template>
                  </el-table-column>
                  <el-table-column label="退宿日期" min-width="120">
                    <template #default="{ row }">{{ formatDate(row.end_date) }}</template>
                  </el-table-column>
                  <el-table-column prop="operator" label="操作人" min-width="120" />
                  <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="床位变更日志" name="logs">
                <el-button type="primary" style="margin-bottom: 12px" @click="loadChangeLogs">刷新日志</el-button>
                <el-table :data="changeLogs" stripe border empty-text="暂无变更日志" max-height="600px">
                  <el-table-column prop="user_name" label="学生" min-width="120" />
                  <el-table-column label="变更类型" min-width="100">
                    <template #default="{ row }">{{ changeTypeMap[row.change_type] || row.change_type }}</template>
                  </el-table-column>
                  <el-table-column label="原房间" min-width="120">
                    <template #default="{ row }">{{ row.from_room_no || '--' }}</template>
                  </el-table-column>
                  <el-table-column label="新房间" min-width="120">
                    <template #default="{ row }">{{ row.to_room_no || '--' }}</template>
                  </el-table-column>
                  <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
                  <el-table-column prop="operator" label="操作人" min-width="120" />
                  <el-table-column label="时间" min-width="165">
                    <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </template>
      </el-skeleton>
    </section>

    <el-dialog v-model="dialogVisible" :title="`${dialogMode === 'create' ? '新建' : '编辑'}${typeNameMap[dialogEntity.type]}`" width="560px">
      <el-form label-position="top" @submit.prevent>
        <template v-if="dialogEntity.type === 'campus'">
          <el-form-item label="校区名称">
            <el-input v-model="campusForm.name" placeholder="请输入校区名称" />
          </el-form-item>
          <el-form-item label="校区编码">
            <el-input v-model="campusForm.code" placeholder="请输入校区编码" />
          </el-form-item>
          <el-form-item label="地址">
            <el-input v-model="campusForm.address" placeholder="请输入地址（可选）" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="campusForm.description" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="campusForm.is_active" />
          </el-form-item>
        </template>

        <template v-else-if="dialogEntity.type === 'building'">
          <el-form-item label="所属校区">
            <el-select v-model="buildingForm.campus_id" placeholder="请选择校区">
              <el-option v-for="c in campusList" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="楼栋名称">
            <el-input v-model="buildingForm.name" placeholder="请输入楼栋名称" />
          </el-form-item>
          <el-form-item label="楼栋编码">
            <el-input v-model="buildingForm.code" placeholder="请输入楼栋编码" />
          </el-form-item>
          <el-form-item label="楼栋类型">
            <el-select v-model="buildingForm.building_type">
              <el-option label="宿舍楼" value="dorm" />
              <el-option label="教学楼" value="teaching" />
              <el-option label="办公楼" value="office" />
              <el-option label="综合楼" value="mixed" />
            </el-select>
          </el-form-item>
          <el-form-item label="性别限制">
            <el-select v-model="buildingForm.gender_limit">
              <el-option label="男生楼" value="male" />
              <el-option label="女生楼" value="female" />
              <el-option label="男女混合" value="mixed" />
            </el-select>
          </el-form-item>
          <el-form-item label="总楼层">
            <el-input-number v-model="buildingForm.total_floors" :min="0" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="buildingForm.description" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
          </el-form-item>
        </template>

        <template v-else-if="dialogEntity.type === 'floor'">
          <el-form-item label="所属楼栋">
            <el-select v-model="floorForm.building_id" placeholder="请选择楼栋">
              <el-option v-for="b in buildingList" :key="b.id" :label="b.name" :value="b.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="楼层名称">
            <el-input v-model="floorForm.name" placeholder="请输入楼层名称（如 1F）" />
          </el-form-item>
          <el-form-item label="楼层号">
            <el-input-number v-model="floorForm.number" :min="1" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="floorForm.description" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
          </el-form-item>
        </template>

        <template v-else-if="dialogEntity.type === 'room'">
          <el-form-item label="所属楼层">
            <el-select v-model="roomForm.floor_id" placeholder="请选择楼层">
              <el-option label="请选择楼层" :value="null" />
            </el-select>
          </el-form-item>
          <el-form-item label="房间名称">
            <el-input v-model="roomForm.name" placeholder="请输入房间名称" />
          </el-form-item>
          <el-form-item label="房间号">
            <el-input v-model="roomForm.room_no" placeholder="请输入房间号" />
          </el-form-item>
          <el-form-item label="房间类型">
            <el-select v-model="roomForm.room_type">
              <el-option label="标准间" value="standard" />
              <el-option label="豪华间" value="deluxe" />
              <el-option label="套间" value="suite" />
            </el-select>
          </el-form-item>
          <el-form-item label="可住人数">
            <el-input-number v-model="roomForm.capacity" :min="1" />
          </el-form-item>
          <el-form-item label="面积(㎡)">
            <el-input-number v-model="roomForm.area" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="设施">
            <el-switch v-model="roomForm.has_bathroom" active-text="独立卫浴" />
            <el-switch v-model="roomForm.has_aircon" active-text="空调" style="margin-left: 24px" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="roomForm.description" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
          </el-form-item>
        </template>

        <template v-else-if="dialogEntity.type === 'bed'">
          <el-form-item label="所属房间">
            <el-select v-model="bedForm.room_id" placeholder="请选择房间">
              <el-option label="请选择房间" :value="null" />
            </el-select>
          </el-form-item>
          <el-form-item label="床位号">
            <el-input v-model="bedForm.bed_no" placeholder="请输入床位号（如 A1）" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="bedForm.description" type="textarea" :rows="2" placeholder="请输入描述（可选）" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="assignDialogVisible" title="指派学生入住" width="480px">
      <el-form label-position="top">
        <el-form-item label="学生用户ID">
          <el-input v-model="assignForm.user_id" placeholder="请输入学生用户ID" />
        </el-form-item>
        <el-form-item label="床位ID">
          <el-input v-model="assignForm.bed_id" placeholder="请输入床位ID" />
        </el-form-item>
        <el-form-item label="入住日期">
          <el-date-picker v-model="assignForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="assignForm.remark" placeholder="请输入备注（可选）" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="assignForm.reason" placeholder="请输入原因（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAssign">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="checkoutDialogVisible" title="学生退宿" width="480px">
      <el-form label-position="top">
        <el-form-item label="学生用户ID">
          <el-input v-model="checkoutForm.user_id" placeholder="请输入学生用户ID" />
        </el-form-item>
        <el-form-item label="退宿日期">
          <el-date-picker v-model="checkoutForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="checkoutForm.reason" placeholder="请输入原因（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="checkoutDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCheckout">确定</el-button>
      </template>
    </el-dialog>
  </main>
</template>
