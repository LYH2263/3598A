<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  buildings: { type: Array, default: () => [] },
  rooms: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
})

const activeTab = ref('buildings')

const maxBuildingCost = computed(() =>
  Math.max(0, ...props.buildings.map((d) => Number(d.total_cost || 0)))
)
const maxRoomCost = computed(() =>
  Math.max(0, ...props.rooms.map((d) => Number(d.total_cost || 0)))
)

function buildingBarWidth(cost) {
  if (maxBuildingCost.value <= 0) return 0
  return Math.max(4, Math.round((Number(cost) / maxBuildingCost.value) * 100))
}
function roomBarWidth(cost) {
  if (maxRoomCost.value <= 0) return 0
  return Math.max(4, Math.round((Number(cost) / maxRoomCost.value) * 100))
}
</script>

<template>
  <div class="chart-wrap">
    <div class="summary-row">
      <div class="summary-item">
        <div class="s-label">楼栋数</div>
        <div class="s-value">{{ summary.building_count || 0 }}</div>
      </div>
      <div class="summary-item">
        <div class="s-label">房间数</div>
        <div class="s-value">{{ summary.room_count || 0 }}</div>
      </div>
      <div class="summary-item">
        <div class="s-label">未绑定空间</div>
        <div class="s-value">{{ summary.no_space_count || 0 }}笔</div>
      </div>
    </div>

    <el-tabs v-model="activeTab" size="small">
      <el-tab-pane label="按楼栋" name="buildings">
        <div v-if="!buildings.length" class="empty">暂无楼栋数据（消费记录未绑定楼栋）</div>
        <div v-else class="list">
          <div v-for="item in buildings" :key="item.building" class="row">
            <div class="label">
              <el-icon style="color: #2d73da"><OfficeBuilding /></el-icon>
              <span>{{ item.building }}</span>
            </div>
            <div class="bar-wrap">
              <div class="bar-fill" :style="{ width: `${buildingBarWidth(item.total_cost)}%` }"></div>
            </div>
            <div class="meta">
              <div class="cost">¥ {{ Number(item.total_cost).toFixed(2) }}</div>
              <div class="sub">{{ item.room_count }}间 / {{ item.count }}笔</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="按房间" name="rooms">
        <div v-if="!rooms.length" class="empty">暂无房间数据（消费记录未绑定房间）</div>
        <el-table v-else :data="rooms" size="small" border stripe max-height="320">
          <el-table-column prop="building" label="楼栋" min-width="100" />
          <el-table-column prop="room" label="房间" min-width="100" />
          <el-table-column label="消费金额" min-width="200">
            <template #default="{ row }">
              <div class="bar-cell">
                <div class="bar-wrap-sm">
                  <div class="bar-fill" :style="{ width: `${roomBarWidth(row.total_cost)}%` }"></div>
                </div>
                <span>¥ {{ Number(row.total_cost).toFixed(2) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="用量" width="100" align="right">
            <template #default="{ row }">{{ Number(row.total_usage).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="count" label="笔数" width="80" align="center" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
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
.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 320px;
  overflow-y: auto;
}
.row {
  display: grid;
  grid-template-columns: 120px 1fr 140px;
  align-items: center;
  gap: 12px;
}
.label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-main);
  font-weight: 500;
}
.bar-wrap {
  height: 10px;
  background: #ebf1fb;
  border-radius: 999px;
  overflow: hidden;
}
.bar-wrap-sm {
  flex: 1;
  height: 8px;
  background: #ebf1fb;
  border-radius: 999px;
  overflow: hidden;
  min-width: 50px;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #2d73da, #5b9cf0);
  border-radius: 999px;
  transition: width 0.4s;
}
.meta {
  text-align: right;
}
.cost {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}
.sub {
  font-size: 11px;
  color: var(--text-sub);
}
.bar-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 500;
}
</style>
