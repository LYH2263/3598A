<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
})

const categoryColors = {
  water: '#2d73da',
  electricity: '#f0a020',
}

function getColor(cat) {
  return categoryColors[cat] || '#2b9f6c'
}

const maxCost = computed(() =>
  Math.max(0, ...props.data.map((d) => Number(d.total_cost || 0)))
)

function barWidth(cost) {
  if (maxCost.value <= 0) return 0
  return Math.max(4, Math.round((Number(cost) / maxCost.value) * 100))
}
</script>

<template>
  <div class="chart-wrap">
    <div class="summary-row">
      <div class="summary-item">
        <div class="s-label">总金额</div>
        <div class="s-value">¥ {{ Number(summary.grand_total || 0).toFixed(2) }}</div>
      </div>
      <div class="summary-item">
        <div class="s-label">类目数</div>
        <div class="s-value">{{ summary.category_count || 0 }}</div>
      </div>
      <div class="summary-item">
        <div class="s-label">总笔数</div>
        <div class="s-value">{{ summary.record_count || 0 }}</div>
      </div>
    </div>

    <div v-if="!data.length" class="empty">暂无数据</div>
    <div v-else class="cat-list">
      <div v-for="item in data" :key="item.category" class="cat-row">
        <div class="cat-left">
          <div class="cat-dot" :style="{ background: getColor(item.category) }"></div>
          <div class="cat-label">{{ item.category_label }}</div>
          <div class="cat-pct">{{ item.percentage.toFixed(1) }}%</div>
        </div>
        <div class="cat-bar-wrap">
          <div
            class="cat-bar"
            :style="{
              width: `${barWidth(item.total_cost)}%`,
              background: getColor(item.category),
            }"
          ></div>
        </div>
        <div class="cat-right">
          <div class="cat-cost">¥ {{ Number(item.total_cost).toFixed(2) }}</div>
          <div class="cat-meta">{{ item.count }}笔 / 均¥{{ Number(item.avg_cost).toFixed(2) }}</div>
        </div>
      </div>
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
}
.s-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
  margin-top: 4px;
}
.empty {
  color: var(--text-sub);
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}
.cat-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cat-row {
  display: grid;
  grid-template-columns: 160px 1fr 140px;
  align-items: center;
  gap: 12px;
}
.cat-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cat-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.cat-label {
  font-size: 13px;
  color: var(--text-main);
  font-weight: 500;
}
.cat-pct {
  font-size: 12px;
  color: var(--text-sub);
  margin-left: auto;
}
.cat-bar-wrap {
  height: 10px;
  background: #ebf1fb;
  border-radius: 999px;
  overflow: hidden;
}
.cat-bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.4s ease;
}
.cat-right {
  text-align: right;
}
.cat-cost {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}
.cat-meta {
  font-size: 11px;
  color: var(--text-sub);
  margin-top: 2px;
}
</style>
