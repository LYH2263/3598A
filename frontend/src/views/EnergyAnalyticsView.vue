<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import SimpleBarChart from '../components/SimpleBarChart.vue'
import http from '../utils/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const activeTab = ref('room-ranking')

const filters = reactive({
  category: '',
  start_date: '',
  end_date: '',
  campus_id: '',
  building_id: '',
  room_id: '',
  top_n: 20,
  group_by: 'building',
})

const roomRanking = ref([])
const buildingRanking = ref([])
const monthlyTrend = ref([])
const campusList = ref([])
const buildingList = ref([])

const categoryMap = {
  water: '水费',
  electricity: '电费',
}

function formatMoney(value) {
  const amount = Number(value ?? 0)
  if (Number.isNaN(amount)) return '0.00'
  return amount.toFixed(2)
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

async function loadCampusList() {
  try {
    const { data } = await http.get('/housing/campus/')
    campusList.value = data
  } catch (_e) {
    campusList.value = []
  }
}

async function loadBuildingList() {
  try {
    const { data } = await http.get('/housing/buildings/')
    buildingList.value = data
  } catch (_e) {
    buildingList.value = []
  }
}

function buildParams() {
  const params = {}
  if (filters.category) params.category = filters.category
  if (filters.start_date) params.start_date = filters.start_date
  if (filters.end_date) params.end_date = filters.end_date
  if (filters.campus_id) params.campus_id = filters.campus_id
  if (filters.building_id) params.building_id = filters.building_id
  if (filters.room_id) params.room_id = filters.room_id
  if (filters.top_n) params.top_n = filters.top_n
  if (filters.group_by) params.group_by = filters.group_by
  return params
}

async function loadRoomRanking() {
  loading.value = true
  try {
    const { data } = await http.get('/housing/energy/room-ranking/', { params: buildParams() })
    roomRanking.value = data
  } catch (_e) {
    roomRanking.value = []
  } finally {
    loading.value = false
  }
}

async function loadBuildingRanking() {
  loading.value = true
  try {
    const { data } = await http.get('/housing/energy/building-ranking/', { params: buildParams() })
    buildingRanking.value = data
  } catch (_e) {
    buildingRanking.value = []
  } finally {
    loading.value = false
  }
}

async function loadMonthlyTrend() {
  loading.value = true
  try {
    const { data } = await http.get('/housing/energy/monthly-trend/', { params: buildParams() })
    monthlyTrend.value = data
  } catch (_e) {
    monthlyTrend.value = []
  } finally {
    loading.value = false
  }
}

const roomRankingChart = computed(() => {
  return roomRanking.value.slice(0, 10).map((item) => ({
    label: item.room_no || item.room_name || `房间#${item.room_id}`,
    value: formatMoney(item.total_cost),
  }))
})

const buildingRankingChart = computed(() => {
  return buildingRanking.value.slice(0, 10).map((item) => ({
    label: item.building_name || `楼栋#${item.building_id}`,
    value: formatMoney(item.total_cost),
  }))
})

const monthlyTrendChart = computed(() => {
  const monthMap = {}
  monthlyTrend.value.forEach((item) => {
    const key = item.month || item.period || '--'
    if (!monthMap[key]) {
      monthMap[key] = 0
    }
    monthMap[key] += Number(item.total_cost || 0)
  })
  return Object.keys(monthMap)
    .sort()
    .map((month) => ({
      label: month,
      value: formatMoney(monthMap[month]),
    }))
})

function handleSearch() {
  if (activeTab.value === 'room-ranking') {
    loadRoomRanking()
  } else if (activeTab.value === 'building-ranking') {
    loadBuildingRanking()
  } else if (activeTab.value === 'monthly-trend') {
    loadMonthlyTrend()
  }
}

function handleReset() {
  filters.category = ''
  filters.start_date = ''
  filters.end_date = ''
  filters.campus_id = ''
  filters.building_id = ''
  filters.room_id = ''
  filters.top_n = 20
  filters.group_by = 'building'
  handleSearch()
}

function switchTab(tabName) {
  activeTab.value = tabName
  handleSearch()
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
  if (authStore.user?.profile?.role !== 'admin') {
    await router.push('/dashboard')
    return
  }
  await Promise.all([loadCampusList(), loadBuildingList()])
  await loadRoomRanking()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :xs="24" :sm="18">
          <h2 class="section-title">能耗分析</h2>
          <p style="margin: 0; color: var(--text-sub)">
            按房间/楼栋查看能耗排行榜与月度趋势
          </p>
        </el-col>
        <el-col :xs="24" :sm="6" style="text-align: right">
          <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回首页</el-button>
          <el-button type="primary" @click="handleSearch">刷新数据</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="section-card" shadow="never">
      <el-row :gutter="12" align="middle">
        <el-col :span="4">
          <el-select v-model="filters.category" placeholder="全部类别" clearable style="width: 100%">
            <el-option label="水费" value="water" />
            <el-option label="电费" value="electricity" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-date-picker v-model="filters.start_date" value-format="YYYY-MM-DD" type="date" placeholder="开始日期" style="width: 100%" />
        </el-col>
        <el-col :span="5">
          <el-date-picker v-model="filters.end_date" value-format="YYYY-MM-DD" type="date" placeholder="结束日期" style="width: 100%" />
        </el-col>
        <el-col :span="3">
          <el-select v-model="filters.campus_id" placeholder="校区" clearable style="width: 100%">
            <el-option v-for="c in campusList" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filters.building_id" placeholder="楼栋" clearable style="width: 100%">
            <el-option v-for="b in buildingList" :key="b.id" :label="b.name" :value="b.id" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button style="margin-right: 8px" @click="handleSearch">查询</el-button>
          <el-button plain @click="handleReset">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-skeleton :loading="loading" animated :rows="10">
      <template #default>
        <el-card class="section-card" shadow="never">
          <el-tabs v-model="activeTab" @tab-change="switchTab">
            <el-tab-pane label="按房间能耗排行" name="room-ranking">
              <div class="form-grid" style="margin-bottom: 14px">
                <SimpleBarChart title="TOP 10 房间消费金额（元）" :items="roomRankingChart" />
                <div class="summary-card">
                  <div class="summary-label">统计数据</div>
                  <div class="summary-value">
                    共 {{ roomRanking.length }} 个房间
                  </div>
                  <div class="summary-value">
                    总消费：¥ {{ formatMoney(roomRanking.reduce((sum, i) => sum + Number(i.total_cost || 0), 0)) }}
                  </div>
                  <div class="summary-value">
                    总用量：{{ formatMoney(roomRanking.reduce((sum, i) => sum + Number(i.total_usage || 0), 0)) }}
                  </div>
                </div>
              </div>
              <el-table :data="roomRanking" stripe border empty-text="暂无数据" max-height="520">
                <el-table-column type="index" label="排名" width="70" />
                <el-table-column label="校区" min-width="120">
                  <template #default="{ row }">{{ row.campus_name || '--' }}</template>
                </el-table-column>
                <el-table-column label="楼栋" min-width="120">
                  <template #default="{ row }">{{ row.building_name || '--' }}</template>
                </el-table-column>
                <el-table-column label="房间" min-width="100">
                  <template #default="{ row }">{{ row.room_no || row.room_name || '--' }}</template>
                </el-table-column>
                <el-table-column label="消费笔数" width="100">
                  <template #default="{ row }">{{ row.count || 0 }}</template>
                </el-table-column>
                <el-table-column label="总用量" min-width="100">
                  <template #default="{ row }">{{ formatMoney(row.total_usage) }}</template>
                </el-table-column>
                <el-table-column label="总金额(元)" min-width="120">
                  <template #default="{ row }">
                    <span style="font-weight: 600; color: #e67e22">¥ {{ formatMoney(row.total_cost) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="按楼栋能耗排行" name="building-ranking">
              <div class="form-grid" style="margin-bottom: 14px">
                <SimpleBarChart title="TOP 10 楼栋消费金额（元）" :items="buildingRankingChart" color="#2b9f6c" />
                <div class="summary-card">
                  <div class="summary-label">统计数据</div>
                  <div class="summary-value">
                    共 {{ buildingRanking.length }} 栋楼
                  </div>
                  <div class="summary-value">
                    总消费：¥ {{ formatMoney(buildingRanking.reduce((sum, i) => sum + Number(i.total_cost || 0), 0)) }}
                  </div>
                  <div class="summary-value">
                    总用量：{{ formatMoney(buildingRanking.reduce((sum, i) => sum + Number(i.total_usage || 0), 0)) }}
                  </div>
                </div>
              </div>
              <el-table :data="buildingRanking" stripe border empty-text="暂无数据" max-height="520">
                <el-table-column type="index" label="排名" width="70" />
                <el-table-column label="校区" min-width="120">
                  <template #default="{ row }">{{ row.campus_name || '--' }}</template>
                </el-table-column>
                <el-table-column label="楼栋" min-width="140">
                  <template #default="{ row }">{{ row.building_name || '--' }}</template>
                </el-table-column>
                <el-table-column label="消费笔数" width="100">
                  <template #default="{ row }">{{ row.count || 0 }}</template>
                </el-table-column>
                <el-table-column label="房间数" width="100">
                  <template #default="{ row }">{{ row.room_count || 0 }}</template>
                </el-table-column>
                <el-table-column label="总用量" min-width="100">
                  <template #default="{ row }">{{ formatMoney(row.total_usage) }}</template>
                </el-table-column>
                <el-table-column label="总金额(元)" min-width="120">
                  <template #default="{ row }">
                    <span style="font-weight: 600; color: #e67e22">¥ {{ formatMoney(row.total_cost) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="月度趋势" name="monthly-trend">
              <div style="margin-bottom: 12px">
                <el-radio-group v-model="filters.group_by" @change="loadMonthlyTrend">
                  <el-radio-button label="building">按楼栋</el-radio-button>
                  <el-radio-button label="room">按房间</el-radio-button>
                </el-radio-group>
              </div>
              <div class="form-grid" style="margin-bottom: 14px">
                <SimpleBarChart title="月度消费金额趋势（元）" :items="monthlyTrendChart" color="#9b59b6" />
                <div class="summary-card">
                  <div class="summary-label">趋势统计</div>
                  <div class="summary-value">
                    共 {{ monthlyTrendChart.length }} 个月份
                  </div>
                  <div class="summary-value">
                    总消费：¥ {{ formatMoney(monthlyTrend.reduce((sum, i) => sum + Number(i.total_cost || 0), 0)) }}
                  </div>
                  <div class="summary-value">
                    月均消费：¥ {{ formatMoney(monthlyTrendChart.length ? monthlyTrend.reduce((sum, i) => sum + Number(i.total_cost || 0), 0) / monthlyTrendChart.length : 0) }}
                  </div>
                </div>
              </div>
              <el-table :data="monthlyTrend" stripe border empty-text="暂无数据" max-height="520">
                <el-table-column label="月份" min-width="120">
                  <template #default="{ row }">{{ row.month || row.period || '--' }}</template>
                </el-table-column>
                <el-table-column v-if="filters.group_by === 'building'" label="楼栋" min-width="140">
                  <template #default="{ row }">{{ row.building_name || '--' }}</template>
                </el-table-column>
                <el-table-column v-if="filters.group_by === 'room'" label="房间" min-width="120">
                  <template #default="{ row }">{{ row.room_no || row.room_name || '--' }}</template>
                </el-table-column>
                <el-table-column label="消费笔数" width="100">
                  <template #default="{ row }">{{ row.count || 0 }}</template>
                </el-table-column>
                <el-table-column label="总用量" min-width="100">
                  <template #default="{ row }">{{ formatMoney(row.total_usage) }}</template>
                </el-table-column>
                <el-table-column label="总金额(元)" min-width="120">
                  <template #default="{ row }">
                    <span style="font-weight: 600; color: #e67e22">¥ {{ formatMoney(row.total_cost) }}</span>
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

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 14px;
}
@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
.summary-card {
  background: #f7f9fc;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 4px;
}
.summary-value {
  font-size: 14px;
  color: var(--text-sub);
}
</style>
