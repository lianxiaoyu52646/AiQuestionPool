<template>
  <div class="max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">✍️ 智能刷题</h1>
      <div class="flex items-center space-x-4 text-sm">
        <!-- Mode toggle -->
        <div class="flex bg-gray-100 rounded-lg p-1">
          <button
            @click="switchMode('normal')"
            class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
            :class="mode === 'normal' ? 'bg-white text-primary shadow-sm' : 'text-gray-500'"
          >
            📖 正常刷题
          </button>
          <button
            @click="switchMode('wrong')"
            class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
            :class="mode === 'wrong' ? 'bg-white text-danger shadow-sm' : 'text-gray-500'"
          >
            ❌ 错题本
          </button>
        </div>
        <span class="text-gray-600">
          今日任务: <span class="font-bold text-primary">{{ completed }}/{{ queue.length + completed }}</span>
        </span>
        <span class="text-gray-600">
          耗时: <span class="font-bold text-warning">{{ formatTime(elapsedSec) }}</span>
        </span>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="card flex flex-wrap items-center gap-3 mb-6">
      <span class="text-sm text-gray-500 font-medium">筛选练习范围:</span>
      <select v-model="filterCategory" class="input w-40 text-sm" @change="loadQueue">
        <option value="">全部分类</option>
        <option v-for="cat in categories" :key="cat.id" :value="cat.id">
          {{ cat.name }}
        </option>
      </select>
      <select v-model="filterTag" class="input w-40 text-sm" @change="loadQueue">
        <option value="">全部标签</option>
        <option v-for="tag in tags" :key="tag.id" :value="tag.id">
          {{ tag.name }}
        </option>
      </select>
      <input
        v-model="filterSearch"
        placeholder="🔍 搜索题目..."
        class="input flex-1 min-w-[150px] text-sm"
        @keyup.enter="loadQueue"
      />
      <button @click="loadQueue" class="btn-primary text-sm">应用筛选</button>
      <button v-if="filterCategory || filterTag || filterSearch" @click="clearFilters" class="btn-secondary text-sm">
        清除
      </button>
    </div>

    <!-- 空状态 -->
    <div v-if="!currentQuestion && queue.length === 0" class="space-y-6">
      <!-- Session Summary -->
      <div v-if="sessionSummary && sessionSummary.total > 0" class="card">
        <h2 class="text-xl font-bold mb-4">📊 本次学习小结</h2>
        <div class="grid grid-cols-4 gap-4 mb-4">
          <div class="text-center">
            <div class="text-2xl font-bold text-primary">{{ sessionSummary.total }}</div>
            <div class="text-xs text-gray-500">总题数</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-success">{{ sessionSummary.correct }}</div>
            <div class="text-xs text-gray-500">答对</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-danger">{{ sessionSummary.wrong }}</div>
            <div class="text-xs text-gray-500">答错</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-warning">{{ sessionSummary.accuracy }}%</div>
            <div class="text-xs text-gray-500">正确率</div>
          </div>
        </div>
        <!-- Rating distribution -->
        <div v-if="sessionSummary.rating_distribution" class="flex gap-2 mb-4">
          <span
            v-for="(count, label) in sessionSummary.rating_distribution"
            :key="label"
            class="px-3 py-1 rounded-full text-xs font-medium"
            :class="ratingBadgeClass(label)"
          >
            {{ label }}: {{ count }}
          </span>
        </div>
        <!-- By category -->
        <div v-if="sessionSummary.by_category && sessionSummary.by_category.length > 0">
          <h3 class="text-sm font-bold text-gray-700 mb-2">分类表现</h3>
          <div v-for="cat in sessionSummary.by_category" :key="cat.name" class="flex items-center space-x-3 mb-1">
            <span class="text-sm w-32 truncate">{{ cat.name }}</span>
            <div class="flex-1 bg-gray-200 rounded-full h-2">
              <div
                class="h-2 rounded-full transition-all duration-500"
                :class="cat.accuracy >= 70 ? 'bg-success' : cat.accuracy >= 40 ? 'bg-warning' : 'bg-danger'"
                :style="{ width: cat.accuracy + '%' }"
              ></div>
            </div>
            <span class="text-xs text-gray-500 w-16 text-right">{{ cat.correct }}/{{ cat.total }}</span>
          </div>
        </div>
      </div>

      <!-- Complete message -->
      <div class="card text-center py-16">
        <div class="text-6xl mb-4">🎉</div>
        <h2 class="text-xl font-bold mb-2">
          {{ mode === 'wrong' ? '错题本已清空！' : '今日任务已完成！' }}
        </h2>
        <p class="text-gray-600 mb-6">
          {{ mode === 'wrong' ? '所有错题已复习完毕' : '明天再来复习吧，间隔重复是记忆的秘诀' }}
        </p>
        <div class="space-x-4">
          <button v-if="mode === 'wrong'" @click="switchMode('normal')" class="btn-secondary">
            ← 返回正常刷题
          </button>
          <router-link to="/stats" class="btn-primary">
            查看学习统计
          </router-link>
        </div>
      </div>
    </div>

    <!-- 题目卡片 -->
    <div v-else-if="currentQuestion" class="space-y-6">
      <!-- 题目信息 -->
      <div class="flex items-center justify-between text-sm text-gray-500">
        <span>{{ currentQuestion.category }}</span>
        <span>
          {{ currentIndex + 1 }} / {{ queue.length }}
          <span v-if="!currentQuestion.is_new" class="ml-2 text-warning">🔄 复习</span>
          <span v-else class="ml-2 text-success">🆕 新题</span>
        </span>
      </div>

      <!-- 题目内容 -->
      <div class="card">
        <div class="mb-6">
          <QuestionMeta
            :type="currentQuestion.question_type"
            :category="currentQuestion.category"
            :page-number="currentQuestion.page_number"
            :is-new="currentQuestion.is_new"
            show-review-badge
          />
          <h2 class="text-xl font-medium text-gray-900 leading-relaxed">
            {{ currentQuestion.question_text }}
          </h2>
        </div>

        <!-- 选项 -->
        <div v-if="currentQuestion.options && currentQuestion.options.length > 0" class="space-y-3">
          <button
            v-for="(opt, idx) in currentQuestion.options"
            :key="idx"
            @click="selectOption(opt)"
            class="w-full text-left p-4 rounded-lg border-2 transition-all duration-200"
            :class="optionClass(opt)"
            :disabled="answered"
          >
            <div class="flex items-center">
              <span
                class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold mr-3"
                :class="optionCircleClass(opt)"
              >
                {{ opt.charAt(0) }}
              </span>
              <span>{{ opt }}</span>
            </div>
          </button>
        </div>

        <!-- 简答/填空输入 -->
        <div v-else-if="currentQuestion.question_type === 'fill'" class="space-y-3">
          <input
            v-model="userAnswer"
            placeholder="请输入答案..."
            class="input"
            :disabled="answered"
            @keyup.enter="submitAnswer"
          />
          <button
            v-if="!answered"
            @click="submitAnswer"
            class="btn-primary w-full"
          >
            提交答案
          </button>
        </div>
      </div>

      <!-- 答案反馈 -->
      <div v-if="answered" class="card" :class="isCorrect ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'">
        <div class="flex items-center mb-3">
          <span v-if="isCorrect" class="text-2xl mr-2">✅</span>
          <span v-else class="text-2xl mr-2">❌</span>
          <span class="font-bold" :class="isCorrect ? 'text-green-800' : 'text-red-800'">
            {{ isCorrect ? '回答正确！' : '回答错误' }}
          </span>
          <span v-if="reviewResult" class="ml-auto text-sm text-gray-500">
            系统评级: <span class="font-bold">{{ reviewResult.auto_rating_label }}</span>
            <span v-if="reviewResult.next_interval_days > 0" class="ml-2">
              下次复习: {{ reviewResult.next_interval_days }}天后
            </span>
            <span v-else class="ml-2">下次复习: 今天</span>
          </span>
        </div>
        <p class="font-medium mb-2" :class="isCorrect ? 'text-green-800' : 'text-red-800'">
          正确答案：{{ currentQuestion.answer }}
        </p>
        <p v-if="currentQuestion.explanation" :class="isCorrect ? 'text-green-700' : 'text-red-700'">
          解析：{{ currentQuestion.explanation }}
        </p>
        <div v-if="currentQuestion.pdf_id && currentQuestion.page_number" class="mt-3">
          <router-link
            :to="`/pdf-view/${currentQuestion.pdf_id}?page=${currentQuestion.page_number}`"
            class="text-sm text-primary hover:underline"
          >
            📄 查看原文（第{{ currentQuestion.page_number }}页）
          </router-link>
        </div>
      </div>

      <!-- 导航 -->
      <div class="flex items-center justify-between">
        <button
          @click="prevQuestion"
          :disabled="currentIndex <= 0"
          class="btn-secondary"
          :class="{ 'opacity-50': currentIndex <= 0 }"
        >
          ← 上一题
        </button>
        <button
          v-if="!answered"
          @click="showAnswerDirectly"
          class="text-gray-500 hover:text-gray-700"
        >
          直接看答案
        </button>
        <button
          v-if="answered"
          @click="nextQuestion"
          class="btn-primary"
        >
          下一题 →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { studyApi, questionApi, tagApi } from '../api'
import QuestionMeta from '../components/QuestionMeta.vue'

const route = useRoute()

const queue = ref([])
const currentIndex = ref(0)
const answered = ref(false)
const selectedOption = ref(null)
const userAnswer = ref('')
const isCorrect = ref(false)
const completed = ref(0)
const reviewResult = ref(null)
const mode = ref('normal') // 'normal' or 'wrong'
const sessionSummary = ref(null)

// Filters
const filterCategory = ref('')
const filterTag = ref('')
const filterSearch = ref('')
const categories = ref([])
const tags = ref([])

// Timer
const startTime = ref(0)
const elapsedSec = ref(0)
let timerId = null

const currentQuestion = computed(() => queue.value[currentIndex.value] || null)

const formatTime = (sec) => {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

const startTimer = () => {
  startTime.value = Date.now()
  elapsedSec.value = 0
  timerId = setInterval(() => {
    elapsedSec.value = Math.floor((Date.now() - startTime.value) / 1000)
  }, 1000)
}

const stopTimer = () => {
  if (timerId) {
    clearInterval(timerId)
    timerId = null
  }
}

const isCorrectOption = (opt) => {
  if (!currentQuestion.value || !currentQuestion.value.answer) return false
  const answer = currentQuestion.value.answer.trim().toUpperCase()
  const optLetter = opt.charAt(0).toUpperCase()
  // For multiple choice (answer like "AB"), check if this option's letter is in the answer
  // For single choice (answer like "A"), check exact match
  // For judge (answer like "True/False"), check if option contains the answer
  return answer.includes(optLetter) || opt.includes(answer) || opt.toUpperCase().includes(answer)
}

const optionClass = (opt) => {
  if (!answered.value) return 'border-gray-200 hover:border-primary hover:bg-blue-50'
  const isAnswer = isCorrectOption(opt)
  if (isAnswer) return 'border-green-500 bg-green-50'
  if (selectedOption.value === opt && !isAnswer) return 'border-red-500 bg-red-50'
  return 'border-gray-200 opacity-50'
}

const optionCircleClass = (opt) => {
  if (!answered.value) return 'bg-gray-100 text-gray-600'
  const isAnswer = isCorrectOption(opt)
  if (isAnswer) return 'bg-green-500 text-white'
  if (selectedOption.value === opt) return 'bg-red-500 text-white'
  return 'bg-gray-100 text-gray-400'
}

const loadQueue = async () => {
  try {
    const params = {}
    if (filterCategory.value) params.category_id = filterCategory.value
    if (filterTag.value) params.tag_id = filterTag.value
    if (filterSearch.value) params.search = filterSearch.value

    let res
    if (mode.value === 'wrong') {
      res = await studyApi.wrongQuestions({ limit: 50, ...params })
    } else {
      res = await studyApi.queue({ new_limit: 10, review_limit: 50, ...params })
    }
    queue.value = res.data
    currentIndex.value = 0
    answered.value = false
    selectedOption.value = null
    userAnswer.value = ''
    reviewResult.value = null
    completed.value = 0
    if (queue.value.length > 0) {
      startTimer()
    } else {
      // Queue empty - load session summary
      await loadSessionSummary()
    }
  } catch (e) {
    console.error('Failed to load queue:', e)
  }
}

const loadSessionSummary = async () => {
  try {
    const res = await studyApi.sessionSummary({ hours: 24 })
    sessionSummary.value = res.data
  } catch (e) {
    console.error('Failed to load session summary:', e)
  }
}

const switchMode = (newMode) => {
  mode.value = newMode
  sessionSummary.value = null
  loadQueue()
}

const ratingBadgeClass = (label) => ({
  'Again': 'bg-red-100 text-red-700',
  'Hard': 'bg-orange-100 text-orange-700',
  'Good': 'bg-green-100 text-green-700',
  'Easy': 'bg-blue-100 text-blue-700'
}[label] || 'bg-gray-100 text-gray-700')

const selectOption = (opt) => {
  if (answered.value) return
  selectedOption.value = opt
  submitAnswer()
}

const submitAnswer = () => {
  if (!selectedOption.value && !userAnswer.value.trim()) return
  submitReview()
}

const submitReview = async () => {
  stopTimer()
  const usedTime = elapsedSec.value

  // Determine selected answer string
  let selectedAnswer = ''
  if (selectedOption.value) {
    // Extract letter prefix (e.g. "A" from "A. Some text")
    selectedAnswer = selectedOption.value.charAt(0)
  } else {
    selectedAnswer = userAnswer.value.trim()
  }

  try {
    const res = await studyApi.review({
      question_id: currentQuestion.value.id,
      selected_answer: selectedAnswer,
      used_time_sec: usedTime
    })

    reviewResult.value = res.data
    isCorrect.value = res.data.is_correct
    answered.value = true
    completed.value++
  } catch (e) {
    console.error('Failed to submit review:', e)
    // Fallback: local check
    answered.value = true
    const answer = (currentQuestion.value.answer || '').trim().toUpperCase()
    if (selectedOption.value) {
      const selected = selectedOption.value.trim().toUpperCase()
      isCorrect.value = selected.includes(answer) || answer.includes(selected.charAt(0))
    } else {
      isCorrect.value = userAnswer.value.trim().toUpperCase() === answer
    }
  }
}

const showAnswerDirectly = () => {
  stopTimer()
  // Submit as wrong answer (empty) to trigger Again rating
  submitReviewWithAnswer('__skip__')
}

const submitReviewWithAnswer = async (answer) => {
  stopTimer()
  try {
    const res = await studyApi.review({
      question_id: currentQuestion.value.id,
      selected_answer: answer,
      used_time_sec: elapsedSec.value
    })
    reviewResult.value = res.data
    isCorrect.value = res.data.is_correct
    answered.value = true
    completed.value++
  } catch (e) {
    console.error('Failed to submit review:', e)
    answered.value = true
    isCorrect.value = false
  }
}

const nextQuestion = () => {
  if (currentIndex.value < queue.value.length - 1) {
    currentIndex.value++
    answered.value = false
    selectedOption.value = null
    userAnswer.value = ''
    reviewResult.value = null
    startTimer()
  } else {
    loadQueue()
  }
}

const prevQuestion = () => {
  if (currentIndex.value > 0) {
    currentIndex.value--
    answered.value = false
    selectedOption.value = null
    userAnswer.value = ''
    reviewResult.value = null
    startTimer()
  }
}

const clearFilters = () => {
  filterCategory.value = ''
  filterTag.value = ''
  filterSearch.value = ''
  loadQueue()
}

const loadCategories = async () => {
  try {
    const res = await questionApi.categories()
    categories.value = res.data
  } catch (e) {
    console.error('加载分类失败:', e)
  }
}

const loadTags = async () => {
  try {
    const res = await tagApi.list()
    tags.value = res.data
  } catch (e) {
    console.error('加载标签失败:', e)
  }
}

onMounted(() => {
  // Read filter params from route query (e.g. from Questions page "开始练习")
  if (route.query.category_id) filterCategory.value = String(route.query.category_id)
  if (route.query.tag_id) filterTag.value = String(route.query.tag_id)
  if (route.query.search) filterSearch.value = String(route.query.search)
  loadCategories()
  loadTags()
  loadQueue()
})
onUnmounted(stopTimer)
</script>
