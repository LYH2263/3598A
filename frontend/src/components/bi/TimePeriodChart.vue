<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
})

const periodColors = {
  morning: '#ffb74d',
  noon: '#4fc3f7',
  evening: '#7986cb',
  night: '#5c6bc0',
}

function getColor(p) {
  return periodColors[p] || '#90a4ae'
}

const maxCost = computed(() =>
  Math.max(0, ...props.data.map((d) => Number(d.total_cost || 0)))
)

function barHeight(cost) {
  if (maxCost.value <= 0) return 0
  return Math.max(4, Math.round((Number(cost) / maxCost.value) * 100))
}

const total = computed(() => Number(props.summary.grand_total || 0))
</script>

<template>
  <div class="chart-wrap">
    <div class="summary-row">
      <div class="summary-item">
        <div class="s-label">总金额</div>
        <div class="s-value">¥ {{ total.toFixed(2) }}</div>
      </div>
      <div class="summary-item">
        <div class="s-label">用电高峰时段</div>
        <div class="s-value peak">{{ summary.peak_period_label || '—' }}</div>
      </div>
    </div>

    <div v-if="!data.length" class="empty">暂无数据</div>
    <div v-else>
      <div class="bar-chart">
        <div
          v-for="item in data"
          :key="item.period"
          class="bar-col"
        >
          <div class="bar-value-top">¥ {{ Number(item.total_cost).toFixed(2) }}</div>
          <div class="bar-outer">
            <div
              class="bar-inner"
              :style="{
                height: `${barHeight(item.total_cost)}%`,
                background: getColor(item.period),
              }"
            ></div>
          </div>
          <div class="bar-label">{{ item.period_label }}</div>
          <div class="bar-pct">{{ item.percentage.toFixed(1) }}%</div>
        </div>
      </div>

      <el-divider style="margin: 14px 0" />

      <div class="detail-grid">
        <div v-for="item in data" :key="'d' + item.period" class="detail-card">
          <div class="det-header">
            <span class="det-dot" :style="{ background: getColor(item.period) }"></span>
            <span class="det-title">{{ item.period_label }}</span>
            <span class="det-pct">{{ item.percentage.toFixed(1) }}%</span>
          </div>
          <div class="det-row">
            <div>
              <div class="det-lbl">水费</div>
              <div class="det-val">¥ {{ Number(item.water_cost).toFixed(2) }}</div>
            </div>
            <div>
              <div class="det-lbl">电费</div>
              <div class="det-val">¥ {{ Number(item.electricity_cost).toFixed(2) }}</div>
            </div>
            <div>
              <div class="det-lbl">笔数</div>
              <div class="det-val">{{ item.count }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.summary-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
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
}
.s-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
  margin-top: 4px;
}
.s-value.peak {
  color: #e67e22;
}
.empty {
  color: var(--text-sub);
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}
.bar-chart {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  gap: 14px;
  height: 200px;
  padding: 10px 10px 0;
  background: #fafbfe;
  border-radius: 8px;
}
.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  height: 100%;
  gap: 4px;
}
.bar-value-top {
  font-size: 11px;
  color: var(--text-sub);
  font-weight: 600;
}
.bar-outer {
  width: 100%;
  max-width: 60px;
  height: 120px;
  background: #ebf1fb;
  border-radius: 6px 6px 2px 2px;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}
.bar-inner {
  width: 100%;
  border-radius: 6px 6px 0 0;
  transition: height 0.4s;
}
.bar-label {
  font-size: 12px;
  color: var(--text-main);
  font-weight: 500;
}
.bar-pct {
  font-size: 11px;
  color: var(--text-sub);
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}
.detail-card {
  padding: 10px 12px;
  background: #fff;
  border: 1px solid rgba(90, 128, 201, 0.16);
  border-radius: 8px;
}
.det-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.det-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.det-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}
.det-pct {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-sub);
  font-weight: 600;
}
.det-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.det-lbl {
  font-size: 11px;
  color: var(--text-sub);
}
.det-val {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  margin-top: 2px;
}
</style>
