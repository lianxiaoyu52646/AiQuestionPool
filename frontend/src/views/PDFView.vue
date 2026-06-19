<template>
  <div class="h-[calc(100vh-8rem)] flex gap-4">
    <!-- PDF 预览区 - 使用 iframe 直接嵌入 -->
    <div class="flex-1 card p-0 overflow-hidden flex flex-col">
      <div class="p-4 border-b flex items-center justify-between">
        <h2 class="font-bold">📄 PDF 预览</h2>
        <div class="flex items-center space-x-2">
          <button @click="prevPage" class="btn-secondary text-sm py-1">←</button>
          <span class="text-sm">{{ currentPage }} / {{ totalPages }}</span>
          <button @click="nextPage" class="btn-secondary text-sm py-1">→</button>
        </div>
      </div>
      <div class="flex-1 overflow-auto bg-gray-100">
        <iframe
          :src="viewerUrl"
          class="w-full border-0"
          style="min-height: 70vh; min-width: 100%"
        ></iframe>
      </div>
    </div>

    <!-- 侧边栏 - 该页题目 -->
    <div class="w-80 card overflow-hidden flex flex-col">
      <div class="p-4 border-b">
        <h2 class="font-bold">📝 本页题目</h2>
      </div>
      <div class="flex-1 overflow-auto p-4 space-y-3">
        <div
          v-for="q in pageQuestions"
          :key="q.id"
          class="p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-blue-50 transition-colors"
          @click="goToQuestion(q.id)"
        >
          <p class="text-sm text-gray-800 line-clamp-2">{{ q.question_text }}</p>
          <div class="mt-2 flex items-center gap-2">
            <span class="text-xs text-gray-500">{{ typeLabel(q.question_type) }}</span>
            <span
              v-for="tag in q.tags"
              :key="tag.id"
              class="px-1.5 py-0.5 rounded text-xs text-white"
              :style="{ backgroundColor: tag.color }"
            >
              {{ tag.name }}
            </span>
          </div>
        </div>
        <div v-if="pageQuestions.length === 0" class="text-center text-gray-400 py-8">
          该页暂无题目
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { questionApi, pdfApi } from '../api'

const route = useRoute()
const router = useRouter()

const pdfId = computed(() => route.params.id)
const targetPage = computed(() => parseInt(route.query.page) || 1)

const pdfFileUrl = computed(() => `/api/pdf/${pdfId.value}/file`)
const viewerUrl = computed(() => `${window.location.origin}/pdf-viewer.html?file=${encodeURIComponent(pdfFileUrl.value)}#page=${currentPage.value}`)
const currentPage = ref(1)
const totalPages = ref(0)
const allQuestions = ref([])

const pageQuestions = computed(() => {
  return allQuestions.value.filter(q => q.page_number === currentPage.value)
})

const typeLabel = (type) => ({ single: '单选', multiple: '多选', judge: '判断', fill: '填空' }[type] || type)

const loadPDF = async () => {
  try {
    // Get PDF info to know total pages
    const res = await pdfApi.list()
    const pdfInfo = res.data.find(p => p.id === parseInt(pdfId.value))
    if (pdfInfo) {
      totalPages.value = pdfInfo.total_pages
    }
    currentPage.value = Math.min(targetPage.value, totalPages.value || 1)
  } catch (e) {
    console.error('加载PDF失败:', e)
  }
}

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

const loadQuestions = async () => {
  try {
    // Load questions filtered by pdf_id, paginated since API limits size to 100
    const all = []
    let page = 1
    const size = 100
    while (true) {
      const res = await questionApi.list({ page, size, pdf_id: pdfId.value })
      all.push(...res.data.items)
      if (all.length >= res.data.total) break
      page++
    }
    allQuestions.value = all
  } catch (e) {
    console.error('加载题目失败:', e)
  }
}

const goToQuestion = (id) => {
  router.push({ path: '/questions', query: { highlight: id } })
}

watch(targetPage, (newPage) => {
  if (newPage) {
    currentPage.value = newPage
  }
})

onMounted(() => {
  loadPDF()
  loadQuestions()
})
</script>
