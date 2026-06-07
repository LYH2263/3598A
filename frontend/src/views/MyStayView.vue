<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { HomeFilled } from '@element-plus/icons-vue'

import http from '../utils/http'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(true)
const currentStay = ref(null)
const stayHistory = ref([])

const stayStatusMap = {
  active: { label: '在住', type: 'success' },
  ended: { label: '已退宿', type: 'info' },
  cancelled: { label: '已取消', type: 'danger' },
}

function formatDate(value) {
  if (!value) return '--'
  return value
}

async function loadCurrentStay() {
  try {
    const { data } = await http.get('/housing/stays/my/current/')
    currentStay.value = data
  } catch (_e) {
    currentStay.value = null
  }
}

async function loadStayHistory() {
  try {
    const { data } = await http.get('/housing/stays/my/history/')
    stayHistory.value = data
  } catch (_e) {
    stayHistory.value = []
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadCurrentStay(), loadStayHistory()])
  } finally {
    loading.value = false
  }
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
  await refreshAll()
})
</script>

<template>
  <main class="page-shell animated-in">
    <section class="dashboard-wrap">
      <el-card class="section-card" shadow="never">
        <el-row justify="space-between" align="middle" :gutter="12">
          <el-col :xs="24" :sm="18">
            <h2 class="section-title">我的入住</h2>
            <p style="margin: 0; color: var(--text-sub)">
              查看当前床位信息与历史入住记录
            </p>
          </el-col>
          <el-col :xs="24" :sm="6" style="text-align: right">
            <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回首页</el-button>
            <el-button type="primary" :loading="loading" @click="refreshAll">刷新</el-button>
          </el-col>
        </el-row>
      </el-card>

      <el-skeleton :loading="loading" animated :rows="6">
        <template #default>
          <el-card class="section-card" shadow="never">
            <h3 class="section-title">当前床位</h3>
            <template v-if="currentStay">
              <div class="stay-current">
                <div class="stay-current-icon">
                  <el-icon :size="48" color="#2d73da">
                    <HomeFilled />
                  </el-icon>
                </div>
                <div class="stay-current-info">
                  <div class="stay-address">
                    {{ currentStay.campus_name }} · {{ currentStay.building_name }} · {{ currentStay.floor_number }}层 · {{ currentStay.room_no }}室 · {{ currentStay.bed_no }}号床
                  </div>
                  <div class="stay-meta">
                    <el-tag :type="stayStatusMap[currentStay.status]?.type || 'info'" effect="plain" size="large">
                      {{ stayStatusMap[currentStay.status]?.label || currentStay.status }}
                    </el-tag>
                    <span class="stay-date">入住日期：{{ formatDate(currentStay.start_date) }}</span>
                    <span class="stay-date" v-if="currentStay.end_date">退宿日期：{{ formatDate(currentStay.end_date) }}</span>
                  </div>
                  <div class="stay-details" v-if="currentStay.remark">
                    备注：{{ currentStay.remark }}
                  </div>
                </div>
              </div>
              <el-divider />
              <div class="form-grid">
                <div class="info-item">
                  <div class="info-label">校区</div>
                  <div class="info-value">{{ currentStay.campus_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">楼栋</div>
                  <div class="info-value">{{ currentStay.building_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">楼层</div>
                  <div class="info-value">{{ currentStay.floor_number }}层</div>
                </div>
                <div class="info-item">
                  <div class="info-label">房间</div>
                  <div class="info-value">{{ currentStay.room_no }}室</div>
                </div>
                <div class="info-item">
                  <div class="info-label">床位</div>
                  <div class="info-value">{{ currentStay.bed_no }}号</div>
                </div>
                <div class="info-item">
                  <div class="info-label">操作人</div>
                  <div class="info-value">{{ currentStay.operator || '--' }}</div>
                </div>
              </div>
            </template>
            <el-empty v-else description="暂无当前入住记录" />
          </el-card>

          <el-card class="section-card" shadow="never">
            <h3 class="section-title">入住历史</h3>
            <el-table :data="stayHistory" stripe border empty-text="暂无历史记录" max-height="480">
              <el-table-column label="校区" min-width="120">
                <template #default="{ row }">{{ row.campus_name || '--' }}</template>
              </el-table-column>
              <el-table-column label="楼栋" min-width="120">
                <template #default="{ row }">{{ row.building_name || '--' }}</template>
              </el-table-column>
              <el-table-column label="楼层" width="80">
                <template #default="{ row }">{{ row.floor_number ? row.floor_number + '层' : '--' }}</template>
              </el-table-column>
              <el-table-column label="房间" min-width="100">
                <template #default="{ row }">{{ row.room_no ? row.room_no + '室' : '--' }}</template>
              </el-table-column>
              <el-table-column label="床位" min-width="100">
                <template #default="{ row }">{{ row.bed_no ? row.bed_no + '号' : '--' }}</template>
              </el-table-column>
              <el-table-column label="状态" min-width="100">
                <template #default="{ row }">
                  <el-tag :type="stayStatusMap[row.status]?.type || 'info'" effect="plain">
                    {{ stayStatusMap[row.status]?.label || row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="入住日期" min-width="120">
                <template #default="{ row }">{{ formatDate(row.start_date) }}</template>
              </el-table-column>
              <el-table-column label="退宿日期" min-width="120">
                <template #default="{ row }">{{ formatDate(row.end_date) }}</template>
              </el-table-column>
              <el-table-column label="操作人" min-width="120">
                <template #default="{ row }">{{ row.operator || '--' }}</template>
              </el-table-column>
              <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
            </el-table>
          </el-card>
        </template>
      </el-skeleton>
    </section>
  </main>
</template>

<style scoped>
.stay-current {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 0;
}
.stay-current-icon {
  width: 80px;
  height: 80px;
  background: #ebf1fb;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stay-current-info {
  flex: 1;
}
.stay-address {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 8px;
}
.stay-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.stay-date {
  font-size: 13px;
  color: var(--text-sub);
}
.stay-details {
  font-size: 13px;
  color: var(--text-sub);
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}
.info-item {
  background: #f7f9fc;
  border-radius: 10px;
  padding: 12px 14px;
}
.info-label {
  font-size: 12px;
  color: var(--text-sub);
  margin-bottom: 4px;
}
.info-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
}
</style>
