<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">📝 题库</h1>
      <div class="flex items-center space-x-2">
        <button @click="initTags" class="btn-secondary text-sm">
          🏷️ 初始化标签
        </button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="card flex flex-wrap items-center gap-4">
      <input
        v-model="searchQuery"
        placeholder="🔍 搜索题目..."
        class="input flex-1 min-w-[200px]"
        @keyup.enter="onFilterChange"
      />
      <select v-model="filterCategory" class="input w-40" @change="onFilterChange">
        <option value="">全部分类</option>
        <option v-for="cat in categories" :key="cat.id" :value="cat.id">
          {{ cat.name }}
        </option>
      </select>
      <select v-model="filterTag" class="input w-40" @change="onFilterChange">
        <option value="">全部标签</option>
        <option v-for="tag in tags" :key="tag.id" :value="tag.id">
          {{ tag.name }}
        </option>
      </select>
      <button @click="onFilterChange" class="btn-primary">搜索</button>
      <button v-if="filterCategory || filterTag || searchQuery" @click="clearFilters" class="btn-secondary text-sm">
        清除
      </button>
    </div>

    <!-- 模式切换栏 -->
    <div class="flex items-center gap-3 flex-wrap">
      <div class="flex bg-gray-100 rounded-lg p-1">
        <button
          @click="switchMode('browse')"
          class="px-4 py-1.5 rounded-md text-sm font-medium transition-colors"
          :class="interactionMode === 'browse' ? 'bg-white text-primary shadow-sm' : 'text-gray-500'"
        >
          📖 浏览
        </button>
        <button
          @click="switchMode('practice')"
          class="px-4 py-1.5 rounded-md text-sm font-medium transition-colors"
          :class="interactionMode === 'practice' ? 'bg-white text-primary shadow-sm' : 'text-gray-500'"
        >
          ✍️ 练习
        </button>
        <button
          @click="switchMode('study')"
          class="px-4 py-1.5 rounded-md text-sm font-medium transition-colors"
          :class="interactionMode === 'study' ? 'bg-white text-primary shadow-sm' : 'text-gray-500'"
        >
          🎯 刷题
        </button>
      </div>

      <!-- 刷题模式专属：正常/错题切换 + 计时 -->
      <template v-if="interactionMode === 'study'">
        <div class="flex bg-gray-100 rounded-lg p-1">
          <button
            @click="switchStudySubMode('normal')"
            class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
            :class="studySubMode === 'normal' ? 'bg-white text-primary shadow-sm' : 'text-gray-500'"
          >
            正常刷题
          </button>
          <button
            @click="switchStudySubMode('wrong')"
            class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
            :class="studySubMode === 'wrong' ? 'bg-white text-danger shadow-sm' : 'text-gray-500'"
          >
            ❌ 错题本
          </button>
        </div>
        <span class="text-sm text-gray-600">
          进度: <span class="font-bold text-primary">{{ studyCompleted }}/{{ studyQueue.length + studyCompleted }}</span>
        </span>
        <span class="text-sm text-gray-600">
          耗时: <span class="font-bold text-warning">{{ formatTime(elapsedSec) }}</span>
        </span>
      </template>

      <span v-if="interactionMode === 'practice'" class="text-sm text-gray-500">
        点击选项作答，系统自动判定并记录学习进度
      </span>
    </div>

    <!-- ==================== 刷题模式 ==================== -->
    <template v-if="interactionMode === 'study'">
      <!-- 空状态 / 学习小结 -->
      <div v-if="!currentStudyQuestion && studyQueue.length === 0" class="space-y-6">
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

        <div class="card text-center py-16">
          <div class="text-6xl mb-4">🎉</div>
          <h2 class="text-xl font-bold mb-2">
            {{ studySubMode === 'wrong' ? '错题本已清空！' : '今日任务已完成！' }}
          </h2>
          <p class="text-gray-600 mb-6">
            {{ studySubMode === 'wrong' ? '所有错题已复习完毕' : '明天再来复习吧，间隔重复是记忆的秘诀' }}
          </p>
          <div class="space-x-4">
            <button v-if="studySubMode === 'wrong'" @click="switchStudySubMode('normal')" class="btn-secondary">
              ← 返回正常刷题
            </button>
            <router-link to="/stats" class="btn-primary">查看学习统计</router-link>
          </div>
        </div>
      </div>

      <!-- 刷题题目卡片 -->
      <div v-else-if="currentStudyQuestion" class="space-y-6">
        <div class="flex items-center justify-between text-sm text-gray-500">
          <span>{{ currentStudyQuestion.category }}</span>
          <span>
            {{ studyIndex + 1 }} / {{ studyQueue.length }}
            <span v-if="!currentStudyQuestion.is_new" class="ml-2 text-warning">🔄 复习</span>
            <span v-else class="ml-2 text-success">🆕 新题</span>
          </span>
        </div>

        <div class="card">
          <div class="mb-6">
            <QuestionMeta
              :type="currentStudyQuestion.question_type"
              :category="currentStudyQuestion.category"
              :page-number="currentStudyQuestion.page_number"
              :is-new="currentStudyQuestion.is_new"
              show-review-badge
            />
            <h2 class="text-xl font-medium text-gray-900 leading-relaxed">
              {{ currentStudyQuestion.question_text }}
            </h2>
          </div>

          <!-- 选项 -->
          <div v-if="currentStudyQuestion.options && currentStudyQuestion.options.length > 0" class="space-y-3">
            <button
              v-for="(opt, idx) in currentStudyQuestion.options"
              :key="idx"
              @click="selectStudyOption(opt)"
              class="w-full text-left p-4 rounded-lg border-2 transition-all duration-200"
              :class="studyOptionClass(opt)"
              :disabled="studyAnswered"
            >
              <div class="flex items-center">
                <span
                  class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold mr-3"
                  :class="studyOptionCircleClass(opt)"
                >
                  {{ opt.charAt(0) }}
                </span>
                <span>{{ opt }}</span>
              </div>
            </button>
          </div>

          <!-- 填空题 -->
          <div v-else-if="currentStudyQuestion.question_type === 'fill'" class="space-y-3">
            <input
              v-model="studyUserAnswer"
              placeholder="请输入答案..."
              class="input"
              :disabled="studyAnswered"
              @keyup.enter="submitStudyAnswer"
            />
            <button v-if="!studyAnswered" @click="submitStudyAnswer" class="btn-primary w-full">
              提交答案
            </button>
          </div>
        </div>

        <!-- 答案反馈 -->
        <div v-if="studyAnswered" class="card" :class="studyIsCorrect ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'">
          <div class="flex items-center mb-3">
            <span class="text-2xl mr-2">{{ studyIsCorrect ? '✅' : '❌' }}</span>
            <span class="font-bold" :class="studyIsCorrect ? 'text-green-800' : 'text-red-800'">
              {{ studyIsCorrect ? '回答正确！' : '回答错误' }}
            </span>
            <span v-if="studyReviewResult" class="ml-auto text-sm text-gray-500">
              系统评级: <span class="font-bold">{{ studyReviewResult.auto_rating_label }}</span>
              <span v-if="studyReviewResult.next_interval_days > 0" class="ml-2">
                下次复习: {{ studyReviewResult.next_interval_days }}天后
              </span>
              <span v-else class="ml-2">下次复习: 今天</span>
            </span>
          </div>
          <p class="font-medium mb-2" :class="studyIsCorrect ? 'text-green-800' : 'text-red-800'">
            正确答案：{{ currentStudyQuestion.answer }}
          </p>
          <p v-if="currentStudyQuestion.explanation" :class="studyIsCorrect ? 'text-green-700' : 'text-red-700'">
            解析：{{ currentStudyQuestion.explanation }}
          </p>
          <div v-if="currentStudyQuestion.pdf_id && currentStudyQuestion.page_number" class="mt-3">
            <router-link
              :to="`/pdf-view/${currentStudyQuestion.pdf_id}?page=${currentStudyQuestion.page_number}`"
              class="text-sm text-primary hover:underline"
            >
              📄 查看原文（第{{ currentStudyQuestion.page_number }}页）
            </router-link>
          </div>
        </div>

        <!-- 导航 -->
        <div class="flex items-center justify-between">
          <button
            @click="prevStudyQuestion"
            :disabled="studyIndex <= 0"
            class="btn-secondary"
            :class="{ 'opacity-50': studyIndex <= 0 }"
          >
            ← 上一题
          </button>
          <button
            v-if="!studyAnswered"
            @click="showAnswerDirectly"
            class="text-gray-500 hover:text-gray-700"
          >
            直接看答案
          </button>
          <button v-if="studyAnswered" @click="nextStudyQuestion" class="btn-primary">
            下一题 →
          </button>
        </div>
      </div>
    </template>

    <!-- ==================== 浏览/练习模式 ==================== -->
    <template v-else>
      <!-- 题目列表 -->
      <div class="space-y-4">
        <div
          v-for="q in questions"
          :key="q.id"
          class="card hover:shadow-md transition-shadow"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <QuestionMeta
                :type="q.question_type"
                :category="q.category"
                :page-number="q.page_number"
              />
              <p class="text-gray-900 font-medium mb-3">{{ q.question_text }}</p>

              <!-- 选项: 浏览模式 -->
              <div v-if="interactionMode === 'browse' && q.options && q.options.length > 0" class="space-y-1 mb-3">
                <div
                  v-for="opt in q.options"
                  :key="opt"
                  class="text-sm text-gray-600 pl-4"
                >
                  {{ opt }}
                </div>
              </div>

              <!-- 选项: 练习模式 -->
              <div v-if="interactionMode === 'practice' && q.options && q.options.length > 0" class="space-y-2 mb-3">
                <button
                  v-for="opt in q.options"
                  :key="opt"
                  @click="selectOption(q, opt)"
                  :disabled="answeredQuestions[q.id]"
                  class="w-full text-left p-3 rounded-lg border-2 transition-all duration-200 text-sm"
                  :class="optionClass(q, opt)"
                >
                  <div class="flex items-center">
                    <span
                      class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold mr-3"
                      :class="optionCircleClass(q, opt)"
                    >
                      {{ opt.charAt(0) }}
                    </span>
                    <span>{{ opt }}</span>
                  </div>
                </button>
              </div>

              <!-- 填空题练习模式 -->
              <div v-if="interactionMode === 'practice' && q.question_type === 'fill' && !q.options?.length" class="space-y-2 mb-3">
                <input
                  v-model="fillAnswers[q.id]"
                  placeholder="请输入答案..."
                  class="input"
                  :disabled="answeredQuestions[q.id]"
                  @keyup.enter="submitFill(q)"
                />
                <button
                  v-if="!answeredQuestions[q.id]"
                  @click="submitFill(q)"
                  class="btn-primary text-sm"
                >
                  提交答案
                </button>
              </div>

              <!-- 答案和解析: 浏览模式 -->
              <div v-if="interactionMode === 'browse' && showAnswer[q.id]" class="mt-3 p-3 bg-green-50 rounded-lg">
                <p class="text-green-800 font-medium">答案：{{ q.answer }}</p>
                <p v-if="q.explanation" class="text-green-700 text-sm mt-1">解析：{{ q.explanation }}</p>
              </div>

              <!-- 答案和解析: 练习模式 -->
              <div
                v-if="interactionMode === 'practice' && answeredQuestions[q.id]"
                class="mt-3 p-3 rounded-lg"
                :class="answeredQuestions[q.id].is_correct ? 'bg-green-50' : 'bg-red-50'"
              >
                <div class="flex items-center mb-2">
                  <span class="text-lg mr-2">{{ answeredQuestions[q.id].is_correct ? '✅' : '❌' }}</span>
                  <span class="font-medium" :class="answeredQuestions[q.id].is_correct ? 'text-green-800' : 'text-red-800'">
                    {{ answeredQuestions[q.id].is_correct ? '回答正确！' : '回答错误' }}
                  </span>
                  <span v-if="answeredQuestions[q.id].auto_rating_label" class="ml-auto text-sm text-gray-500">
                    评级: <span class="font-bold">{{ answeredQuestions[q.id].auto_rating_label }}</span>
                    <span v-if="answeredQuestions[q.id].next_interval_days > 0" class="ml-2">
                      下次复习: {{ answeredQuestions[q.id].next_interval_days }}天后
                    </span>
                  </span>
                </div>
                <p class="font-medium" :class="answeredQuestions[q.id].is_correct ? 'text-green-800' : 'text-red-800'">
                  正确答案：{{ q.answer }}
                </p>
                <p v-if="q.explanation" :class="answeredQuestions[q.id].is_correct ? 'text-green-700' : 'text-red-700'" class="text-sm mt-1">
                  解析：{{ q.explanation }}
                </p>
              </div>

              <!-- 标签 -->
              <div class="flex items-center gap-2 mt-3 flex-wrap">
                <span
                  v-for="tag in q.tags"
                  :key="tag.id"
                  class="px-2 py-0.5 rounded-full text-xs text-white"
                  :style="{ backgroundColor: tag.color }"
                >
                  {{ tag.name }}
                </span>
                <div class="relative group">
                  <button class="text-gray-400 hover:text-primary text-sm">+ 标签</button>
                  <div class="absolute top-full left-0 mt-1 bg-white shadow-lg rounded-lg border p-2 hidden group-hover:block z-10 min-w-[120px]">
                    <button
                      v-for="tag in availableTags(q)"
                      :key="tag.id"
                      @click="addTag(q.id, tag.id)"
                      class="block w-full text-left px-2 py-1 text-sm hover:bg-gray-100 rounded"
                    >
                      <span class="w-3 h-3 inline-block rounded-full mr-1" :style="{ backgroundColor: tag.color }"></span>
                      {{ tag.name }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="flex items-center space-x-2 ml-4">
              <button
                v-if="interactionMode === 'browse'"
                @click="toggleAnswer(q.id)"
                class="btn-secondary text-sm"
              >
                {{ showAnswer[q.id] ? '隐藏答案' : '查看答案' }}
              </button>
              <button
                v-if="interactionMode === 'practice' && answeredQuestions[q.id]"
                @click="resetAnswer(q.id)"
                class="btn-secondary text-sm"
              >
                🔄 重置
              </button>
              <router-link
                :to="`/pdf-view/${q.pdf_id}?page=${q.page_number}`"
                class="btn-secondary text-sm"
              >
                📄 原文
              </router-link>
              <button @click="deleteQuestion(q.id)" class="text-gray-400 hover:text-danger">🗑️</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="flex items-center justify-center space-x-2">
        <button
          @click="page--; loadQuestions()"
          :disabled="page <= 1"
          class="btn-secondary"
          :class="{ 'opacity-50 cursor-not-allowed': page <= 1 }"
        >
          上一页
        </button>
        <span class="text-gray-600">第 {{ page }} 页 / 共 {{ totalPages }} 页</span>
        <button
          @click="page++; loadQuestions()"
          :disabled="page >= totalPages"
          class="btn-secondary"
          :class="{ 'opacity-50 cursor-not-allowed': page >= totalPages }"
        >
          下一页
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { questionApi, tagApi, studyApi } from '../api'
import { useStudyStore } from '../stores/studyStore'
import QuestionMeta from '../components/QuestionMeta.vue'

const route = useRoute()
const router = useRouter()
const studyStore = useStudyStore()

// ==================== 共享状态 ====================
const categories = ref([])
const tags = ref([])
const searchQuery = ref('')
const filterCategory = ref('')
const filterTag = ref('')

// 浏览/练习模式状态
const questions = ref([])
const page = ref(1)
const size = ref(20)
const total = ref(0)
const showAnswer = ref({})
const interactionMode = ref('browse') // 'browse' | 'practice' | 'study'
const answeredQuestions = ref({})
const fillAnswers = ref({})

// 刷题模式状态
const studyQueue = ref([])
const studyIndex = ref(0)
const studyAnswered = ref(false)
const studySelectedOption = ref(null)
const studyUserAnswer = ref('')
const studyIsCorrect = ref(false)
const studyCompleted = ref(0)
const studyReviewResult = ref(null)
const studySubMode = ref('normal') // 'normal' | 'wrong'
const sessionSummary = ref(null)

// 计时器
const startTime = ref(0)
const elapsedSec = ref(0)
let timerId = null

// ==================== 计算属性 ====================
const totalPages = computed(() => Math.ceil(total.value / size.value) || 1)
const currentStudyQuestion = computed(() => studyQueue.value[studyIndex.value] || null)

// ==================== 工具函数 ====================
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

const ratingBadgeClass = (label) => ({
  'Again': 'bg-red-100 text-red-700',
  'Hard': 'bg-orange-100 text-orange-700',
  'Good': 'bg-green-100 text-green-700',
  'Easy': 'bg-blue-100 text-blue-700'
}[label] || 'bg-gray-100 text-gray-700')

// ==================== 数据加载 ====================
const loadQuestions = async () => {
  try {
    const res = await questionApi.list({
      search: searchQuery.value || undefined,
      category_id: filterCategory.value || undefined,
      tag_id: filterTag.value || undefined,
      page: page.value,
      size: size.value
    })
    questions.value = res.data.items
    total.value = res.data.total
    answeredQuestions.value = {}
    fillAnswers.value = {}
  } catch (e) {
    console.error('加载题目失败:', e)
  }
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

const loadStudyQueue = async () => {
  try {
    const params = {}
    if (filterCategory.value) params.category_id = filterCategory.value
    if (filterTag.value) params.tag_id = filterTag.value
    if (searchQuery.value) params.search = searchQuery.value

    let res
    if (studySubMode.value === 'wrong') {
      res = await studyApi.wrongQuestions({ limit: 50, ...params })
    } else {
      res = await studyApi.queue({ new_limit: 10, review_limit: 50, ...params })
    }
    studyQueue.value = res.data
    studyIndex.value = 0
    studyAnswered.value = false
    studySelectedOption.value = null
    studyUserAnswer.value = ''
    studyReviewResult.value = null
    studyCompleted.value = 0
    if (studyQueue.value.length > 0) {
      startTimer()
    } else {
      await loadSessionSummary()
    }
  } catch (e) {
    console.error('加载刷题队列失败:', e)
  }
}

const loadSessionSummary = async () => {
  try {
    const res = await studyApi.sessionSummary({ hours: 24 })
    sessionSummary.value = res.data
  } catch (e) {
    console.error('加载学习小结失败:', e)
  }
}

// ==================== 模式切换 ====================
const switchMode = (mode) => {
  interactionMode.value = mode
  if (mode === 'study') {
    loadStudyQueue()
  } else if (mode === 'browse' || mode === 'practice') {
    stopTimer()
    if (questions.value.length === 0) loadQuestions()
  }
}

const switchStudySubMode = (subMode) => {
  studySubMode.value = subMode
  sessionSummary.value = null
  loadStudyQueue()
}

const onFilterChange = () => {
  page.value = 1
  if (interactionMode.value === 'study') {
    loadStudyQueue()
  } else {
    loadQuestions()
  }
}

const clearFilters = () => {
  searchQuery.value = ''
  filterCategory.value = ''
  filterTag.value = ''
  onFilterChange()
}

// ==================== 浏览/练习模式逻辑 ====================
const availableTags = (question) => {
  const qTagIds = new Set(question.tags.map(t => t.id))
  return tags.value.filter(t => !qTagIds.has(t.id))
}

const toggleAnswer = (id) => {
  showAnswer.value[id] = !showAnswer.value[id]
}

const isCorrectOption = (q, opt) => {
  if (!q.answer) return false
  const answer = q.answer.trim().toUpperCase()
  const optLetter = opt.charAt(0).toUpperCase()
  return answer.includes(optLetter) || opt.includes(q.answer) || opt.toUpperCase().includes(answer)
}

const optionClass = (q, opt) => {
  const ans = answeredQuestions.value[q.id]
  if (!ans) return 'border-gray-200 hover:border-primary hover:bg-blue-50'
  const isAnswer = isCorrectOption(q, opt)
  if (isAnswer) return 'border-green-500 bg-green-50'
  if (ans.selectedOption === opt && !isAnswer) return 'border-red-500 bg-red-50'
  return 'border-gray-200 opacity-50'
}

const optionCircleClass = (q, opt) => {
  const ans = answeredQuestions.value[q.id]
  if (!ans) return 'bg-gray-100 text-gray-600'
  const isAnswer = isCorrectOption(q, opt)
  if (isAnswer) return 'bg-green-500 text-white'
  if (ans.selectedOption === opt) return 'bg-red-500 text-white'
  return 'bg-gray-100 text-gray-400'
}

const selectOption = async (q, opt) => {
  if (answeredQuestions.value[q.id]) return
  const selectedAnswer = opt.charAt(0)
  await submitReview(q, selectedAnswer, opt)
}

const submitFill = async (q) => {
  if (answeredQuestions.value[q.id]) return
  const answer = fillAnswers.value[q.id]?.trim()
  if (!answer) return
  await submitReview(q, answer, answer)
}

const submitReview = async (q, selectedAnswer, displayOption) => {
  try {
    const res = await studyApi.review({
      question_id: q.id,
      selected_answer: selectedAnswer,
      used_time_sec: 0,
      is_practice: interactionMode.value === 'practice'
    })
    answeredQuestions.value[q.id] = {
      selectedOption: displayOption,
      is_correct: res.data.is_correct,
      auto_rating_label: res.data.auto_rating_label,
      next_interval_days: res.data.next_interval_days
    }
    studyStore.bumpStatsVersion()
  } catch (e) {
    console.error('提交答案失败:', e)
    const correct = q.answer?.trim().toUpperCase() === selectedAnswer.toUpperCase()
    answeredQuestions.value[q.id] = {
      selectedOption: displayOption,
      is_correct: correct,
      auto_rating_label: correct ? 'Good' : 'Again',
      next_interval_days: 0
    }
  }
}

const resetAnswer = (qid) => {
  delete answeredQuestions.value[qid]
  delete fillAnswers.value[qid]
  answeredQuestions.value = { ...answeredQuestions.value }
}

// ==================== 刷题模式逻辑 ====================
const studyIsCorrectOption = (opt) => {
  if (!currentStudyQuestion.value || !currentStudyQuestion.value.answer) return false
  const answer = currentStudyQuestion.value.answer.trim().toUpperCase()
  const optLetter = opt.charAt(0).toUpperCase()
  return answer.includes(optLetter) || opt.includes(answer) || opt.toUpperCase().includes(answer)
}

const studyOptionClass = (opt) => {
  if (!studyAnswered.value) return 'border-gray-200 hover:border-primary hover:bg-blue-50'
  const isAnswer = studyIsCorrectOption(opt)
  if (isAnswer) return 'border-green-500 bg-green-50'
  if (studySelectedOption.value === opt && !isAnswer) return 'border-red-500 bg-red-50'
  return 'border-gray-200 opacity-50'
}

const studyOptionCircleClass = (opt) => {
  if (!studyAnswered.value) return 'bg-gray-100 text-gray-600'
  const isAnswer = studyIsCorrectOption(opt)
  if (isAnswer) return 'bg-green-500 text-white'
  if (studySelectedOption.value === opt) return 'bg-red-500 text-white'
  return 'bg-gray-100 text-gray-400'
}

const selectStudyOption = (opt) => {
  if (studyAnswered.value) return
  studySelectedOption.value = opt
  submitStudyAnswer()
}

const submitStudyAnswer = async () => {
  stopTimer()
  let selectedAnswer = ''
  if (studySelectedOption.value) {
    selectedAnswer = studySelectedOption.value.charAt(0)
  } else {
    selectedAnswer = studyUserAnswer.value.trim()
  }
  if (!selectedAnswer) return

  try {
    const res = await studyApi.review({
      question_id: currentStudyQuestion.value.id,
      selected_answer: selectedAnswer,
      used_time_sec: elapsedSec.value
    })
    studyReviewResult.value = res.data
    studyIsCorrect.value = res.data.is_correct
    studyAnswered.value = true
    studyCompleted.value++
    studyStore.bumpStatsVersion()
  } catch (e) {
    console.error('提交答案失败:', e)
    studyAnswered.value = true
    const answer = (currentStudyQuestion.value.answer || '').trim().toUpperCase()
    if (studySelectedOption.value) {
      const selected = studySelectedOption.value.trim().toUpperCase()
      studyIsCorrect.value = selected.includes(answer) || answer.includes(selected.charAt(0))
    } else {
      studyIsCorrect.value = studyUserAnswer.value.trim().toUpperCase() === answer
    }
  }
}

const showAnswerDirectly = () => {
  stopTimer()
  submitStudyReviewWithAnswer('__skip__')
}

const submitStudyReviewWithAnswer = async (answer) => {
  stopTimer()
  try {
    const res = await studyApi.review({
      question_id: currentStudyQuestion.value.id,
      selected_answer: answer,
      used_time_sec: elapsedSec.value
    })
    studyReviewResult.value = res.data
    studyIsCorrect.value = res.data.is_correct
    studyAnswered.value = true
    studyCompleted.value++
    studyStore.bumpStatsVersion()
  } catch (e) {
    console.error('提交答案失败:', e)
    studyAnswered.value = true
    studyIsCorrect.value = false
  }
}

const nextStudyQuestion = () => {
  if (studyIndex.value < studyQueue.value.length - 1) {
    studyIndex.value++
    studyAnswered.value = false
    studySelectedOption.value = null
    studyUserAnswer.value = ''
    studyReviewResult.value = null
    startTimer()
  } else {
    loadStudyQueue()
  }
}

const prevStudyQuestion = () => {
  if (studyIndex.value > 0) {
    studyIndex.value--
    studyAnswered.value = false
    studySelectedOption.value = null
    studyUserAnswer.value = ''
    studyReviewResult.value = null
    startTimer()
  }
}

// ==================== 标签管理 ====================
const initTags = async () => {
  try {
    await tagApi.initDefaults()
    await loadTags()
    alert('默认标签初始化成功！')
  } catch (e) {
    alert('初始化失败: ' + e.message)
  }
}

const addTag = async (qid, tid) => {
  try {
    await questionApi.addTag(qid, tid)
    await loadQuestions()
  } catch (e) {
    alert('添加标签失败: ' + e.message)
  }
}

const deleteQuestion = async (id) => {
  if (!confirm('确定删除此题目？')) return
  alert('删除功能需要后端支持')
}

// ==================== 生命周期 ====================
onMounted(() => {
  // 读取路由参数
  if (route.query.mode === 'study') interactionMode.value = 'study'
  if (route.query.mode === 'practice') interactionMode.value = 'practice'
  if (route.query.mode === 'browse') interactionMode.value = 'browse'
  if (route.query.category_id) filterCategory.value = String(route.query.category_id)
  if (route.query.tag_id) filterTag.value = String(route.query.tag_id)
  if (route.query.search) searchQuery.value = String(route.query.search)

  loadCategories()
  loadTags()

  if (interactionMode.value === 'study') {
    loadStudyQueue()
  } else {
    loadQuestions()
  }
})

onUnmounted(stopTimer)
</script>
