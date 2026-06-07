<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  topN: { type: Number, default: 10 },
})

const maxCost = computed(() =>
  Math.max(0, ...props.data.map((d) => Number(d.total_cost || 0)))
)

function barWidth(cost) {
  if (maxCost.value <= 0) return 0
  return Math.max(4, Math.round((Number(cost) / maxCost.value) * 100))
}

function rankClass(rank) {
  if (rank === 1) return 'rank-gold'
  if (rank === 2) return 'rank-silver'
  if (rank === 3) return 'rank-bronze'
  return ''
}
</script>

<template>
  <div class="chart-wrap">
    <div v-if="!data.length" class="empty">暂无数据</div>
    <el-table v-else :data="data" size="default" border stripe>
      <el-table-column label="排名" width="70" align="center">
        <template #default="{ row }">
          <span class="rank-badge" :class="rankClass(row.rank)">{{ row.rank }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="username" label="用户名" min-width="110" />
      <el-table-column prop="student_id" label="学号" min-width="110" />
      <el-table-column label="消费金额" min-width="220">
        <template #default="{ row }">
          <div class="bar-cell">
            <div class="bar-wrap">
              <div
                class="bar-fill"
                :style="{ width: `${barWidth(row.total_cost)}%` }"
              ></div>
            </div>
            <span class="bar-value">¥ {{ Number(row.total_cost).toFixed(2) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="水费(元)" width="100" align="right">
        <template #default="{ row }">{{ Number(row.water_cost).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="电费(元)" width="100" align="right">
        <template #default="{ row }">{{ Number(row.electricity_cost).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="笔数" width="80" align="center" prop="count" />
    </el-table>
  </div>
</template>

<style scoped>
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
.rank-badge {
  display: inline-block;
  width: 28px;
  height: 28px;
  line-height: 28px;
  border-radius: 50%;
  background: #eef2f8;
  color: var(--text-sub);
  font-weight: 700;
  font-size: 13px;
  text-align: center;
}
.rank-gold {
  background: linear-gradient(135deg, #ffd700, #ffb300);
  color: #fff;
}
.rank-silver {
  background: linear-gradient(135deg, #c0c0c0, #9a9a9a);
  color: #fff;
}
.rank-bronze {
  background: linear-gradient(135deg, #cd7f32, #a46323);
  color: #fff;
}
.bar-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.bar-wrap {
  flex: 1;
  height: 8px;
  background: #ebf1fb;
  border-radius: 999px;
  overflow: hidden;
  min-width: 60px;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #2d73da, #5b9cf0);
  border-radius: 999px;
  transition: width 0.4s;
}
.bar-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  min-width: 85px;
  text-align: right;
}
</style>
