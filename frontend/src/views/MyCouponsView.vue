<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElNotification } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const authStore = useAuthStore()

const loading = ref(true)
const activeStatus = ref('available')

const coupons = ref([])

const statusMap = {
  available: { label: '可用', type: 'success' },
  used: { label: '已用', type: 'info' },
  expired: { label: '已过期', type: 'warning' },
  revoked: { label: '已回收', type: 'danger' },
}

const tabs = [
  { key: 'available', label: '可用' },
  { key: 'used', label: '已用' },
  { key: 'expired', label: '已过期' },
]

function formatMoney(value) {
  const v = Number(value ?? 0)
  if (Number.isNaN(v)) return '0.00'
  return v.toFixed(2)
}

function formatDateTime(value) {
  if (!value) return '--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(d)
}

const filteredCoupons = computed(() => {
  if (!activeStatus.value) return coupons.value
  return coupons.value.filter(c => c.status === activeStatus.value)
})

function couponValueText(coupon) {
  const d = coupon.coupon_detail || {}
  if (d.coupon_type === 'fixed') return `¥${formatMoney(d.face_value)}`
  if (d.coupon_type === 'percent') return `${(Number(d.discount_rate) * 10).toFixed(1)}折`
  return '优惠券'
}

function couponConditionText(coupon) {
  const d = coupon.coupon_detail || {}
  const min = Number(d.min_amount || 0)
  return min > 0 ? `满¥${formatMoney(min)}可用` : '无门槛'
}

async function loadCoupons() {
  try {
    const { data } = await http.get('/marketing/user-coupons/')
    coupons.value = data
  } catch (e) {
    coupons.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) {
    try { await authStore.fetchMe() } catch (_e) { return }
  }
  await loadCoupons()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :span="18">
          <h2 class="section-title">我的优惠券</h2>
          <p style="margin: 0; color: var(--text-sub)">查看和管理我的优惠券</p>
        </el-col>
        <el-col :span="6" style="text-align: right">
          <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回控制台</el-button>
          <el-button type="primary" plain @click="loadCoupons">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-skeleton :loading="loading" animated :rows="4">
      <template #default>
        <el-card class="section-card" shadow="never">
          <el-tabs v-model="activeStatus">
            <el-tab-pane v-for="t in tabs" :key="t.key" :label="`${t.label} (${coupons.filter(c => c.status === t.key).length})`" :name="t.key" />
          </el-tabs>

          <div v-if="filteredCoupons.length === 0" style="padding: 40px 0; text-align: center">
            <el-empty description="暂无优惠券" />
          </div>

          <div v-else class="coupon-grid">
            <div
              v-for="c in filteredCoupons"
              :key="c.id"
              class="coupon-card"
              :class="`coupon-${c.status}`"
            >
              <div class="coupon-left">
                <div class="coupon-value">{{ couponValueText(c) }}</div>
                <div class="coupon-condition">{{ couponConditionText(c) }}</div>
              </div>
              <div class="coupon-divider" />
              <div class="coupon-right">
                <div class="coupon-name">{{ c.coupon_detail?.name || '优惠券' }}</div>
                <div v-if="c.coupon_detail?.description" class="coupon-desc">{{ c.coupon_detail.description }}</div>
                <div class="coupon-time">
                  <span v-if="c.status === 'used'">已使用：{{ formatDateTime(c.used_at) }}</span>
                  <span v-else-if="c.status === 'revoked'">{{ c.revoked_reason || '已回收' }}</span>
                  <span v-else>有效期至：{{ formatDateTime(c.expired_at) }}</span>
                </div>
                <div v-if="c.status === 'used' && c.used_order_no" class="coupon-order">
                  关联订单：{{ c.used_order_no }}
                  <span v-if="c.discount_amount > 0" class="coupon-discount">（优惠 ¥{{ formatMoney(c.discount_amount) }}）</span>
                </div>
                <el-tag size="small" :type="statusMap[c.status]?.type || 'info'" effect="plain" style="margin-top: 6px">
                  {{ statusMap[c.status]?.label || c.status }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </template>
    </el-skeleton>
  </main>
</template>

<style scoped>
.coupon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
}

.coupon-card {
  display: flex;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  min-height: 120px;
}

.coupon-left {
  width: 130px;
  background: linear-gradient(135deg, #f56c6c, #e6a23c);
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 12px;
}

.coupon-card.coupon-used .coupon-left,
.coupon-card.coupon-expired .coupon-left,
.coupon-card.coupon-revoked .coupon-left {
  background: linear-gradient(135deg, #909399, #c0c4cc);
}

.coupon-value {
  font-size: 26px;
  font-weight: 700;
}

.coupon-condition {
  font-size: 12px;
  margin-top: 4px;
  opacity: 0.9;
}

.coupon-divider {
  width: 1px;
  background: repeating-linear-gradient(
    to bottom,
    #ebeef5 0,
    #ebeef5 4px,
    transparent 4px,
    transparent 10px
  );
}

.coupon-right {
  flex: 1;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.coupon-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.coupon-desc {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.coupon-time {
  font-size: 12px;
  color: #606266;
}

.coupon-order {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.coupon-discount {
  color: #f56c6c;
}
</style>
