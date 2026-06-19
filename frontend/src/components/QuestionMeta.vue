<template>
  <div class="flex items-center gap-2 mb-2">
    <span
      class="px-2 py-0.5 rounded text-xs font-medium"
      :class="typeClass(type)"
    >
      {{ typeLabel(type) }}
    </span>
    <span v-if="category" class="text-sm text-gray-500">{{ category }}</span>
    <span v-if="pageNumber" class="text-sm text-gray-500">| 第{{ pageNumber }}页</span>
    <span v-if="isNew" class="ml-2 text-success text-xs">🆕 新题</span>
    <span v-else-if="!isNew && showReviewBadge" class="ml-2 text-warning text-xs">🔄 复习</span>
  </div>
</template>

<script setup>
defineProps({
  type: { type: String, default: '' },
  category: { type: String, default: '' },
  pageNumber: { type: [Number, String], default: null },
  isNew: { type: Boolean, default: false },
  showReviewBadge: { type: Boolean, default: false }
})

const typeLabel = (type) => ({
  single: '单选',
  multiple: '多选',
  judge: '判断',
  fill: '填空'
}[type] || type)

const typeClass = (type) => ({
  single: 'bg-blue-100 text-blue-800',
  multiple: 'bg-purple-100 text-purple-800',
  judge: 'bg-orange-100 text-orange-800',
  fill: 'bg-gray-100 text-gray-800'
}[type] || 'bg-gray-100 text-gray-800')
</script>
