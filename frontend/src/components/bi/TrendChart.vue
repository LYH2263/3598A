<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
  granularity: { type: String, default: 'day' },
  compareData: { type: Object, default: null },
})

const maxCost = computed(() => {
  const all = props.data.map((d) => Number(d.total_cost || 0))
  if (props.compareData?.comparison) {
    props.compareData.comparison.forEach((c) => {
      all.push(Number(c.period_a_cost || 0), Number(c.period_b_cost || 0))
    })
  }
  return Math.max(10, ...all)
})

const chartWidth = 800
const chartHeight = 240
const padding = { top: 20, right: 20, bottom: 40, left: 50 }
const innerW = computed(() => chartWidth - padding.left - padding.right)
const innerH = computed(() => chartHeight - padding.top - padding.bottom)

function xPos(i, total) {
  if (total <= 1) return padding.left + innerW.value / 2
  return padding.left + (i / (total - 1)) * innerW.value
}
function yPos(val) {
  return padding.top + innerH.value - (Number(val) / maxCost.value) * innerH.value
}

function polylinePoints(arr, key) {
  return arr
    .map((d, i) => `${xPos(i, arr.length)},${yPos(d[key] || 0)}`)
    .join(' ')
}

function yTicks() {
  const n = 5
  return Array.from({ length: n + 1 }, (_, i) => {
    const v = (maxCost.value / n) * i
    return { v: v.toFixed(0), y: yPos(v) }
  })
}

const periods = computed(() => {
  if (props.compareData?.comparison?.length) {
    return props.compareData.comparison.map((c) => c.period)
  }
  return props.data.map((d) => d.period)
})

const seriesA = computed(() => {
  if (props.compareData?.comparison?.length) {
    return props.compareData.comparison.map((c) => ({ period: c.period, total_cost: c.period_a_cost }))
  }
  return props.data
})
const seriesB = computed(() => {
  if (!props.compareData?.comparison?.length) return null
  return props.compareData.comparison.map((c) => ({ period: c.period, total_cost: c.period_b_cost }))
})

function growthClass(rate) {
  if (rate == null) return 'neutral'
  return rate >= 0 ? 'up' : 'down'
}
</script>

<template>
  <div class="chart-wrap">
    <div class="summary-row">
      <div class="summary-item">
        <div class="s-label">
          <span class="legend-dot" style="background: #2d73da"></span>
          当前周期总额
        </div>
        <div class="s-value">
          ¥ {{ Number(compareData ? compareData.period_a.total_cost : summary.total_cost || 0).toFixed(2) }}
        </div>
      </div>
      <div v-if="compareData" class="summary-item">
        <div class="s-label">
          <span class="legend-dot" style="background: #2b9f6c"></span>
          对比周期总额
        </div>
        <div class="s-value">
          ¥ {{ Number(compareData.period_b.total_cost).toFixed(2) }}
        </div>
      </div>
      <div v-if="compareData" class="summary-item">
        <div class="s-label">增长率</div>
        <div class="s-value" :class="growthClass(compareData.growth_rate)">
          <template v-if="compareData.growth_rate != null">
            {{ compareData.growth_rate >= 0 ? '+' : '' }}{{ compareData.growth_rate }}%
          </template>
          <template v-else>—</template>
        </div>
      </div>
      <div v-else class="summary-item">
        <div class="s-label">周期数</div>
        <div class="s-value">{{ summary.period_count || 0 }}</div>
      </div>
    </div>

    <div v-if="!periods.length" class="empty">暂无数据</div>
    <div v-else class="trend-svg-wrap">
      <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="trend-svg" preserveAspectRatio="xMidYMid meet">
        <g class="y-axis">
          <line
            v-for="tick in yTicks()"
            :key="tick.v"
            :x1="padding.left"
            :x2="chartWidth - padding.right"
            :y1="tick.y"
            :y2="tick.y"
            stroke="#eef2f8"
            stroke-width="1"
          />
          <text
            v-for="tick in yTicks()"
            :key="'t' + tick.v"
            :x="padding.left - 6"
            :y="tick.y + 4"
            text-anchor="end"
            font-size="10"
            fill="#8a94a6"
          >{{ tick.v }}</text>
        </g>
        <g>
          <polyline
            :points="polylinePoints(seriesA, 'total_cost')"
            fill="none"
            stroke="#2d73da"
            stroke-width="2.5"
          />
          <circle
            v-for="(d, i) in seriesA"
            :key="'a' + i"
            :cx="xPos(i, seriesA.length)"
            :cy="yPos(d.total_cost)"
            r="3.5"
            fill="#2d73da"
          />
          <polyline
            v-if="seriesB"
            :points="polylinePoints(seriesB, 'total_cost')"
            fill="none"
            stroke="#2b9f6c"
            stroke-width="2.5"
            stroke-dasharray="5 3"
          />
          <circle
            v-for="(d, i) in seriesB || []"
            :key="'b' + i"
            :cx="xPos(i, seriesB.length)"
            :cy="yPos(d.total_cost)"
            r="3.5"
            fill="#2b9f6c"
          />
        </g>
        <g class="x-axis">
          <text
            v-for="(p, i) in periods"
            :key="p + i"
            :x="xPos(i, periods.length)"
            :y="chartHeight - padding.bottom + 16"
            text-anchor="middle"
            font-size="10"
            fill="#8a94a6"
          >{{ periods.length > 15 && i % Math.ceil(periods.length / 10) !== 0 ? '' : p }}</text>
        </g>
      </svg>
    </div>

    <div v-if="compareData?.comparison?.length" class="compare-table-wrap">
      <el-table :data="compareData.comparison" size="small" border max-height="220">
        <el-table-column prop="period" label="周期" min-width="120" />
        <el-table-column label="当前(元)" min-width="110">
          <template #default="{ row }">¥ {{ Number(row.period_a_cost).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="对比(元)" min-width="110">
          <template #default="{ row }">¥ {{ Number(row.period_b_cost).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="增长率" min-width="100">
          <template #default="{ row }">
            <el-tag v-if="row.cost_growth_rate != null" :type="row.cost_growth_rate >= 0 ? 'success' : 'danger'" size="small" effect="plain">
              {{ row.cost_growth_rate >= 0 ? '+' : '' }}{{ row.cost_growth_rate }}%
            </el-tag>
            <span v-else style="color: var(--text-sub)">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.chart-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.summary-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.summary-item {
  padding: 10px 12px;
  background: #f4f7fd;
  border-radius: 8px;
}
.s-label {
  font-size: 12px;
  color: var(--text-sub);
  display: flex;
  align-items: center;
  gap: 6px;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.s-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
  margin-top: 4px;
}
.s-value.up {
  color: #f56c6c;
}
.s-value.down {
  color: #67c23a;
}
.s-value.neutral {
  color: var(--text-sub);
}
.empty {
  color: var(--text-sub);
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}
.trend-svg-wrap {
  width: 100%;
  background: #fafbfe;
  border-radius: 8px;
  padding: 8px;
}
.trend-svg {
  width: 100%;
  height: auto;
  max-height: 280px;
}
.compare-table-wrap {
  margin-top: 4px;
}
</style>
