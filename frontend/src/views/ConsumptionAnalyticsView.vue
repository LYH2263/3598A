<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'

import BIFilterBar from '../components/bi/BIFilterBar.vue'
import BICard from '../components/bi/BICard.vue'
import CategoryChart from '../components/bi/CategoryChart.vue'
import TrendChart from '../components/bi/TrendChart.vue'
import ChannelChart from '../components/bi/ChannelChart.vue'
import TopStudentsChart from '../components/bi/TopStudentsChart.vue'
import BuildingRoomChart from '../components/bi/BuildingRoomChart.vue'
import TimePeriodChart from '../components/bi/TimePeriodChart.vue'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const saving = ref(false)

const filters = reactive({
  start_date: '',
  end_date: '',
  categories: [],
  channels: [],
  min_amount: null,
  max_amount: null,
  buildings: [],
  rooms: [],
  user_ids: [],
  trend_granularity: 'day',
  top_n: 10,
  compare_enabled: false,
  compare_start_date: '',
  compare_end_date: '',
})

const dimensionOptions = reactive({
  categories: [],
  channels: [],
  buildings: [],
  rooms: [],
  date_range: { min: null, max: null },
})

const biData = reactive({
  by_category: { items: [], summary: {} },
  by_trend: { items: [], summary: {} },
  by_channel: { items: [], summary: {} },
  top_students: [],
  by_building_room: { buildings: [], rooms: [], summary: {} },
  by_time_period: { items: [], summary: {} },
  compare: null,
})

const defaultCardOrder = [
  'category',
  'trend',
  'channel',
  'time_period',
  'building_room',
  'top_students',
]

const cardConfig = {
  category: { title: '消费类目分布', exportView: 'category' },
  trend: { title: '消费时间趋势', exportView: 'trend' },
  channel: { title: '消费渠道分布', exportView: 'channel' },
  top_students: { title: `学生消费 Top N`, exportView: 'top_students' },
  building_room: { title: '楼栋/房间分布', exportView: 'building_room' },
  time_period: { title: '消费时段分布', exportView: 'time_period' },
}

const cardOrder = ref([...defaultCardOrder])
const collapsedCards = ref([])
const dragOverCardId = ref(null)

function buildQueryParams(source = filters) {
  const params = {}
  if (source.start_date) params.start_date = source.start_date
  if (source.end_date) params.end_date = source.end_date
  if (source.categories?.length) params.categories = source.categories.join(',')
  if (source.channels?.length) params.channels = source.channels.join(',')
  if (source.buildings?.length) params.buildings = source.buildings.join(',')
  if (source.rooms?.length) params.rooms = source.rooms.join(',')
  if (source.user_ids?.length) params.user_ids = source.user_ids.join(',')
  if (source.min_amount != null) params.min_amount = source.min_amount
  if (source.max_amount != null) params.max_amount = source.max_amount
  if (source.top_n) params.top_n = source.top_n
  if (source.trend_granularity) params.trend_granularity = source.trend_granularity
  return params
}

async function loadOverview() {
  loading.value = true
  try {
    const params = buildQueryParams()
    const { data } = await http.get('/billing/bi/overview/', { params })
    Object.assign(dimensionOptions, data.dimension_options || {})
    biData.by_category = { items: data.by_category?.items || [], summary: data.by_category?.summary || {} }
    biData.by_trend = { items: data.by_trend?.items || [], summary: data.by_trend?.summary || {} }
    biData.by_channel = { items: data.by_channel?.items || [], summary: data.by_channel?.summary || {} }
    biData.top_students = data.top_students || []
    biData.by_building_room = {
      buildings: data.by_building_room?.buildings || [],
      rooms: data.by_building_room?.rooms || [],
      summary: data.by_building_room?.summary || {},
    }
    biData.by_time_period = { items: data.by_time_period?.items || [], summary: data.by_time_period?.summary || {} }

    if (filters.compare_enabled && filters.compare_start_date && filters.compare_end_date) {
      await loadCompare()
    } else {
      biData.compare = null
    }
  } catch (e) {
    // 错误已由 http 拦截器处理
  } finally {
    loading.value = false
  }
}

async function loadCompare() {
  try {
    const params = buildQueryParams()
    params.compare_start_date = filters.compare_start_date
    params.compare_end_date = filters.compare_end_date
    params.granularity = filters.trend_granularity
    const { data } = await http.get('/billing/bi/compare/', { params })
    biData.compare = data
  } catch (_e) {
    biData.compare = null
  }
}

async function loadDimensionOptions() {
  try {
    const { data } = await http.get('/billing/bi/dimensions/')
    Object.assign(dimensionOptions, data)
  } catch (_e) {
    // ignore
  }
}

async function loadDashboardPreference() {
  try {
    const { data } = await http.get('/billing/dashboard-preferences/admin-analytics/')
    if (data?.card_order?.length) cardOrder.value = data.card_order
    if (data?.collapsed_cards) collapsedCards.value = data.collapsed_cards
    if (data?.filters_snapshot) Object.assign(filters, data.filters_snapshot)
  } catch (_e) {
    // ignore - 可能是首次访问没有偏好记录
  }
}

async function saveDashboardPreference() {
  saving.value = true
  try {
    const payload = {
      board_key: 'admin-analytics',
      card_order: cardOrder.value,
      collapsed_cards: collapsedCards.value,
      filters_snapshot: { ...filters },
    }
    await http.put('/billing/dashboard-preferences/admin-analytics/', payload)
    ElNotification({ title: '已保存', message: '看板布局与筛选偏好已保存。', type: 'success' })
  } catch (e) {
    ElNotification({ title: '保存失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  } finally {
    saving.value = false
  }
}

function handleSearch() {
  loadOverview()
}

function handleReset() {
  loadOverview()
}

function handleToggleCollapse({ cardId, collapsed }) {
  if (collapsed) {
    if (!collapsedCards.value.includes(cardId)) collapsedCards.value.push(cardId)
  } else {
    collapsedCards.value = collapsedCards.value.filter((id) => id !== cardId)
  }
}

function handleExport(viewName) {
  const params = buildQueryParams()
  params.view = viewName
  const qs = new URLSearchParams(params).toString()
  const url = `/billing/bi/export-csv/?${qs}`
  http
    .get(url, { responseType: 'blob' })
    .then((res) => {
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8-sig' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      const ts = new Date().toISOString().slice(0, 10)
      link.download = `bi_${viewName}_${ts}.csv`
      link.click()
      URL.revokeObjectURL(link.href)
    })
    .catch((e) => {
      ElNotification({ title: '导出失败', message: e?.response?.data?.detail || String(e), type: 'error' })
    })
}

function handleDragOver(e, cardId) {
  dragOverCardId.value = cardId
}

function handleDrop(e, targetCardId) {
  const sourceCardId = e.dataTransfer.getData('text/plain')
  dragOverCardId.value = null
  if (!sourceCardId || sourceCardId === targetCardId) return
  const order = [...cardOrder.value]
  const srcIdx = order.indexOf(sourceCardId)
  const tgtIdx = order.indexOf(targetCardId)
  if (srcIdx < 0 || tgtIdx < 0) return
  order.splice(srcIdx, 1)
  order.splice(tgtIdx, 0, sourceCardId)
  cardOrder.value = order
}

const orderedCards = computed(() => {
  return cardOrder.value
    .filter((id) => cardConfig[id])
    .map((id) => ({ id, ...cardConfig[id], collapsed: collapsedCards.value.includes(id) }))
})

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
  if (authStore.user?.profile?.role !== 'admin') {
    await router.push('/dashboard')
    return
  }
  await Promise.all([loadDimensionOptions(), loadDashboardPreference()])
  await loadOverview()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :xs="24" :sm="18">
          <h2 class="section-title">消费分析（BI）</h2>
          <p style="margin: 0; color: var(--text-sub)">
            多维筛选 · 6 大视图 · 时间段对比 · 可拖拽布局
          </p>
        </el-col>
        <el-col :xs="24" :sm="6" style="text-align: right">
          <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回总览</el-button>
          <el-button style="margin-right: 8px" :loading="loading" @click="loadOverview">刷新数据</el-button>
          <el-button type="primary" :loading="saving" @click="saveDashboardPreference">保存布局偏好</el-button>
        </el-col>
      </el-row>
    </el-card>

    <BIFilterBar
      v-model="filters"
      :is-admin="true"
      :dimension-options="dimensionOptions"
      @search="handleSearch"
      @reset="handleReset"
    />

    <el-skeleton :loading="loading" animated :rows="12">
      <template #default>
        <div class="bi-grid">
          <div
            v-for="card in orderedCards"
            :key="card.id"
            class="bi-grid-item"
            :class="{ 'drag-over': dragOverCardId === card.id }"
            @dragover="(e) => handleDragOver(e, card.id)"
            @drop="(e) => handleDrop(e, card.id)"
          >
            <BICard
              :card-id="card.id"
              :title="card.title"
              :export-view="card.exportView"
              :collapsed="card.collapsed"
              :loading="loading"
              @toggle-collapse="handleToggleCollapse"
              @export="handleExport"
            >
              <CategoryChart
                v-if="card.id === 'category'"
                :data="biData.by_category.items"
                :summary="biData.by_category.summary"
              />
              <TrendChart
                v-else-if="card.id === 'trend'"
                :data="biData.by_trend.items"
                :summary="biData.by_trend.summary"
                :granularity="filters.trend_granularity"
                :compare-data="biData.compare"
              />
              <ChannelChart
                v-else-if="card.id === 'channel'"
                :data="biData.by_channel.items"
                :summary="biData.by_channel.summary"
              />
              <TopStudentsChart
                v-else-if="card.id === 'top_students'"
                :data="biData.top_students"
                :top-n="filters.top_n"
              />
              <BuildingRoomChart
                v-else-if="card.id === 'building_room'"
                :buildings="biData.by_building_room.buildings"
                :rooms="biData.by_building_room.rooms"
                :summary="biData.by_building_room.summary"
              />
              <TimePeriodChart
                v-else-if="card.id === 'time_period'"
                :data="biData.by_time_period.items"
                :summary="biData.by_time_period.summary"
              />
            </BICard>
          </div>
        </div>
      </template>
    </el-skeleton>
  </main>
</template>

<style scoped>
.bi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}
.bi-grid-item {
  transition: transform 0.15s, box-shadow 0.15s;
}
.bi-grid-item.drag-over {
  outline: 2px dashed #2d73da;
  outline-offset: 2px;
  border-radius: 12px;
}
@media (max-width: 900px) {
  .bi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
