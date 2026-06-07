<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  cardId: { type: String, default: '' },
  collapsed: { type: Boolean, default: false },
  exportView: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  draggable: { type: Boolean, default: true },
})

const emit = defineEmits(['toggle-collapse', 'export', 'dragstart', 'dragover', 'drop'])

const isCollapsed = ref(props.collapsed)

function toggle() {
  isCollapsed.value = !isCollapsed.value
  emit('toggle-collapse', { cardId: props.cardId, collapsed: isCollapsed.value })
}

function handleExport() {
  emit('export', props.exportView)
}

function onDragStart(e) {
  if (!props.draggable) return
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', props.cardId)
}
</script>

<template>
  <el-card
    class="bi-card"
    shadow="never"
    :class="{ 'is-collapsed': isCollapsed, 'is-draggable': draggable }"
    :draggable="draggable"
    @dragstart="onDragStart"
    @dragover.prevent="$emit('dragover', $event)"
    @drop.prevent="$emit('drop', $event)"
  >
    <template #header>
      <div class="bi-card-header">
        <div class="bi-card-title" :class="{ 'cursor-move': draggable }">
          <span v-if="draggable" class="drag-handle" title="拖拽排序">⋮⋮</span>
          <el-icon class="collapse-icon" @click="toggle">
            <component :is="isCollapsed ? 'ArrowDown' : 'ArrowUp'" />
          </el-icon>
          <span class="title-text">{{ title }}</span>
        </div>
        <div class="bi-card-actions">
          <el-button
            v-if="exportView"
            link
            type="primary"
            size="small"
            :loading="loading"
            @click="handleExport"
          >
            导出 CSV
          </el-button>
        </div>
      </div>
    </template>

    <div v-show="!isCollapsed" class="bi-card-body">
      <el-skeleton v-if="loading" :rows="5" animated />
      <slot v-else />
    </div>
  </el-card>
</template>

<style scoped>
.bi-card {
  border: 1px solid rgba(90, 128, 201, 0.16);
  transition: box-shadow 0.2s;
}
.bi-card.is-draggable:hover {
  box-shadow: 0 2px 12px rgba(45, 115, 218, 0.12);
}
.bi-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  user-select: none;
}
.bi-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-main);
}
.bi-card-title.cursor-move {
  cursor: move;
}
.drag-handle {
  color: var(--text-sub);
  font-size: 12px;
  letter-spacing: 2px;
  opacity: 0.6;
}
.collapse-icon {
  cursor: pointer;
  color: var(--text-sub);
  transition: transform 0.2s;
}
.title-text {
  margin-left: 2px;
}
.bi-card-body {
  padding-top: 4px;
}
.bi-card.is-collapsed :deep(.el-card__body) {
  padding-top: 0;
  padding-bottom: 0;
}
</style>
