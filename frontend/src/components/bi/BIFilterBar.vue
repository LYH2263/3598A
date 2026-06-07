<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({}),
  },
  isAdmin: {
    type: Boolean,
    default: false,
  },
  dimensionOptions: {
    type: Object,
    default: () => ({
      categories: [],
      channels: [],
      buildings: [],
      rooms: [],
      date_range: { min: null, max: null },
    }),
  },
  showCompare: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['update:modelValue', 'search', 'reset'])

const localFilters = reactive({
  start_date: '',
  end_date: '',
  categories: [],
  channels: [],
  min_amount: null,
  max_amount: null,
  buildings: [],
  rooms: [],
  user_ids: [],
  trend_granularity: 'day',
  top_n: 10,
  compare_enabled: false,
  compare_start_date: '',
  compare_end_date: '',
})

watch(
  () => props.modelValue,
  (val) => {
    if (val) Object.assign(localFilters, val)
  },
  { deep: true, immediate: true }
)

function emitUpdate() {
  emit('update:modelValue', { ...localFilters })
}

function doSearch() {
  emitUpdate()
  emit('search', { ...localFilters })
}

function doReset() {
  Object.assign(localFilters, {
    start_date: '',
    end_date: '',
    categories: [],
    channels: [],
    min_amount: null,
    max_amount: null,
    buildings: [],
    rooms: [],
    user_ids: [],
    trend_granularity: 'day',
    top_n: 10,
    compare_enabled: false,
    compare_start_date: '',
    compare_end_date: '',
  })
  emitUpdate()
  emit('reset', { ...localFilters })
}

const quickRanges = [
  { label: '近7天', days: 7 },
  { label: '近30天', days: 30 },
  { label: '近90天', days: 90 },
]

function applyQuickRange(days) {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - days)
  localFilters.end_date = formatDate(end)
  localFilters.start_date = formatDate(start)
}

function formatDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
</script>

<template>
  <el-card class="bi-filter-bar" shadow="never">
    <el-form :inline="true" label-position="top" size="default" @submit.prevent>
      <el-row :gutter="12">
        <el-col :span="24" style="margin-bottom: 8px">
          <el-space wrap>
            <span class="filter-label">快捷范围：</span>
            <el-button
              v-for="r in quickRanges"
              :key="r.days"
              size="small"
              plain
              @click="applyQuickRange(r.days)"
            >{{ r.label }}</el-button>
            <el-divider direction="vertical" />
            <el-radio-group v-model="localFilters.trend_granularity" size="small" @change="emitUpdate">
              <el-radio-button value="day">按日</el-radio-button>
              <el-radio-button value="week">按周</el-radio-button>
              <el-radio-button value="month">按月</el-radio-button>
            </el-radio-group>
          </el-space>
        </el-col>

        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item label="开始日期">
            <el-date-picker
              v-model="localFilters.start_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择开始日期"
              style="width: 100%"
              :disabled-date="(d) => dimensionOptions.date_range.max && d > new Date(dimensionOptions.date_range.max)"
              @change="emitUpdate"
            />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item label="结束日期">
            <el-date-picker
              v-model="localFilters.end_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择结束日期"
              style="width: 100%"
              :disabled-date="(d) => dimensionOptions.date_range.min && d < new Date(dimensionOptions.date_range.min)"
              @change="emitUpdate"
            />
          </el-form-item>
        </el-col>

        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item label="消费类目">
            <el-select
              v-model="localFilters.categories"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部类目"
              clearable
              style="width: 100%"
              @change="emitUpdate"
            >
              <el-option
                v-for="opt in dimensionOptions.categories"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item label="消费渠道">
            <el-select
              v-model="localFilters.channels"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部渠道"
              clearable
              style="width: 100%"
              @change="emitUpdate"
            >
              <el-option
                v-for="opt in dimensionOptions.channels"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col v-if="isAdmin" :xs="24" :sm="12" :md="6">
          <el-form-item label="楼栋">
            <el-select
              v-model="localFilters.buildings"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部楼栋"
              clearable
              filterable
              style="width: 100%"
              @change="emitUpdate"
            >
              <el-option
                v-for="opt in dimensionOptions.buildings"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col v-if="isAdmin" :xs="24" :sm="12" :md="6">
          <el-form-item label="房间">
            <el-select
              v-model="localFilters.rooms"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部房间"
              clearable
              filterable
              style="width: 100%"
              @change="emitUpdate"
            >
              <el-option
                v-for="opt in dimensionOptions.rooms"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item label="最小金额(元)">
            <el-input-number
              v-model="localFilters.min_amount"
              :min="0"
              :precision="2"
              :step="10"
              controls-position="right"
              style="width: 100%"
              @change="emitUpdate"
            />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item label="最大金额(元)">
            <el-input-number
              v-model="localFilters.max_amount"
              :min="0"
              :precision="2"
              :step="10"
              controls-position="right"
              style="width: 100%"
              @change="emitUpdate"
            />
          </el-form-item>
        </el-col>

        <el-col v-if="isAdmin" :xs="24" :sm="12" :md="6">
          <el-form-item label="Top N 学生数">
            <el-input-number
              v-model="localFilters.top_n"
              :min="3"
              :max="50"
              :step="1"
              style="width: 100%"
              @change="emitUpdate"
            />
          </el-form-item>
        </el-col>

        <el-col :span="24">
          <el-space wrap>
            <el-button v-if="showCompare" type="primary" plain size="small" @click="localFilters.compare_enabled = !localFilters.compare_enabled">
              {{ localFilters.compare_enabled ? '关闭对比' : '启用时间段对比' }}
            </el-button>
            <template v-if="localFilters.compare_enabled && showCompare">
              <el-date-picker
                v-model="localFilters.compare_start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="对比开始"
                size="small"
                @change="emitUpdate"
              />
              <span>至</span>
              <el-date-picker
                v-model="localFilters.compare_end_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="对比结束"
                size="small"
                @change="emitUpdate"
              />
            </template>
            <el-button type="primary" @click="doSearch">查询</el-button>
            <el-button @click="doReset">重置</el-button>
          </el-space>
        </el-col>
      </el-row>
    </el-form>
  </el-card>
</template>

<style scoped>
.bi-filter-bar {
  margin-bottom: 14px;
  border: 1px solid rgba(90, 128, 201, 0.16);
}
.filter-label {
  font-size: 13px;
  color: var(--text-sub);
}
:deep(.el-form-item) {
  margin-bottom: 10px;
}
:deep(.el-form-item__label) {
  font-size: 12px;
  color: var(--text-sub);
  padding-bottom: 4px;
}
</style>
