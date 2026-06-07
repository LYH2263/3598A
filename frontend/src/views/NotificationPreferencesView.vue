<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElNotification } from 'element-plus'

import http from '../utils/http'

const loading = ref(true)
const saving = ref(false)

const preferences = ref([])

const channelOptions = [
  { value: 'in_site', label: '站内通知' },
  { value: 'email', label: '邮件' },
  { value: 'sms', label: '短信' },
]

const categoryMap = {
  announcement: { label: '系统公告', type: 'info' },
  order: { label: '订单通知', type: 'primary' },
  security: { label: '安全通知', type: 'warning' },
  system: { label: '系统消息', type: 'success' },
}

async function loadPreferences() {
  loading.value = true
  try {
    const { data } = await http.get('/notices/notification-preferences/')
    preferences.value = data.map((item) => ({
      message_type: item.message_type,
      enabled_channels: [...item.enabled_channels],
    }))
  } finally {
    loading.value = false
  }
}

async function savePreferences() {
  saving.value = true
  try {
    const items = preferences.value.map((p) => ({
      message_type_id: p.message_type.id,
      enabled_channels: p.enabled_channels,
    }))
    const { data } = await http.post('/notices/notification-preferences/batch/', { items })
    ElNotification({
      title: '保存成功',
      message: `成功保存 ${data.success_count} 项配置。${data.errors.length ? `失败 ${data.errors.length} 项。` : ''}`,
      type: data.errors.length === 0 ? 'success' : 'warning',
    })
    await loadPreferences()
  } finally {
    saving.value = false
  }
}

function toggleChannel(pref, channel) {
  const idx = pref.enabled_channels.indexOf(channel)
  if (idx >= 0) {
    pref.enabled_channels.splice(idx, 1)
  } else {
    pref.enabled_channels.push(channel)
  }
}

onMounted(loadPreferences)
</script>

<template>
  <main class="page-shell animated-in">
    <el-card class="section-card" shadow="never">
      <el-row justify="space-between" align="middle">
        <el-col>
          <h2 class="section-title">通知偏好设置</h2>
          <p style="margin: 4px 0 0; color: var(--text-sub)">按消息类型选择您希望接收通知的渠道，站内通知始终推荐开启。</p>
        </el-col>
        <el-col>
          <el-button type="primary" :loading="saving" @click="savePreferences">保存设置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="section-card" shadow="never" style="margin-top: 16px">
      <el-skeleton :loading="loading" animated :rows="6">
        <template #default>
          <el-table :data="preferences" stripe border empty-text="暂无可配置的消息类型">
            <el-table-column label="消息类型" min-width="200">
              <template #default="{ row }">
                <div style="font-weight: 600">{{ row.message_type.name_zh }}</div>
                <div style="color: var(--text-sub); font-size: 12px; margin-top: 2px">
                  {{ row.message_type.code }} · {{ row.message_type.name_en }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="分类" width="120">
              <template #default="{ row }">
                <el-tag :type="categoryMap[row.message_type.category]?.type || 'info'" effect="plain">
                  {{ categoryMap[row.message_type.category]?.label || row.message_type.category }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="描述" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">{{ row.message_type.description_zh || row.message_type.description_en || '--' }}</template>
            </el-table-column>
            <el-table-column label="接收渠道" min-width="360">
              <template #default="{ row }">
                <el-checkbox-group>
                  <el-checkbox
                    v-for="opt in channelOptions"
                    :key="opt.value"
                    :model-value="row.enabled_channels.includes(opt.value)"
                    @change="() => toggleChannel(row, opt.value)"
                  >
                    {{ opt.label }}
                  </el-checkbox>
                </el-checkbox-group>
                <div v-if="row.message_type.quiet_hours_start && row.message_type.quiet_hours_end" style="margin-top: 6px; color: var(--text-sub); font-size: 12px">
                  ℹ 静默时段：{{ row.message_type.quiet_hours_start?.slice(0, 5) }} - {{ row.message_type.quiet_hours_end?.slice(0, 5) }}（邮件/短信不推送）
                </div>
              </template>
            </el-table-column>
            <el-table-column label="默认渠道" min-width="220">
              <template #default="{ row }">
                <el-tag
                  v-for="c in row.message_type.default_channels"
                  :key="c"
                  type="info"
                  effect="plain"
                  size="small"
                  style="margin-right: 4px"
                >
                  {{ channelOptions.find((o) => o.value === c)?.label || c }}
                </el-tag>
                <span v-if="!row.message_type.default_channels.length" style="color: var(--text-sub)">未设置</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </el-skeleton>
    </el-card>
  </main>
</template>
