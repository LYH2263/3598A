<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'

import BICard from '../components/bi/BICard.vue'
import TrendChart from '../components/bi/TrendChart.vue'
import TimePeriodChart from '../components/bi/TimePeriodChart.vue'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(true)

const profile = reactive({
  category_breakdown: {
    water: { cost: 0, percentage: 0 },
    electricity: { cost: 0, percentage: 0 },
    total_cost: 0,
    total_count: 0,
  },
  peak_period: null,
  peak_period_label: '—',
  time_period_distribution: [],
  monthly_trend: [],
  summary: {
    avg_monthly_cost: 0,
    total_cost: 0,
  },
})

const categoryTotal = computed(() => Number(profile.category_breakdown.total_cost || 0))
const waterPct = computed(() => {
  const t = categoryTotal.value
  return t > 0 ? Math.round((Number(profile.category_breakdown.water.cost) / t) * 100) : 0
})
const elecPct = computed(() => {
  const t = categoryTotal.value
  return t > 0 ? Math.round((Number(profile.category_breakdown.electricity.cost) / t) * 100) : 0
})

const trendSummary = computed(() => ({
  total_cost: profile.summary.total_cost,
  period_count: profile.monthly_trend.length,
}))

async function loadProfile() {
  loading.value = true
  try {
    const { data } = await http.get('/billing/bi/my-profile/')
    Object.assign(profile, data)
  } catch (_e) {
    // 错误已由 http 拦截器处理
  } finally {
    loading.value = false
  }
}

function handleExport() {
  http
    .get('/billing/bi/export-csv/?view=my_profile', { responseType: 'blob' })
    .then((res) => {
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8-sig' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      const ts = new Date().toISOString().slice(0, 10)
      link.download = `my_analytics_${ts}.csv`
      link.click()
      URL.revokeObjectURL(link.href)
    })
    .catch((e) => {
      ElNotification({ title: '导出失败', message: e?.response?.data?.detail || String(e), type: 'error' })
    })
}

function describeArc(cx, cy, r, startAngle, endAngle) {
  function polarToCartesian(cx, cy, r, angleRad) {
    return { x: cx + r * Math.cos(angleRad), y: cy + r * Math.sin(angleRad) }
  }
  const start = polarToCartesian(cx, cy, r, endAngle)
  const end = polarToCartesian(cx, cy, r, startAngle)
  const largeArcFlag = endAngle - startAngle <= Math.PI ? '0' : '1'
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y} L ${cx} ${cy} Z`
}

const donutSlices = computed(() => {
  const total = categoryTotal.value
  if (total <= 0) return []
  const arr = []
  let start = -Math.PI / 2
  const items = [
    { key: 'water', cost: profile.category_breakdown.water.cost, color: '#2d73da', label: '水费' },
    { key: 'electricity', cost: profile.category_breakdown.electricity.cost, color: '#f0a020', label: '电费' },
  ]
  items.forEach((it) => {
    const angle = (Number(it.cost) / total) * Math.PI * 2
    arr.push({
      ...it,
      path: describeArc(100, 100, 70, start, start + angle),
    })
    start += angle
  })
  return arr
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
  await loadProfile()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :xs="24" :sm="18">
          <h2 class="section-title">我的消费分析</h2>
          <p style="margin: 0; color: var(--text-sub)">
            个人画像 · 水电占比 · 用电高峰 · 月度趋势
          </p>
        </el-col>
        <el-col :xs="24" :sm="6" style="text-align: right">
          <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回总览</el-button>
          <el-button style="margin-right: 8px" :loading="loading" @click="loadProfile">刷新数据</el-button>
          <el-button type="primary" @click="handleExport">导出分析报告 CSV</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-skeleton :loading="loading" animated :rows="10">
      <template #default>
        <section class="summary-grid" style="margin-bottom: 14px">
          <article class="summary-card">
            <div class="label">累计消费</div>
            <div class="value">¥ {{ Number(profile.summary.total_cost || 0).toFixed(2) }}</div>
            <div class="summary-note">共 {{ profile.category_breakdown.total_count }} 笔消费记录</div>
          </article>
          <article class="summary-card">
            <div class="label">月均消费</div>
            <div class="value">¥ {{ Number(profile.summary.avg_monthly_cost || 0).toFixed(2) }}</div>
            <div class="summary-note">最近 6 个月均值</div>
          </article>
          <article class="summary-card">
            <div class="label">用电高峰时段</div>
            <div class="value peak">{{ profile.peak_period_label || '—' }}</div>
            <div class="summary-note">根据消费时段分布统计</div>
          </article>
        </section>

        <div class="bi-grid">
          <BICard title="用水 / 用电占比" card-id="category_breakdown" :draggable="false" :loading="loading" export-view="my_profile" @export="handleExport">
            <div class="chart-wrap">
              <div v-if="categoryTotal <= 0" class="empty">暂无消费数据</div>
              <div v-else class="donut-row">
                <svg viewBox="0 0 200 200" class="pie-svg">
                  <g transform="translate(100, 100)">
                    <circle r="70" fill="#f4f7fd" />
                    <path
                      v-for="(slice, idx) in donutSlices"
                      :key="idx"
                      :d="slice.path"
                      :fill="slice.color"
                      stroke="#fff"
                      stroke-width="2"
                    />
                    <circle r="38" fill="#fff" />
                    <text text-anchor="middle" y="-2" font-size="11" fill="#8a94a6">总金额</text>
                    <text text-anchor="middle" y="14" font-size="15" font-weight="700" fill="#2d3748">
                      ¥ {{ categoryTotal.toFixed(0) }}
                    </text>
                  </g>
                </svg>
                <div class="legend">
                  <div class="legend-item">
                    <span class="legend-dot" style="background: #2d73da"></span>
                    <span class="legend-label">水费</span>
                    <span class="legend-pct">{{ waterPct }}%</span>
                  </div>
                  <div class="legend-sub">
                    ¥ {{ Number(profile.category_breakdown.water.cost).toFixed(2) }}
                  </div>
                  <div class="legend-item" style="margin-top: 10px">
                    <span class="legend-dot" style="background: #f0a020"></span>
                    <span class="legend-label">电费</span>
                    <span class="legend-pct">{{ elecPct }}%</span>
                  </div>
                  <div class="legend-sub">
                    ¥ {{ Number(profile.category_breakdown.electricity.cost).toFixed(2) }}
                  </div>
                </div>
              </div>
            </div>
          </BICard>

          <BICard title="消费时段分布" card-id="time_period" :draggable="false" :loading="loading">
            <TimePeriodChart
              :data="profile.time_period_distribution"
              :summary="{ grand_total: profile.summary.total_cost, peak_period_label: profile.peak_period_label }"
            />
          </BICard>

          <BICard title="近 6 个月消费趋势" card-id="monthly_trend" :draggable="false" :loading="loading">
            <TrendChart
              :data="profile.monthly_trend"
              :summary="trendSummary"
              granularity="month"
            />
          </BICard>
        </div>
      </template>
    </el-skeleton>
  </main>
</template>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.summary-card {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(90, 128, 201, 0.16);
  border-radius: 12px;
  padding: 14px 16px;
}
.summary-card .label {
  font-size: 12px;
  color: var(--text-sub);
}
.summary-card .value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-main);
  margin-top: 4px;
}
.summary-card .value.peak {
  color: #e67e22;
}
.summary-card .summary-note {
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 4px;
}
.bi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}
.bi-grid > :last-child {
  grid-column: 1 / -1;
}
@media (max-width: 900px) {
  .bi-grid {
    grid-template-columns: 1fr;
  }
}
.chart-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.empty {
  color: var(--text-sub);
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}
.donut-row {
  display: flex;
  align-items: center;
  gap: 20px;
}
.pie-svg {
  width: 200px;
  height: 200px;
  flex-shrink: 0;
}
.legend {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-main);
  font-weight: 500;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}
.legend-label {
  min-width: 40px;
}
.legend-pct {
  color: var(--text-main);
  font-weight: 700;
  margin-left: auto;
}
.legend-sub {
  font-size: 12px;
  color: var(--text-sub);
  padding-left: 18px;
}
</style>
