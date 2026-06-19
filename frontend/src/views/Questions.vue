<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">📝 题库管理</h1>
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
        @keyup.enter="loadQuestions"
      />
      <select v-model="filterCategory" class="input w-40" @change="loadQuestions">
        <option value="">全部分类</option>
        <option v-for="cat in categories" :key="cat.id" :value="cat.id">
          {{ cat.name }}
        </option>
      </select>
      <select v-model="filterTag" class="input w-40" @change="loadQuestions">
        <option value="">全部标签</option>
        <option v-for="tag in tags" :key="tag.id" :value="tag.id">
          {{ tag.name }}
        </option>
      </select>
      <button @click="loadQuestions" class="btn-primary">搜索</button>
      <button @click="startPractice" class="btn-primary bg-green-600 hover:bg-green-700">
        ✍️ 开始练习
      </button>
    </div>

    <!-- 浏览/答题模式切换 -->
    <div class="flex items-center gap-3">
      <div class="flex bg-gray-100 rounded-lg p-1">
        <button
          @click="interactionMode = 'browse'"
          class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
          :class="interactionMode === 'browse' ? 'bg-white text-primary shadow-sm' : 'text-gray-500'"
        >
          📖 浏览模式
        </button>
        <button
          @click="interactionMode = 'practice'"
          class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
          :class="interactionMode === 'practice' ? 'bg-white text-primary shadow-sm' : 'text-gray-500'"
        >
          ✍️ 答题模式
        </button>
      </div>
      <span v-if="interactionMode === 'practice'" class="text-sm text-gray-500">
        点击选项作答，系统自动判定并记录学习进度
      </span>
    </div>

    <!-- 题目列表 -->
    <div class="space-y-4">
      <div
        v-for="q in questions"
        :key="q.id"
        class="card hover:shadow-md transition-shadow"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <!-- 题目标题 -->
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

            <!-- 选项: 答题模式 -->
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

            <!-- 填空题答题模式 -->
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

            <!-- 答案和解析: 浏览模式手动展开 -->
            <div v-if="interactionMode === 'browse' && showAnswer[q.id]" class="mt-3 p-3 bg-green-50 rounded-lg">
              <p class="text-green-800 font-medium">
                答案：{{ q.answer }}
              </p>
              <p v-if="q.explanation" class="text-green-700 text-sm mt-1">
                解析：{{ q.explanation }}
              </p>
            </div>

            <!-- 答案和解析: 答题模式作答后显示 -->
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
            <button
              @click="deleteQuestion(q.id)"
              class="text-gray-400 hover:text-danger"
            >
              🗑️
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="flex items-center justify-center space-x-2">
      <button
        @click="page--"
        :disabled="page <= 1"
        class="btn-secondary"
        :class="{ 'opacity-50 cursor-not-allowed': page <= 1 }"
      >
        上一页
      </button>
      <span class="text-gray-600">第 {{ page }} 页 / 共 {{ totalPages }} 页</span>
      <button
        @click="page++"
        :disabled="page >= totalPages"
        class="btn-secondary"
        :class="{ 'opacity-50 cursor-not-allowed': page >= totalPages }"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { questionApi, tagApi, studyApi } from '../api'
import QuestionMeta from '../components/QuestionMeta.vue'

const router = useRouter()

const questions = ref([])
const categories = ref([])
const tags = ref([])
const searchQuery = ref('')
const filterCategory = ref('')
const filterTag = ref('')
const page = ref(1)
const size = ref(20)
const total = ref(0)
const showAnswer = ref({})

// Practice mode state
const interactionMode = ref('browse') // 'browse' or 'practice'
const answeredQuestions = ref({}) // { [qid]: { selectedOption, is_correct, auto_rating_label, next_interval_days } }
const fillAnswers = ref({}) // { [qid]: 'user input' }

const totalPages = computed(() => Math.ceil(total.value / size.value) || 1)

const availableTags = (question) => {
  const qTagIds = new Set(question.tags.map(t => t.id))
  return tags.value.filter(t => !qTagIds.has(t.id))
}

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
    // Clear practice state when loading new questions
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

const toggleAnswer = (id) => {
  showAnswer.value[id] = !showAnswer.value[id]
}

// --- Practice mode functions ---

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
      used_time_sec: 0
    })
    answeredQuestions.value[q.id] = {
      selectedOption: displayOption,
      is_correct: res.data.is_correct,
      auto_rating_label: res.data.auto_rating_label,
      next_interval_days: res.data.next_interval_days
    }
  } catch (e) {
    console.error('提交答案失败:', e)
    // Fallback: local check
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
  // Force reactivity
  answeredQuestions.value = { ...answeredQuestions.value }
}

const startPractice = () => {
  const query = {}
  if (filterCategory.value) query.category_id = filterCategory.value
  if (filterTag.value) query.tag_id = filterTag.value
  if (searchQuery.value) query.search = searchQuery.value
  router.push({ name: 'Study', query })
}

const deleteQuestion = async (id) => {
  if (!confirm('确定删除此题目？')) return
  // 暂时使用API删除，需要后端添加删除接口
  alert('删除功能需要后端支持')
}

watch(page, loadQuestions)

onMounted(() => {
  loadQuestions()
  loadCategories()
  loadTags()
})
</script>
