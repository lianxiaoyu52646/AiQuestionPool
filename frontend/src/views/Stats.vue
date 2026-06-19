<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">📊 学习统计</h1>
      <button
        @click="loadAll"
        :disabled="loading"
        class="btn-secondary text-sm flex items-center gap-1"
      >
        <span :class="{ 'animate-spin': loading }">🔄</span>
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>

    <!-- 总览卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
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
    </div>

    <!-- 今日学习概况 -->
    <div v-if="sessionSummary" class="grid grid-cols-2 gap-4">
      <div class="card text-center">
        <div class="text-2xl font-bold text-primary">{{ sessionSummary.total }}</div>
        <div class="text-sm text-gray-500 mt-1">今日答题数</div>
      </div>
      <div class="card text-center">
        <div class="text-2xl font-bold" :class="accuracyColor(sessionSummary.accuracy)">
          {{ sessionSummary.accuracy }}%
        </div>
        <div class="text-sm text-gray-500 mt-1">正确率</div>
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

  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { studyApi } from '../api'
import { useStudyStore } from '../stores/studyStore'

const studyStore = useStudyStore()

const loading = ref(false)
const stats = ref({
  total_questions: 0,
  learned: 0,
  mastered: 0,
  due_today: 0,
  new_questions: 0,
  master_rate: 0
})
const categoryStats = ref([])
const sessionSummary = ref(null)

const masteryColor = (cat) => {
  const rate = cat.total > 0 ? (cat.mastered / cat.total) : 0
  if (rate >= 0.8) return 'text-success'
  if (rate >= 0.5) return 'text-warning'
  return 'text-danger'
}

const accuracyColor = (acc) => {
  if (acc >= 80) return 'text-success'
  if (acc >= 50) return 'text-warning'
  return 'text-danger'
}

const loadAll = async () => {
  loading.value = true
  try {
    const [statsRes, catRes, sessionRes] = await Promise.all([
      studyApi.stats(),
      studyApi.statsByCategory(),
      studyApi.sessionSummary({ hours: 24 }).catch(() => ({ data: null }))
    ])
    stats.value = statsRes.data
    categoryStats.value = catRes.data
    sessionSummary.value = sessionRes.data
    // 同步缓存到store
    studyStore.cachedStats = statsRes.data
  } catch (e) {
    console.error('加载统计失败:', e)
  } finally {
    loading.value = false
  }
}

// 监听store版本变化（答题后触发刷新）
watch(() => studyStore.statsVersion, (newVal, oldVal) => {
  if (newVal > 0 && newVal !== oldVal) {
    loadAll()
  }
})

onMounted(() => {
  loadAll()
})
</script>
