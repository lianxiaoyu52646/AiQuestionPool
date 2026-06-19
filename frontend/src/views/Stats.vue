<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold">📊 学习统计</h1>

    <!-- 总览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
      <div class="card text-center">
        <div class="text-3xl font-bold text-primary">{{ stats.total_questions }}</div>
        <div class="text-sm text-gray-500 mt-1">总题数</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-success">{{ stats.learned }}</div>
        <div class="text-sm text-gray-500 mt-1">已学习</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-blue-600">{{ stats.mastered }}</div>
        <div class="text-sm text-gray-500 mt-1">已掌握</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-warning">{{ stats.due_today }}</div>
        <div class="text-sm text-gray-500 mt-1">今日待复习</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-danger">{{ stats.new_questions }}</div>
        <div class="text-sm text-gray-500 mt-1">新题</div>
      </div>
    </div>

    <!-- 掌握率 -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold">🎯 整体掌握率</h2>
        <span class="text-2xl font-bold text-primary">{{ stats.master_rate }}%</span>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-4">
        <div
          class="bg-gradient-to-r from-primary to-success h-4 rounded-full transition-all duration-1000"
          :style="{ width: stats.master_rate + '%' }"
        ></div>
      </div>
    </div>

    <!-- 分类进度 -->
    <div class="card">
      <h2 class="text-lg font-bold mb-4">📚 分类学习进度</h2>
      <div class="space-y-4">
        <div
          v-for="cat in categoryStats"
          :key="cat.id"
          class="flex items-center space-x-4"
        >
          <div class="w-40 text-sm font-medium truncate">{{ cat.name }}</div>
          <div class="flex-1">
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div
                class="bg-primary h-2 rounded-full transition-all duration-500"
                :style="{ width: (cat.progress_rate || 0) + '%' }"
              ></div>
            </div>
          </div>
          <div class="w-24 text-sm text-gray-600 text-right">
            {{ cat.learned }}/{{ cat.total }}
          </div>
          <div class="w-16 text-sm font-medium text-right" :class="masteryColor(cat)">
            {{ cat.mastered }} 掌握
          </div>
        </div>
      </div>
    </div>

    <!-- 最近答题记录 -->
    <div class="card">
      <h2 class="text-lg font-bold mb-4">📝 最近答题记录</h2>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b">
              <th class="text-left py-2 px-4">时间</th>
              <th class="text-left py-2 px-4">题目</th>
              <th class="text-center py-2 px-4">评级</th>
              <th class="text-center py-2 px-4">用时</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="log in reviewHistory"
              :key="log.id"
              class="border-b hover:bg-gray-50"
            >
              <td class="py-2 px-4 text-gray-500">
                {{ formatTime(log.review_time) }}
              </td>
              <td class="py-2 px-4 max-w-xs truncate">
                {{ log.question_text }}
              </td>
              <td class="py-2 px-4 text-center">
                <span
                  class="px-2 py-0.5 rounded text-xs font-medium"
                  :class="ratingClass(log.rating)"
                >
                  {{ ratingLabel(log.rating) }}
                </span>
              </td>
              <td class="py-2 px-4 text-center text-gray-500">
                {{ log.used_time_sec }}s
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { studyApi } from '../api'

const stats = ref({
  total_questions: 0,
  learned: 0,
  mastered: 0,
  due_today: 0,
  new_questions: 0,
  master_rate: 0
})
const categoryStats = ref([])
const reviewHistory = ref([])

const ratingLabel = (r) => ['', '忘记', '困难', '良好', '简单'][r] || r

const ratingClass = (r) => ({
  1: 'bg-red-100 text-red-800',
  2: 'bg-orange-100 text-orange-800',
  3: 'bg-blue-100 text-blue-800',
  4: 'bg-green-100 text-green-800'
}[r] || 'bg-gray-100')

const masteryColor = (cat) => {
  const rate = cat.total > 0 ? (cat.mastered / cat.total) : 0
  if (rate >= 0.8) return 'text-success'
  if (rate >= 0.5) return 'text-warning'
  return 'text-danger'
}

const formatTime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(async () => {
  try {
    const [statsRes, catRes, historyRes] = await Promise.all([
      studyApi.stats(),
      studyApi.statsByCategory(),
      studyApi.history({ limit: 20 })
    ])
    stats.value = statsRes.data
    categoryStats.value = catRes.data
    reviewHistory.value = historyRes.data
  } catch (e) {
    console.error('加载统计失败:', e)
  }
})
</script>
