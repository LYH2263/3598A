<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessageBox, ElNotification } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import http from '../utils/http'

const authStore = useAuthStore()

const loading = ref(true)
const activeTab = ref('promotions')

const promotionTypeMap = {
  bonus: { label: '满赠（充X送Y）', type: 'success' },
  discount: { label: '满减（满A减B）', type: 'warning' },
  tiered_cashback: { label: '阶梯返现', type: 'primary' },
}

const audienceTypeMap = {
  all: '全部用户',
  role: '指定角色',
  tag: '指定标签',
}

const limitTypeMap = {
  none: '不限次',
  per_day: '每人每日限享',
  total: '每人累计限享',
}

const stackingPolicyMap = {
  allow: '活动+优惠券可叠加',
  exclusive: '互斥（择优）',
  coupon_only: '仅允许用券',
  promo_only: '仅允许活动',
}

const couponTypeMap = {
  fixed: '固定面额',
  percent: '折扣券',
}

const couponScopeMap = {
  public: '公开领取',
  directed: '定向发放',
}

const userCouponStatusMap = {
  available: { label: '可用', type: 'success' },
  used: { label: '已用', type: 'info' },
  expired: { label: '已过期', type: 'warning' },
  revoked: { label: '已回收', type: 'danger' },
}

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

// ============== 营销活动 ==============
const promotions = ref([])
const promotionFormVisible = ref(false)
const promotionForm = reactive({
  id: null,
  name: '',
  description: '',
  promotion_type: 'bonus',
  is_active: true,
  start_time: '',
  end_time: '',
  audience_type: 'all',
  audience_roles: [],
  audience_tag_ids: [],
  limit_type: 'none',
  limit_count: 0,
  stacking_policy: 'allow',
  rule_config: {},
})

const bonusForm = reactive({ threshold: null, bonus: null })
const discountForm = reactive({ threshold: null, discount: null })
const tieredForm = reactive({ tiers: [{ threshold: null, rate: null }] })

function openPromotionForm(promo = null) {
  if (promo) {
    Object.assign(promotionForm, {
      id: promo.id,
      name: promo.name,
      description: promo.description || '',
      promotion_type: promo.promotion_type,
      is_active: promo.is_active,
      start_time: promo.start_time ? promo.start_time.slice(0, 16) : '',
      end_time: promo.end_time ? promo.end_time.slice(0, 16) : '',
      audience_type: promo.audience_type,
      audience_roles: promo.audience_roles || [],
      audience_tag_ids: promo.audience_tag_ids || [],
      limit_type: promo.limit_type,
      limit_count: promo.limit_count || 0,
      stacking_policy: promo.stacking_policy,
      rule_config: promo.rule_config || {},
    })
    if (promo.promotion_type === 'bonus') {
      bonusForm.threshold = promo.rule_config.threshold
      bonusForm.bonus = promo.rule_config.bonus
    } else if (promo.promotion_type === 'discount') {
      discountForm.threshold = promo.rule_config.threshold
      discountForm.discount = promo.rule_config.discount
    } else if (promo.promotion_type === 'tiered_cashback') {
      tieredForm.tiers = (promo.rule_config.tiers || []).map(t => ({ ...t }))
      if (tieredForm.tiers.length === 0) tieredForm.tiers = [{ threshold: null, rate: null }]
    }
  } else {
    Object.assign(promotionForm, {
      id: null, name: '', description: '', promotion_type: 'bonus',
      is_active: true, start_time: '', end_time: '',
      audience_type: 'all', audience_roles: [], audience_tag_ids: [],
      limit_type: 'none', limit_count: 0, stacking_policy: 'allow', rule_config: {},
    })
    bonusForm.threshold = null; bonusForm.bonus = null
    discountForm.threshold = null; discountForm.discount = null
    tieredForm.tiers = [{ threshold: null, rate: null }]
  }
  promotionFormVisible.value = true
}

function addTier() { tieredForm.tiers.push({ threshold: null, rate: null }) }
function removeTier(idx) { if (tieredForm.tiers.length > 1) tieredForm.tiers.splice(idx, 1) }

function buildRuleConfig() {
  if (promotionForm.promotion_type === 'bonus') {
    return { threshold: Number(bonusForm.threshold || 0), bonus: Number(bonusForm.bonus || 0) }
  }
  if (promotionForm.promotion_type === 'discount') {
    return { threshold: Number(discountForm.threshold || 0), discount: Number(discountForm.discount || 0) }
  }
  if (promotionForm.promotion_type === 'tiered_cashback') {
    return {
      tiers: tieredForm.tiers
        .filter(t => t.threshold != null && t.rate != null)
        .map(t => ({ threshold: Number(t.threshold), rate: Number(t.rate) })),
    }
  }
  return {}
}

async function savePromotion() {
  if (!promotionForm.name.trim()) {
    ElNotification({ title: '请填写活动名称', type: 'warning' })
    return
  }
  if (!promotionForm.start_time || !promotionForm.end_time) {
    ElNotification({ title: '请填写生效时间段', type: 'warning' })
    return
  }
  const payload = {
    ...promotionForm,
    start_time: new Date(promotionForm.start_time).toISOString(),
    end_time: new Date(promotionForm.end_time).toISOString(),
    rule_config: buildRuleConfig(),
  }
  delete payload.id
  try {
    if (promotionForm.id) {
      await http.put(`/marketing/promotions/${promotionForm.id}/`, payload)
      ElNotification({ title: '活动已更新', type: 'success' })
    } else {
      await http.post('/marketing/promotions/', payload)
      ElNotification({ title: '活动已创建', type: 'success' })
    }
    promotionFormVisible.value = false
    await loadPromotions()
  } catch (e) {
    ElNotification({ title: '保存失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function togglePromotion(promo) {
  try {
    await http.put(`/marketing/promotions/${promo.id}/`, { is_active: !promo.is_active })
    await loadPromotions()
  } catch (e) {
    ElNotification({ title: '操作失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

function describePromotion(promo) {
  const cfg = promo.rule_config || {}
  if (promo.promotion_type === 'bonus') return `充满${cfg.threshold}元送${cfg.bonus}元`
  if (promo.promotion_type === 'discount') return `满${cfg.threshold}元减${cfg.discount}元`
  if (promo.promotion_type === 'tiered_cashback') {
    return (cfg.tiers || []).map(t => `达${t.threshold}返${(Number(t.rate) * 100).toFixed(0)}%`).join('、') || '未配置阶梯'
  }
  return '--'
}

async function loadPromotions() {
  const { data } = await http.get('/marketing/promotions/')
  promotions.value = data
}

// ============== 优惠券模板 ==============
const coupons = ref([])
const couponFormVisible = ref(false)
const couponForm = reactive({
  id: null,
  name: '',
  description: '',
  coupon_type: 'fixed',
  is_active: true,
  face_value: null,
  discount_rate: 1,
  min_amount: 0,
  max_discount: null,
  scope: 'directed',
  total_quantity: 0,
  per_user_limit: 1,
  valid_from: '',
  valid_until: '',
  audience_tag_ids: [],
})

function openCouponForm(coupon = null) {
  if (coupon) {
    Object.assign(couponForm, {
      id: coupon.id,
      name: coupon.name,
      description: coupon.description || '',
      coupon_type: coupon.coupon_type,
      is_active: coupon.is_active,
      face_value: coupon.face_value,
      discount_rate: Number(coupon.discount_rate || 1),
      min_amount: coupon.min_amount,
      max_discount: coupon.max_discount,
      scope: coupon.scope,
      total_quantity: coupon.total_quantity,
      per_user_limit: coupon.per_user_limit,
      valid_from: coupon.valid_from ? coupon.valid_from.slice(0, 16) : '',
      valid_until: coupon.valid_until ? coupon.valid_until.slice(0, 16) : '',
      audience_tag_ids: coupon.audience_tag_ids || [],
    })
  } else {
    Object.assign(couponForm, {
      id: null, name: '', description: '', coupon_type: 'fixed',
      is_active: true, face_value: 10, discount_rate: 1, min_amount: 0,
      max_discount: null, scope: 'directed', total_quantity: 0, per_user_limit: 1,
      valid_from: '', valid_until: '', audience_tag_ids: [],
    })
  }
  couponFormVisible.value = true
}

async function saveCoupon() {
  if (!couponForm.name.trim()) { ElNotification({ title: '请填写优惠券名称', type: 'warning' }); return }
  if (!couponForm.valid_from || !couponForm.valid_until) { ElNotification({ title: '请填写有效期', type: 'warning' }); return }
  const payload = {
    ...couponForm,
    valid_from: new Date(couponForm.valid_from).toISOString(),
    valid_until: new Date(couponForm.valid_until).toISOString(),
  }
  delete payload.id
  try {
    if (couponForm.id) {
      await http.put(`/marketing/coupons/${couponForm.id}/`, payload)
      ElNotification({ title: '优惠券已更新', type: 'success' })
    } else {
      await http.post('/marketing/coupons/', payload)
      ElNotification({ title: '优惠券已创建', type: 'success' })
    }
    couponFormVisible.value = false
    await loadCoupons()
  } catch (e) {
    ElNotification({ title: '保存失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function toggleCoupon(coupon) {
  try {
    await http.put(`/marketing/coupons/${coupon.id}/`, { is_active: !coupon.is_active })
    await loadCoupons()
  } catch (e) {
    ElNotification({ title: '操作失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

const grantVisible = ref(false)
const grantTarget = reactive({ coupon_id: null, usernames: '', user_ids: [] })

function openGrantDialog(coupon) {
  grantTarget.coupon_id = coupon.id
  grantTarget.usernames = ''
  grantTarget.user_ids = []
  grantVisible.value = true
}

async function confirmGrant() {
  if (!grantTarget.usernames.trim()) {
    ElNotification({ title: '请填写用户名', type: 'warning' })
    return
  }
  const usernames = grantTarget.usernames.split(/[,，\s]+/).filter(Boolean)
  try {
    const { data } = await http.post('/marketing/coupons/grant/', {
      coupon_id: grantTarget.coupon_id,
      usernames,
    })
    ElNotification({
      title: '发放完成',
      message: `共 ${data.total} 个，成功 ${data.success_count}，失败 ${data.failure_count}`,
      type: data.failure_count === 0 ? 'success' : 'warning',
    })
    grantVisible.value = false
    await loadCoupons()
  } catch (e) {
    ElNotification({ title: '发放失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

// 用户优惠券列表
const userCoupons = ref([])
const userCouponFilters = reactive({ status: '', user_id: '' })

async function loadUserCoupons() {
  const params = {}
  if (userCouponFilters.status) params.status = userCouponFilters.status
  if (userCouponFilters.user_id) params.user_id = userCouponFilters.user_id
  const { data } = await http.get('/marketing/user-coupons/', { params })
  userCoupons.value = data
}

async function revokeUserCoupon(uc) {
  const result = await ElMessageBox.prompt(
    '请输入回收原因（可选）', '回收用户优惠券',
    { confirmButtonText: '回收', cancelButtonText: '取消', inputPlaceholder: '请输入原因' },
  ).catch(() => null)
  if (!result) return
  try {
    await http.post(`/marketing/user-coupons/${uc.id}/revoke/`, { reason: result.value || '' })
    ElNotification({ title: '已回收', type: 'success' })
    await loadUserCoupons()
  } catch (e) {
    ElNotification({ title: '回收失败', message: e?.response?.data?.detail || String(e), type: 'error' })
  }
}

async function loadCoupons() {
  const { data } = await http.get('/marketing/coupons/')
  coupons.value = data
}

// ============== 用户标签 ==============
const tags = ref([])
async function loadTags() {
  try {
    const { data } = await http.get('/marketing/tags/')
    tags.value = data
  } catch (_e) { tags.value = [] }
}

// ============== 营销报表 ==============
const reportOverview = reactive({})
const reportPromotions = ref([])
const reportCoupons = ref([])

async function loadReportOverview() {
  const { data } = await http.get('/marketing/reports/overview/')
  Object.assign(reportOverview, data)
}
async function loadReportPromotions() {
  const { data } = await http.get('/marketing/reports/promotions/')
  reportPromotions.value = data
}
async function loadReportCoupons() {
  const { data } = await http.get('/marketing/reports/coupons/')
  reportCoupons.value = data
}

// ============== 刷新所有 ==============
async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([
      loadPromotions(), loadCoupons(), loadUserCoupons(), loadTags(),
      loadReportOverview(), loadReportPromotions(), loadReportCoupons(),
    ])
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) {
    try { await authStore.fetchMe() } catch (_e) { return }
  }
  await refreshAll()
})
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle" :gutter="12">
        <el-col :span="18">
          <h2 class="section-title">营销中心</h2>
          <p style="margin: 0; color: var(--text-sub)">活动配置、优惠券管理、营销报表一站式运营</p>
        </el-col>
        <el-col :span="6" style="text-align: right">
          <el-button style="margin-right: 8px" @click="$router.push('/dashboard')">返回控制台</el-button>
          <el-button type="primary" @click="refreshAll">刷新数据</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-skeleton :loading="loading" animated :rows="6">
      <template #default>
        <el-card class="section-card" shadow="never">
          <el-tabs v-model="activeTab">
            <!-- 活动配置 -->
            <el-tab-pane label="营销活动" name="promotions">
              <el-row justify="space-between" align="middle" :gutter="12" style="margin-bottom: 12px">
                <el-col :span="18">
                  <h3 class="section-title" style="margin: 0">营销活动列表</h3>
                  <div style="color: var(--text-sub); font-size: 13px">
                    支持满赠、满减、阶梯返现三类活动，可配置时间段、限次、人群与叠加策略
                  </div>
                </el-col>
                <el-col :span="6" style="text-align: right">
                  <el-button type="primary" @click="openPromotionForm()">新建活动</el-button>
                </el-col>
              </el-row>
              <el-table :data="promotions" stripe border empty-text="暂无活动">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="name" label="活动名称" min-width="160" />
                <el-table-column label="类型" min-width="150">
                  <template #default="{ row }">
                    <el-tag :type="promotionTypeMap[row.promotion_type]?.type || 'info'" effect="plain">
                      {{ promotionTypeMap[row.promotion_type]?.label || row.promotion_type }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="规则" min-width="220">
                  <template #default="{ row }">{{ describePromotion(row) }}</template>
                </el-table-column>
                <el-table-column label="生效时间" min-width="330">
                  <template #default="{ row }">
                    {{ formatDateTime(row.start_time) }} ~ {{ formatDateTime(row.end_time) }}
                  </template>
                </el-table-column>
                <el-table-column label="人群" min-width="120">
                  <template #default="{ row }">{{ audienceTypeMap[row.audience_type] }}</template>
                </el-table-column>
                <el-table-column label="限次" min-width="120">
                  <template #default="{ row }">
                    {{ limitTypeMap[row.limit_type] }}{{ row.limit_count > 0 ? ` ×${row.limit_count}` : '' }}
                  </template>
                </el-table-column>
                <el-table-column label="叠加策略" min-width="160">
                  <template #default="{ row }">{{ stackingPolicyMap[row.stacking_policy] }}</template>
                </el-table-column>
                <el-table-column label="状态" width="100">
                  <template #default="{ row }">
                    <el-switch :model-value="row.is_active" @change="() => togglePromotion(row)" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="160" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" plain @click="openPromotionForm(row)">编辑</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- 优惠券管理 -->
            <el-tab-pane label="优惠券管理" name="coupons">
              <h3 class="section-title" style="margin: 0 0 12px">优惠券模板</h3>
              <el-row :gutter="12" style="margin-bottom: 12px">
                <el-col :span="18">
                  <div style="color: var(--text-sub); font-size: 13px">
                    支持固定面额与折扣券，可定向发放或公开领取
                  </div>
                </el-col>
                <el-col :span="6" style="text-align: right">
                  <el-button type="primary" @click="openCouponForm()">新建优惠券</el-button>
                </el-col>
              </el-row>
              <el-table :data="coupons" stripe border empty-text="暂无优惠券" style="margin-bottom: 24px">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="name" label="名称" min-width="160" />
                <el-table-column label="类型" min-width="120">
                  <template #default="{ row }">{{ couponTypeMap[row.coupon_type] }}</template>
                </el-table-column>
                <el-table-column label="面额/折扣" min-width="130">
                  <template #default="{ row }">
                    <span v-if="row.coupon_type === 'fixed'">¥{{ formatMoney(row.face_value) }}</span>
                    <span v-else>{{ (Number(row.discount_rate) * 10).toFixed(1) }}折</span>
                  </template>
                </el-table-column>
                <el-table-column label="门槛" min-width="110">
                  <template #default="{ row }">满 ¥{{ formatMoney(row.min_amount) }}</template>
                </el-table-column>
                <el-table-column label="发放范围" min-width="110">
                  <template #default="{ row }">{{ couponScopeMap[row.scope] }}</template>
                </el-table-column>
                <el-table-column label="总量/已发" min-width="120">
                  <template #default="{ row }">{{ row.total_quantity > 0 ? `${row.total_quantity}/${row.issued_count}` : `不限/${row.issued_count}` }}</template>
                </el-table-column>
                <el-table-column label="已用" width="80">
                  <template #default="{ row }">{{ row.used_count }}</template>
                </el-table-column>
                <el-table-column label="有效期" min-width="330">
                  <template #default="{ row }">
                    {{ formatDateTime(row.valid_from) }} ~ {{ formatDateTime(row.valid_until) }}
                  </template>
                </el-table-column>
                <el-table-column label="启用" width="80">
                  <template #default="{ row }">
                    <el-switch :model-value="row.is_active" @change="() => toggleCoupon(row)" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="220" fixed="right">
                  <template #default="{ row }">
                    <el-space>
                      <el-button size="small" type="primary" plain @click="openCouponForm(row)">编辑</el-button>
                      <el-button size="small" type="success" @click="openGrantDialog(row)">发放</el-button>
                    </el-space>
                  </template>
                </el-table-column>
              </el-table>

              <h3 class="section-title" style="margin: 0 0 12px">用户券实例</h3>
              <el-row :gutter="12" style="margin-bottom: 12px">
                <el-col :span="6">
                  <el-select v-model="userCouponFilters.status" placeholder="按状态" clearable style="width: 100%">
                    <el-option label="全部状态" value="" />
                    <el-option label="可用" value="available" />
                    <el-option label="已用" value="used" />
                    <el-option label="已过期" value="expired" />
                    <el-option label="已回收" value="revoked" />
                  </el-select>
                </el-col>
                <el-col :span="6">
                  <el-input v-model="userCouponFilters.user_id" placeholder="按用户ID" clearable />
                </el-col>
                <el-col :span="6">
                  <el-button @click="loadUserCoupons">查询</el-button>
                </el-col>
              </el-row>
              <el-table :data="userCoupons.slice(0, 300)" stripe border empty-text="暂无用户券">
                <el-table-column prop="id" label="ID" width="70" />
                <el-table-column prop="code" label="券码" min-width="180" />
                <el-table-column label="券名" min-width="160">
                  <template #default="{ row }">{{ row.coupon_detail?.name }}</template>
                </el-table-column>
                <el-table-column prop="used_order_no" label="关联订单号" min-width="180" />
                <el-table-column label="状态" min-width="100">
                  <template #default="{ row }">
                    <el-tag :type="userCouponStatusMap[row.status]?.type || 'info'" effect="plain">
                      {{ userCouponStatusMap[row.status]?.label || row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="实际优惠" min-width="110">
                  <template #default="{ row }">¥{{ formatMoney(row.discount_amount) }}</template>
                </el-table-column>
                <el-table-column label="有效期至" min-width="170">
                  <template #default="{ row }">{{ formatDateTime(row.expired_at) }}</template>
                </el-table-column>
                <el-table-column label="领取时间" min-width="170">
                  <template #default="{ row }">{{ formatDateTime(row.granted_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="110" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      size="small"
                      type="danger"
                      plain
                      :disabled="row.status !== 'available'"
                      @click="revokeUserCoupon(row)"
                    >回收</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <!-- 营销报表 -->
            <el-tab-pane label="营销报表" name="reports">
              <section class="summary-grid" style="margin-bottom: 16px">
                <article class="summary-card">
                  <div class="label">营销活动数</div>
                  <div class="value">{{ reportOverview.promotion_count || 0 }}</div>
                  <div class="summary-note">当前启用 {{ reportOverview.active_promotion_count || 0 }} 个</div>
                </article>
                <article class="summary-card">
                  <div class="label">优惠券模板</div>
                  <div class="value">{{ reportOverview.coupon_template_count || 0 }}</div>
                  <div class="summary-note">启用 {{ reportOverview.active_coupon_template_count || 0 }} 个</div>
                </article>
                <article class="summary-card">
                  <div class="label">活动参与次数</div>
                  <div class="value">{{ reportOverview.total_promotion_redemption_count || 0 }}</div>
                  <div class="summary-note">活动赠送合计 ¥{{ formatMoney(reportOverview.total_promotion_benefit_amount) }}</div>
                </article>
                <article class="summary-card">
                  <div class="label">优惠券核销</div>
                  <div class="value">{{ reportOverview.total_coupon_used_count || 0 }}</div>
                  <div class="summary-note">优惠减免合计 ¥{{ formatMoney(reportOverview.total_coupon_discount_amount) }}</div>
                </article>
              </section>

              <h3 class="section-title" style="margin: 0 0 12px">活动维度报表</h3>
              <el-table :data="reportPromotions" stripe border empty-text="暂无活动数据" style="margin-bottom: 24px">
                <el-table-column prop="promotion_id" label="活动ID" width="90" />
                <el-table-column prop="name" label="活动名称" min-width="180" />
                <el-table-column label="类型" min-width="150">
                  <template #default="{ row }">{{ row.type_display }}</template>
                </el-table-column>
                <el-table-column label="生效时间" min-width="330">
                  <template #default="{ row }">
                    {{ formatDateTime(row.start_time) }} ~ {{ formatDateTime(row.end_time) }}
                  </template>
                </el-table-column>
                <el-table-column prop="redemption_count" label="参与次数" min-width="110" />
                <el-table-column prop="unique_user_count" label="参与用户数" min-width="120" />
                <el-table-column label="赠送/优惠合计" min-width="140">
                  <template #default="{ row }">¥{{ formatMoney(row.total_benefit_amount) }}</template>
                </el-table-column>
                <el-table-column label="带动充值额" min-width="140">
                  <template #default="{ row }">¥{{ formatMoney(row.total_recharge_amount) }}</template>
                </el-table-column>
                <el-table-column label="状态" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
                      {{ row.is_active ? '启用' : '停用' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>

              <h3 class="section-title" style="margin: 0 0 12px">优惠券维度报表</h3>
              <el-table :data="reportCoupons" stripe border empty-text="暂无优惠券数据">
                <el-table-column prop="coupon_id" label="券模板ID" width="110" />
                <el-table-column prop="name" label="优惠券名称" min-width="180" />
                <el-table-column label="类型" min-width="120">
                  <template #default="{ row }">{{ row.type_display }}</template>
                </el-table-column>
                <el-table-column label="范围" min-width="110">
                  <template #default="{ row }">{{ row.scope_display }}</template>
                </el-table-column>
                <el-table-column label="有效期" min-width="330">
                  <template #default="{ row }">
                    {{ formatDateTime(row.valid_from) }} ~ {{ formatDateTime(row.valid_until) }}
                  </template>
                </el-table-column>
                <el-table-column prop="claimed_count" label="已领取" width="90" />
                <el-table-column prop="used_count" label="已核销" width="90" />
                <el-table-column prop="expired_count" label="已过期" width="90" />
                <el-table-column prop="revoked_count" label="已回收" width="90" />
                <el-table-column label="优惠减免合计" min-width="140">
                  <template #default="{ row }">¥{{ formatMoney(row.total_discount_amount) }}</template>
                </el-table-column>
                <el-table-column label="带动充值额" min-width="140">
                  <template #default="{ row }">¥{{ formatMoney(row.driven_recharge_amount) }}</template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </template>
    </el-skeleton>

    <!-- 活动新建/编辑对话框 -->
    <el-dialog v-model="promotionFormVisible" :title="promotionForm.id ? '编辑营销活动' : '新建营销活动'" width="680px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="活动名称" required>
          <el-input v-model="promotionForm.name" placeholder="如：开学季充值满赠" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="活动说明">
          <el-input v-model="promotionForm.description" type="textarea" :rows="2" maxlength="500" show-word-limit />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="活动类型">
              <el-select v-model="promotionForm.promotion_type" style="width: 100%">
                <el-option label="满赠（充X送Y）" value="bonus" />
                <el-option label="满减（满A减B）" value="discount" />
                <el-option label="阶梯返现" value="tiered_cashback" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="叠加策略">
              <el-select v-model="promotionForm.stacking_policy" style="width: 100%">
                <el-option label="活动+优惠券可叠加" value="allow" />
                <el-option label="互斥（择优）" value="exclusive" />
                <el-option label="仅允许用券" value="coupon_only" />
                <el-option label="仅允许活动" value="promo_only" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="生效开始时间" required>
              <el-date-picker v-model="promotionForm.start_time" type="datetime" value-format="YYYY-MM-DDTHH:mm" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生效结束时间" required>
              <el-date-picker v-model="promotionForm.end_time" type="datetime" value-format="YYYY-MM-DDTHH:mm" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="用户人群">
              <el-select v-model="promotionForm.audience_type" style="width: 100%">
                <el-option label="全部用户" value="all" />
                <el-option label="指定角色" value="role" />
                <el-option label="指定标签" value="tag" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="限次类型">
              <el-select v-model="promotionForm.limit_type" style="width: 100%">
                <el-option label="不限次" value="none" />
                <el-option label="每人每日限享" value="per_day" />
                <el-option label="每人累计限享" value="total" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="限次数量">
              <el-input-number v-model="promotionForm.limit_count" :min="0" :precision="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12" v-if="promotionForm.audience_type === 'role'">
          <el-col :span="24">
            <el-form-item label="指定角色">
              <el-select v-model="promotionForm.audience_roles" multiple style="width: 100%">
                <el-option label="学生" value="student" />
                <el-option label="管理员" value="admin" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12" v-if="promotionForm.audience_type === 'tag'">
          <el-col :span="24">
            <el-form-item label="指定标签">
              <el-select v-model="promotionForm.audience_tag_ids" multiple style="width: 100%">
                <el-option v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>活动规则</el-divider>

        <template v-if="promotionForm.promotion_type === 'bonus'">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="充值满 X（元）">
                <el-input-number v-model="bonusForm.threshold" :min="0" :precision="2" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="送 Y（元）">
                <el-input-number v-model="bonusForm.bonus" :min="0" :precision="2" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <template v-else-if="promotionForm.promotion_type === 'discount'">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="充值满 A（元）">
                <el-input-number v-model="discountForm.threshold" :min="0" :precision="2" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="减 B（元）">
                <el-input-number v-model="discountForm.discount" :min="0" :precision="2" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <template v-else-if="promotionForm.promotion_type === 'tiered_cashback'">
          <div v-for="(t, idx) in tieredForm.tiers" :key="idx" style="margin-bottom: 10px">
            <el-row :gutter="12" align="middle">
              <el-col :span="10">
                <el-form-item :label="idx === 0 ? '达到金额（元）' : ''">
                  <el-input-number v-model="t.threshold" :min="0" :precision="2" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="10">
                <el-form-item :label="idx === 0 ? '返现比例（如 0.05 表示 5%）' : ''">
                  <el-input-number v-model="t.rate" :min="0" :max="1" :step="0.01" :precision="3" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="4">
                <el-button v-if="tieredForm.tiers.length > 1" type="danger" plain size="small" @click="removeTier(idx)">删除</el-button>
              </el-col>
            </el-row>
          </div>
          <el-button type="primary" plain size="small" @click="addTier">新增阶梯</el-button>
        </template>

        <el-form-item>
          <el-switch v-model="promotionForm.is_active" active-text="立即启用" inactive-text="保存为停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="promotionFormVisible = false">取消</el-button>
        <el-button type="primary" @click="savePromotion">保存</el-button>
      </template>
    </el-dialog>

    <!-- 优惠券新建/编辑对话框 -->
    <el-dialog v-model="couponFormVisible" :title="couponForm.id ? '编辑优惠券' : '新建优惠券'" width="640px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="优惠券名称" required>
          <el-input v-model="couponForm.name" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="couponForm.description" type="textarea" :rows="2" maxlength="500" show-word-limit />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="券类型">
              <el-select v-model="couponForm.coupon_type" style="width: 100%">
                <el-option label="固定面额" value="fixed" />
                <el-option label="折扣券" value="percent" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发放范围">
              <el-select v-model="couponForm.scope" style="width: 100%">
                <el-option label="定向发放" value="directed" />
                <el-option label="公开领取" value="public" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12" v-if="couponForm.coupon_type === 'fixed'">
            <el-form-item label="面额（元）">
              <el-input-number v-model="couponForm.face_value" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="couponForm.coupon_type === 'percent'">
            <el-form-item label="折扣率（如 0.8 表示 8 折）">
              <el-input-number v-model="couponForm.discount_rate" :min="0" :max="1" :step="0.05" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最低使用门槛（元）">
              <el-input-number v-model="couponForm.min_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="couponForm.coupon_type === 'percent'">
            <el-form-item label="最大优惠金额（元，可空）">
              <el-input-number v-model="couponForm.max_discount" :min="0" :precision="2" :controls="false" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="发放总量（0 不限）">
              <el-input-number v-model="couponForm.total_quantity" :min="0" :precision="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="每人限领张数">
              <el-input-number v-model="couponForm.per_user_limit" :min="1" :precision="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="生效开始时间" required>
              <el-date-picker v-model="couponForm.valid_from" type="datetime" value-format="YYYY-MM-DDTHH:mm" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="过期时间" required>
              <el-date-picker v-model="couponForm.valid_until" type="datetime" value-format="YYYY-MM-DDTHH:mm" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="领取门槛标签（空表示不限）">
          <el-select v-model="couponForm.audience_tag_ids" multiple style="width: 100%">
            <el-option v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-switch v-model="couponForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="couponFormVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCoupon">保存</el-button>
      </template>
    </el-dialog>

    <!-- 发放优惠券对话框 -->
    <el-dialog v-model="grantVisible" title="定向发放优惠券" width="520px">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="目标用户（多个用英文逗号、中文逗号或空格分隔）">
          <el-input v-model="grantTarget.usernames" type="textarea" :rows="4" placeholder="user1, user2, user3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="grantVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmGrant">确认发放</el-button>
      </template>
    </el-dialog>
  </main>
</template>
