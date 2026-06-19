<template>
  <div class="space-y-8">
    <!-- 欢迎区 -->
    <div class="text-center py-12">
      <h1 class="text-4xl font-bold text-gray-900 mb-4">
        📚 智能题库系统
      </h1>
      <p class="text-lg text-gray-600 max-w-2xl mx-auto">
        上传PDF电子书，AI自动提取题目，基于 FSRS 间隔重复算法智能推送，
        让学习更高效
      </p>
      <div class="mt-8 space-x-4">
        <router-link to="/upload" class="btn-primary text-lg px-8 py-3">
          📤 上传PDF
        </router-link>
        <router-link to="/study" class="btn-success text-lg px-8 py-3">
          ✍️ 开始学习
        </router-link>
      </div>
    </div>

    <!-- 今日概览卡片 -->
    <div v-if="stats" class="grid grid-cols-1 md:grid-cols-4 gap-6">
      <div class="card text-center">
        <div class="text-3xl font-bold text-primary">{{ stats.total_questions }}</div>
        <div class="text-sm text-gray-500 mt-1">总题数</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-success">{{ stats.mastered }}</div>
        <div class="text-sm text-gray-500 mt-1">已掌握</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-warning">{{ dueCount.due_today }}</div>
        <div class="text-sm text-gray-500 mt-1">今日待复习</div>
      </div>
      <div class="card text-center">
        <div class="text-3xl font-bold text-danger">{{ dueCount.new_questions }}</div>
        <div class="text-sm text-gray-500 mt-1">新题待学</div>
      </div>
    </div>

    <!-- 学习进度 -->
    <div v-if="categoryStats.length > 0" class="card">
      <h2 class="text-xl font-bold mb-6">📈 分类学习进度</h2>
      <div class="space-y-4">
        <div
          v-for="cat in categoryStats"
          :key="cat.id"
          class="flex items-center space-x-4"
        >
          <div class="w-32 text-sm font-medium truncate">{{ cat.name }}</div>
          <div class="flex-1">
            <div class="w-full bg-gray-200 rounded-full h-2.5">
              <div
                class="bg-primary h-2.5 rounded-full transition-all duration-500"
                :style="{ width: cat.progress_rate + '%' }"
              ></div>
            </div>
          </div>
          <div class="w-20 text-sm text-gray-600 text-right">
            {{ cat.learned }}/{{ cat.total }}
          </div>
        </div>
      </div>
    </div>

    <!-- 快速操作 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <router-link to="/upload" class="card hover:shadow-md transition-shadow cursor-pointer">
        <div class="text-4xl mb-4">📤</div>
        <h3 class="text-lg font-bold mb-2">上传PDF</h3>
        <p class="text-gray-600 text-sm">上传电子书，AI自动提取题目并分类</p>
      </router-link>
      <router-link to="/study" class="card hover:shadow-md transition-shadow cursor-pointer">
        <div class="text-4xl mb-4">✍️</div>
        <h3 class="text-lg font-bold mb-2">智能刷题</h3>
        <p class="text-gray-600 text-sm">FSRS算法智能推送，优先复习薄弱知识点</p>
      </router-link>
      <router-link to="/stats" class="card hover:shadow-md transition-shadow cursor-pointer">
        <div class="text-4xl mb-4">📊</div>
        <h3 class="text-lg font-bold mb-2">学习统计</h3>
        <p class="text-gray-600 text-sm">查看学习进度、遗忘曲线和掌握程度</p>
      </router-link>
    </div>

    <!-- 最近上传 -->
    <div v-if="pdfList.length > 0" class="card">
      <h2 class="text-xl font-bold mb-4">📄 最近上传</h2>
      <div class="space-y-2">
        <div
          v-for="pdf in pdfList.slice(0, 5)"
          :key="pdf.id"
          class="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
        >
          <div class="flex items-center space-x-3">
            <span class="text-2xl">📑</span>
            <div>
              <div class="font-medium">{{ pdf.filename }}</div>
              <div class="text-sm text-gray-500">
                {{ pdf.total_pages }}页 | {{ pdf.question_count }}题
              </div>
            </div>
          </div>
          <router-link
            :to="`/pdf-view/${pdf.id}`"
            class="text-primary hover:underline text-sm"
          >
            查看PDF
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { pdfApi, studyApi } from '../api'

const stats = ref(null)
const dueCount = ref({ due_today: 0, new_questions: 0 })
const categoryStats = ref([])
const pdfList = ref([])

onMounted(async () => {
  try {
    const [statsRes, dueRes, catRes, pdfRes] = await Promise.all([
      studyApi.stats(),
      studyApi.dueCount(),
      studyApi.statsByCategory(),
      pdfApi.list()
    ])
    stats.value = statsRes.data
    dueCount.value = dueRes.data
    categoryStats.value = catRes.data
    pdfList.value = pdfRes.data
  } catch (e) {
    console.error('加载数据失败:', e)
  }
})
</script>
