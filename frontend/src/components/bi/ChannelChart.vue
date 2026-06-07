<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
})

const channelColors = {
  manual: '#2d73da',
  ic_card: '#f0a020',
  online: '#2b9f6c',
  smart_meter: '#9b59b6',
}

function getColor(ch) {
  return channelColors[ch] || '#6c7a89'
}

const maxCost = computed(() =>
  Math.max(0, ...props.data.map((d) => Number(d.total_cost || 0)))
)

function barWidth(cost) {
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
        <div class="s-label">渠道数</div>
        <div class="s-value">{{ summary.channel_count || 0 }}</div>
      </div>
    </div>

    <div v-if="!data.length" class="empty">暂无数据</div>
    <div v-else>
      <div class="pie-row">
        <svg viewBox="0 0 200 200" class="pie-svg">
          <g transform="translate(100, 100)">
            <circle r="70" fill="#f4f7fd" />
            <g v-if="total > 0">
              <path
                v-for="(slice, idx) in (function () {
                  const arr = []
                  let start = -Math.PI / 2
                  data.forEach((d) => {
                    const angle = (Number(d.total_cost) / total) * Math.PI * 2
                    arr.push({
                      d,
                      path: describeArc(0, 0, 70, start, start + angle),
                      color: getColor(d.channel),
                    })
                    start += angle
                  })
                  return arr
                })()"
                :key="idx"
                :d="slice.path"
                :fill="slice.color"
                stroke="#fff"
                stroke-width="2"
              />
            </g>
            <circle r="38" fill="#fff" />
            <text text-anchor="middle" y="-2" font-size="11" fill="#8a94a6">总金额</text>
            <text text-anchor="middle" y="14" font-size="15" font-weight="700" fill="#2d3748">¥ {{ total.toFixed(0) }}</text>
          </g>
        </svg>
        <div class="legend">
          <div v-for="item in data" :key="item.channel" class="legend-item">
            <span class="legend-dot" :style="{ background: getColor(item.channel) }"></span>
            <span class="legend-label">{{ item.channel_label }}</span>
            <span class="legend-pct">{{ item.percentage.toFixed(1) }}%</span>
          </div>
        </div>
      </div>

      <div class="ch-list">
        <div v-for="item in data" :key="item.channel" class="ch-row">
          <div class="ch-label">
            <span class="ch-dot" :style="{ background: getColor(item.channel) }"></span>
            {{ item.channel_label }}
          </div>
          <div class="ch-bar-wrap">
            <div class="ch-bar" :style="{ width: `${barWidth(item.total_cost)}%`, background: getColor(item.channel) }"></div>
          </div>
          <div class="ch-cost">¥ {{ Number(item.total_cost).toFixed(2) }} ({{ item.count }}笔)</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
function polarToCartesian(cx, cy, r, angleRad) {
  return {
    x: cx + r * Math.cos(angleRad),
    y: cy + r * Math.sin(angleRad),
  }
}
function describeArc(cx, cy, r, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, r, endAngle)
  const end = polarToCartesian(cx, cy, r, startAngle)
  const largeArcFlag = endAngle - startAngle <= Math.PI ? '0' : '1'
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y} L ${cx} ${cy} Z`
}
export default { methods: { describeArc } }
</script>

<style scoped>
.chart-wrap {
  display: flex;
  flex-direction: column;
  gap: 14px;
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
.empty {
  color: var(--text-sub);
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}
.pie-row {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 14px;
}
.pie-svg {
  width: 180px;
  height: 180px;
  flex-shrink: 0;
}
.legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}
.legend-label {
  color: var(--text-main);
  min-width: 70px;
}
.legend-pct {
  color: var(--text-sub);
  font-weight: 600;
  margin-left: auto;
}
.ch-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ch-row {
  display: grid;
  grid-template-columns: 90px 1fr 180px;
  align-items: center;
  gap: 10px;
}
.ch-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-main);
}
.ch-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ch-bar-wrap {
  height: 8px;
  background: #ebf1fb;
  border-radius: 999px;
  overflow: hidden;
}
.ch-bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.4s;
}
.ch-cost {
  font-size: 12px;
  color: var(--text-sub);
  text-align: right;
}
</style>
