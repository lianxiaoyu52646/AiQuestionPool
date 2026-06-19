<template>
  <div class="max-w-3xl mx-auto">
    <h1 class="text-2xl font-bold mb-6">📤 上传PDF电子书</h1>

    <!-- PDF 类型选择 -->
    <div class="card mb-6">
      <h3 class="font-bold mb-3">选择PDF类型</h3>
      <div class="flex gap-3 flex-wrap">
        <button
          v-for="opt in pdfTypeOptions"
          :key="opt.value"
          @click="selectedPdfType = opt.value"
          class="px-4 py-2 rounded-lg border-2 transition-colors text-sm"
          :class="selectedPdfType === opt.value
            ? 'border-primary bg-blue-50 text-primary'
            : 'border-gray-200 text-gray-600 hover:border-gray-300'"
        >
          {{ opt.icon }} {{ opt.label }}
        </button>
      </div>
      <p class="text-sm text-gray-500 mt-2">{{ selectedTypeDesc }}</p>

      <!-- 答案PDF: 选择关联的题目PDF -->
      <div v-if="selectedPdfType === 'answer'" class="mt-4">
        <label class="block text-sm font-medium text-gray-700 mb-1">关联的题目PDF</label>
        <select
          v-model="linkedPdfId"
          class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option :value="null" disabled>请选择题目PDF...</option>
          <option
            v-for="qpdf in questionPdfs"
            :key="qpdf.id"
            :value="qpdf.id"
          >
            {{ qpdf.filename }} ({{ qpdf.question_count || 0 }}题)
          </option>
        </select>
      </div>
    </div>

    <!-- 上传区域 -->
    <div
      class="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center transition-colors"
      :class="{ 'border-primary bg-blue-50': isDragging }"
      @dragenter.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @dragover.prevent
      @drop.prevent="handleDrop"
    >
      <div class="text-6xl mb-4">📄</div>
      <p class="text-lg text-gray-600 mb-2">
        拖拽PDF文件到此处，或
        <label class="text-primary cursor-pointer hover:underline">
          点击上传
          <input
            type="file"
            accept=".pdf"
            class="hidden"
            @change="handleFileSelect"
          />
        </label>
      </p>
      <p class="text-sm text-gray-400">支持 .pdf 格式，最大 50MB</p>
      <p v-if="selectedPdfType === 'answer' && !linkedPdfId" class="text-sm text-orange-500 mt-2">
        ⚠️ 请先选择关联的题目PDF
      </p>
    </div>

    <!-- 文件列表 -->
    <div v-if="uploadedFiles.length > 0" class="mt-8">
      <h2 class="text-lg font-bold mb-4">已上传文件</h2>
      <div class="space-y-3">
        <div
          v-for="file in uploadedFiles"
          :key="file.id"
          class="card flex items-center justify-between relative overflow-hidden"
        >
          <div class="flex items-center space-x-4">
            <span class="text-3xl">{{ typeIcon(file.pdf_type) }}</span>
            <div>
              <div class="font-medium">{{ file.filename }}</div>
              <div class="text-sm text-gray-500">
                <span class="inline-block bg-gray-100 px-1.5 py-0.5 rounded text-xs mr-1">
                  {{ typeLabel(file.pdf_type) }}
                </span>
                {{ file.total_pages }}页 | {{ file.question_count || 0 }}题 |
                {{ formatDate(file.upload_time) }}
              </div>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <span
              v-if="file.parse_status === 'parsing'"
              class="text-sm text-primary flex items-center w-40"
            >
              <svg class="animate-spin h-4 w-4 mr-2 shrink-0" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              <span>解析中 {{ file.parse_progress || 0 }}%</span>
            </span>
            <span
              v-else-if="file.parse_status === 'completed' || file.parsed"
              class="text-sm text-success"
            >
              ✅ 已解析 ({{ file.question_count || file.parsed_questions || 0 }}题)
            </span>
            <span
              v-else-if="file.parse_status === 'failed'"
              class="text-sm text-danger"
            >
              ❌ 解析失败
            </span>
            <!-- Progress bar for parsing -->
            <div
              v-if="file.parse_status === 'parsing'"
              class="absolute bottom-0 left-0 h-1 bg-primary transition-all duration-500"
              :style="{ width: (file.parse_progress || 0) + '%' }"
            ></div>
            <button
              v-if="file.parse_status !== 'parsing' && !file.parsed && file.parse_status !== 'completed'"
              @click="parsePdf(file)"
              class="btn-primary text-sm"
            >
              🚀 解析题目
            </button>
            <router-link
              :to="`/pdf-view/${file.id}`"
              class="btn-secondary text-sm"
            >
              预览
            </router-link>
            <button
              @click="deletePdf(file)"
              class="text-gray-400 hover:text-danger transition-colors"
            >
              🗑️
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { pdfApi } from '../api'

const isDragging = ref(false)
const uploadedFiles = ref([])
const selectedPdfType = ref('combined')
const linkedPdfId = ref(null)
let pollTimer = null

const pdfTypeOptions = [
  { value: 'question', label: '题目PDF（扫描版）', icon: '📝' },
  { value: 'answer', label: '答案PDF（文字版）', icon: '📖' },
  { value: 'combined', label: '题答合一', icon: '📚' },
]

const selectedTypeDesc = computed(() => {
  const opt = pdfTypeOptions.find(o => o.value === selectedPdfType.value)
  if (selectedPdfType.value === 'question') return '扫描版题目PDF，将使用OCR自动识别文字'
  if (selectedPdfType.value === 'answer') return '答案PDF，需关联到已上传的题目PDF进行匹配'
  return '题目和答案在同一PDF中'
})

const questionPdfs = computed(() => {
  return uploadedFiles.value.filter(f => f.pdf_type === 'question')
})

const typeIcon = (t) => {
  if (t === 'question') return '📝'
  if (t === 'answer') return '📖'
  return '📚'
}

const typeLabel = (t) => {
  if (t === 'question') return '题目'
  if (t === 'answer') return '答案'
  return '合一'
}

const loadFiles = async () => {
  try {
    const res = await pdfApi.list()
    uploadedFiles.value = res.data.map(f => ({
      ...f,
      parsed: f.parse_status === 'completed' || f.question_count > 0
    }))
    startPolling()
  } catch (e) {
    console.error('加载文件列表失败:', e)
  }
}

const startPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    let stillParsing = false
    for (const file of uploadedFiles.value) {
      if (file.parse_status === 'parsing') {
        stillParsing = true
        try {
          const res = await pdfApi.parseStatus(file.id)
          file.parse_status = res.data.status
          file.parse_progress = res.data.progress
          file.parsed_questions = res.data.parsed_questions
          if (res.data.status === 'completed') {
            file.parsed = true
            file.question_count = res.data.parsed_questions
          } else if (res.data.status === 'failed') {
            file.parse_error = res.data.error
          }
        } catch (e) {
          console.error('轮询失败:', e)
        }
      }
    }
    if (!stillParsing) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }, 2000)
}

const handleFileSelect = async (e) => {
  const file = e.target.files[0]
  if (file) await uploadFile(file)
  e.target.value = '' // reset for re-upload
}

const handleDrop = async (e) => {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file && file.type === 'application/pdf') {
    await uploadFile(file)
  }
}

const uploadFile = async (file) => {
  if (selectedPdfType.value === 'answer' && !linkedPdfId.value) {
    alert('请先选择关联的题目PDF')
    return
  }
  try {
    const res = await pdfApi.upload(file, selectedPdfType.value, linkedPdfId.value)
    uploadedFiles.value.unshift({
      ...res.data,
      parse_status: 'pending',
      parse_progress: 0,
      parsed_questions: 0,
      parsed: false
    })
  } catch (e) {
    alert('上传失败: ' + (e.response?.data?.detail || e.message))
  }
}

const parsePdf = async (file) => {
  try {
    await pdfApi.parse(file.id)
    file.parse_status = 'parsing'
    file.parse_progress = 0
    startPolling()
  } catch (e) {
    alert('解析启动失败: ' + (e.response?.data?.detail || e.message))
  }
}

const deletePdf = async (file) => {
  if (!confirm('确定删除此PDF及所有关联题目？')) return
  try {
    await pdfApi.delete(file.id)
    uploadedFiles.value = uploadedFiles.value.filter(f => f.id !== file.id)
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

const formatDate = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN')
}

onMounted(loadFiles)
onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>
