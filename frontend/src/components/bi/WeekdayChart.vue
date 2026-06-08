<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
})

const maxCost = computed(() => {
  const vals = props.data.map((x) => Number(x.total_cost) || 0)
  return Math.max(1, ...vals)
})

const barMaxHeight = 160

function barHeight(val) {
  return Math.max(4, (Number(val) / maxCost.value) * barMaxHeight)
}

function fmt(n) {
  return (Number(n) || 0).toFixed(2)
}
</script>

<template>
  <div class="wp-wrap">
    <div class="wp-summary">
      <div class="wp-stat">
        <div class="wp-stat-label">总消费</div>
        <div class="wp-stat-value">¥ {{ fmt(summary.grand_total) }}</div>
      </div>
      <div class="wp-stat">
        <div class="wp-stat-label">消费高峰</div>
        <div class="wp-stat-value peak">{{ summary.peak_weekday_label || '—' }}</div>
      </div>
      <div class="wp-stat">
        <div class="wp-stat-label">统计天数</div>
        <div class="wp-stat-value">{{ data.length }}</div>
      </div>
    </div>

    <div class="wp-chart">
      <div v-for="d in data" :key="d.weekday" class="wp-col">
        <div class="wp-bar-stack">
          <div
            class="wp-bar wp-bar-water"
            :style="{ height: barHeight(d.water_cost) + 'px' }"
            :title="`水费 ¥${fmt(d.water_cost)}`"
          ></div>
          <div
            class="wp-bar wp-bar-elec"
            :style="{ height: barHeight(d.electricity_cost) + 'px' }"
            :title="`电费 ¥${fmt(d.electricity_cost)}`"
          ></div>
        </div>
        <div class="wp-amount">¥ {{ fmt(d.total_cost) }}</div>
        <div class="wp-label">{{ d.weekday_label }}</div>
        <div class="wp-sub">{{ d.count }} 笔 · {{ fmt(d.total_usage) }}</div>
      </div>
    </div>

    <div class="wp-legend">
      <span class="lg-item"><i class="lg-dot" style="background:#2d73da"></i>水费</span>
      <span class="lg-item"><i class="lg-dot" style="background:#f0a020"></i>电费</span>
    </div>
  </div>
</template>

<style scoped>
.wp-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.wp-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.wp-stat {
  background: #f7f9ff;
  border-radius: 8px;
  padding: 10px 12px;
}
.wp-stat-label {
  font-size: 12px;
  color: #6b7280;
}
.wp-stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
  margin-top: 2px;
}
.wp-stat-value.peak {
  color: #e67e22;
}
.wp-chart {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
  align-items: end;
}
.wp-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.wp-bar-stack {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 160px;
}
.wp-bar {
  width: 16px;
  border-radius: 4px 4px 0 0;
  transition: height 0.3s;
}
.wp-bar-water {
  background: linear-gradient(180deg, #4f8eff, #2d73da);
}
.wp-bar-elec {
  background: linear-gradient(180deg, #ffc46b, #f0a020);
}
.wp-amount {
  font-size: 12px;
  font-weight: 600;
  color: #1f4ed3;
}
.wp-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.wp-sub {
  font-size: 11px;
  color: #94a3b8;
}
.wp-legend {
  display: flex;
  gap: 14px;
  justify-content: flex-end;
  padding-top: 4px;
  border-top: 1px solid #eef2fb;
}
.lg-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
}
.lg-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}
</style>
