<template>
  <div class="exam-page">
    <!-- 试卷选择页 -->
    <div v-if="mode === 'list'" class="exam-list-page">
      <div class="page-header">
        <h1>真题模考</h1>
        <p class="subtitle">中药学执业药师考试真题在线模拟</p>
      </div>

      <div v-if="loading" class="loading-box">
        <div class="spinner"></div>
        <span>加载中...</span>
      </div>

      <div v-else-if="papers.length === 0" class="empty-box">
        <p>暂无试卷数据</p>
      </div>

      <div v-else class="paper-grid">
        <div v-for="paper in papers" :key="paper.id" class="paper-card" @click="startExam(paper)">
          <div class="paper-card-header">
            <span class="paper-year">{{ paper.year }}</span>
            <span class="paper-badge" v-if="paper.question_count > 0">{{ paper.question_count }}题</span>
          </div>
          <h3 class="paper-title">{{ paper.title }}</h3>
          <div class="paper-meta">
            <span>⏱ {{ paper.time_limit_minutes }}分钟</span>
            <span>✅ 及格线{{ paper.pass_score }}分</span>
          </div>
          <div class="paper-stats" v-if="paper.attempt_count > 0">
            <span class="attempt-count">已考{{ paper.attempt_count }}次</span>
          </div>
          <button class="btn-start" :disabled="paper.question_count === 0">
            {{ paper.question_count > 0 ? '开始考试' : '题目准备中' }}
          </button>
        </div>
      </div>

      <!-- 历史记录 -->
      <div v-if="attempts.length > 0" class="history-section">
        <h2 class="section-title">考试记录</h2>
        <div class="attempt-list">
          <div v-for="att in paginatedAttempts" :key="att.id" class="attempt-item" @click="viewResult(att.id)">
            <div class="attempt-info">
              <span class="attempt-title">{{ att.paper_title }}</span>
              <span class="attempt-date">{{ formatDate(att.finished_at) }}</span>
            </div>
            <div class="attempt-score" :class="{ passed: att.score >= (att.pass_score || 72), failed: att.score < (att.pass_score || 72) }">
              {{ att.score }}分
            </div>
            <div class="attempt-detail">
              <span>✅{{ att.correct_count }}</span>
              <span>❌{{ att.wrong_count }}</span>
              <span>⬜{{ att.unanswered }}</span>
              <span>⏱{{ formatTime(att.time_used_seconds) }}</span>
            </div>
          </div>
        </div>
        <!-- 分页控件 -->
        <div v-if="totalPages > 1" class="pagination">
          <button class="page-btn" :disabled="currentPage === 1" @click="currentPage--">上一页</button>
          <div class="page-numbers">
            <button
              v-for="p in totalPages"
              :key="p"
              class="page-num"
              :class="{ active: p === currentPage }"
              @click="currentPage = p"
            >{{ p }}</button>
          </div>
          <button class="page-btn" :disabled="currentPage === totalPages" @click="currentPage++">下一页</button>
        </div>
      </div>
    </div>

    <!-- 考试中 -->
    <div v-else-if="mode === 'exam'" class="exam-taking-page">
      <!-- 顶部信息栏 -->
      <div class="exam-topbar">
        <div class="topbar-left">
          <button class="btn-back" @click="exitExam">← 返回</button>
          <span class="exam-title-text">{{ paper.title }}</span>
        </div>
        <div class="topbar-right">
          <div class="timer" :class="{ 'timer-warning': remainingSeconds < 300 }">
            ⏱ {{ formatTime(remainingSeconds) }}
          </div>
          <button class="btn-submit" @click="confirmSubmit">交卷</button>
        </div>
      </div>

      <div class="exam-body">
        <!-- 左侧题目区 -->
        <div class="question-area">
          <!-- 共享题干（B/C型题） -->
          <div v-if="currentQuestion.shared_stem" class="shared-stem-box">
            <div class="shared-stem-label">材料题</div>
            <div class="shared-stem-text">{{ currentQuestion.shared_stem }}</div>
          </div>

          <!-- 题目 -->
          <div class="question-box">
            <div class="question-header">
              <span class="question-num">{{ currentQuestion.question_number }}.</span>
              <span class="question-type-tag" :class="`type-${currentQuestion.question_type}`">
                {{ typeLabel(currentQuestion.question_type) }}
              </span>
              <span class="question-stem">{{ currentQuestion.stem }}</span>
            </div>

            <div class="options-list">
              <div
                v-for="(text, key) in currentQuestion.options"
                :key="key"
                class="option-item"
                :class="{
                  selected: isOptionSelected(key),
                  'multi': currentQuestion.question_type === 'X'
                }"
                @click="selectOption(key)"
              >
                <span class="option-key">{{ key }}</span>
                <span class="option-text">{{ text }}</span>
              </div>
            </div>
          </div>

          <!-- 底部导航 -->
          <div class="question-nav">
            <button class="btn-nav" :disabled="currentIndex === 0" @click="goTo(currentIndex - 1)">
              上一题
            </button>
            <button class="btn-nav btn-next" :disabled="currentIndex === questions.length - 1" @click="goTo(currentIndex + 1)">
              下一题
            </button>
          </div>
        </div>

        <!-- 右侧答题卡 -->
        <div class="answer-card">
          <div class="card-header">
            <span class="card-title">📝 答题卡</span>
            <span class="card-badge">{{ answeredCount }}/{{ questions.length }}</span>
          </div>
          <div class="card-progress-section">
            <div class="card-progress-bar">
              <div class="card-progress-fill" :style="{ width: (questions.length ? (answeredCount / questions.length * 100) : 0) + '%' }"></div>
            </div>
            <span class="card-progress-text">{{ questions.length ? Math.round(answeredCount / questions.length * 100) : 0 }}%</span>
          </div>
          <div class="card-scroll-area">
            <div class="card-grid">
              <div
                v-for="(q, idx) in questions"
                :key="q.id"
                class="card-cell"
                :class="{
                  answered: userAnswers[q.id],
                  current: idx === currentIndex
                }"
                @click="goTo(idx)"
              >
                {{ q.question_number }}
              </div>
            </div>
          </div>
          <div class="card-footer">
            <div class="card-legend">
              <span><span class="dot answered"></span>已答</span>
              <span><span class="dot"></span>未答</span>
              <span><span class="dot current"></span>当前</span>
            </div>
            <button class="btn-save-progress" @click="saveProgress" :disabled="saving">
              {{ saving ? '保存中...' : '💾 保存进度' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 考试结果 -->
    <div v-else-if="mode === 'result'" class="result-page">
      <div class="result-header">
        <div class="result-score" :class="{ passed: result.passed, failed: !result.passed }">
          <span class="score-num">{{ result.score }}</span>
          <span class="score-unit">分</span>
        </div>
        <div class="result-status">
          {{ result.passed ? '🎉 恭喜通过！' : '😔 未通过' }}
        </div>
        <div class="result-meta">
          及格线: {{ result.pass_score }}分 | 总题数: {{ result.total_questions }} | 用时: {{ formatTime(result.time_used_seconds) }}
        </div>
      </div>

      <div class="result-summary">
        <div class="summary-item correct">
          <span class="summary-num">{{ result.correct_count }}</span>
          <span class="summary-label">答对</span>
        </div>
        <div class="summary-item wrong">
          <span class="summary-num">{{ result.wrong_count }}</span>
          <span class="summary-label">答错</span>
        </div>
        <div class="summary-item unanswered">
          <span class="summary-num">{{ result.unanswered }}</span>
          <span class="summary-label">未答</span>
        </div>
      </div>

      <!-- 答题详情 -->
      <div class="answer-detail-list">
        <div class="detail-header">答题详情</div>
        <div
          v-for="ans in result.answers"
          :key="ans.question_id"
          class="answer-detail-item"
          :class="{ correct: ans.is_correct === true, wrong: ans.is_correct === false && ans.user_answer, unanswered: !ans.user_answer }"
        >
          <div v-if="ans.shared_stem" class="detail-shared-stem">{{ ans.shared_stem }}</div>
          <div class="detail-question">
            <span class="detail-num">{{ ans.question_number }}.</span>
            <span class="detail-type" :class="`type-${ans.question_type}`">{{ typeLabel(ans.question_type) }}</span>
            <span class="detail-stem">{{ ans.stem }}</span>
          </div>
          <div class="detail-options">
            <div
              v-for="(text, key) in ans.options"
              :key="key"
              class="detail-option"
              :class="{
                'correct-answer': ans.correct_answer.includes(key),
                'user-correct': ans.user_answer.includes(key) && ans.correct_answer.includes(key),
                'user-wrong': ans.user_answer.includes(key) && !ans.correct_answer.includes(key)
              }"
            >
              <span class="option-key">{{ key }}</span>
              <span>{{ text }}</span>
            </div>
          </div>
          <div class="detail-answer-row">
            <span class="detail-label">正确答案: <strong class="correct-text">{{ ans.correct_answer }}</strong></span>
            <span class="detail-label">你的答案: <strong :class="ans.is_correct ? 'correct-text' : 'wrong-text'">{{ ans.user_answer || '未作答' }}</strong></span>
          </div>
          <div v-if="ans.explanation" class="detail-explanation">
            <span class="exp-label">解析:</span>
            <span class="exp-text">{{ ans.explanation }}</span>
          </div>
        </div>
      </div>

      <div class="result-actions">
        <button class="btn-action" @click="backToList">返回列表</button>
        <button class="btn-action btn-retry" @click="retryExam">再考一次</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { examApi } from '../api'

const mode = ref('list') // list | exam | result
const loading = ref(false)
const papers = ref([])
const attempts = ref([])
const currentPage = ref(1)
const pageSize = 5
const paper = ref(null)
const questions = ref([])
const currentIndex = ref(0)
const userAnswers = ref({}) // { question_id: "A" or "ABCDE" }
const result = ref(null)
const remainingSeconds = ref(0)
const examStartTime = ref(null) // 记录考试开始时间
const saving = ref(false) // 保存进度中
let timer = null

const totalPages = computed(() => Math.ceil(attempts.value.length / pageSize))
const paginatedAttempts = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return attempts.value.slice(start, start + pageSize)
})

const currentQuestion = computed(() => questions.value[currentIndex.value] || {})
const answeredCount = computed(() => {
  return Object.values(userAnswers.value).filter(v => v).length
})

onMounted(() => {
  loadPapers()
  loadAttempts()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function loadPapers() {
  loading.value = true
  try {
    const res = await examApi.papers()
    papers.value = res.data
  } catch (e) {
    console.error('加载试卷失败', e)
  }
  loading.value = false
}

async function loadAttempts() {
  try {
    const res = await examApi.attempts({ limit: 100 })
    attempts.value = res.data
    currentPage.value = 1
  } catch (e) {
    console.error('加载记录失败', e)
  }
}

async function startExam(p) {
  try {
    const res = await examApi.paperDetail(p.id)
    paper.value = p
    questions.value = res.data.questions
    userAnswers.value = {}
    currentIndex.value = 0
    remainingSeconds.value = p.time_limit_minutes * 60
    examStartTime.value = Date.now()

    // 检查是否有未完成的草稿
    try {
      const draftRes = await examApi.getDraft(p.id)
      if (draftRes.data && draftRes.data.answers && draftRes.data.answers.length > 0) {
        const hasDraft = await new Promise(resolve => {
          // 恢复草稿到 userAnswers
          for (const a of draftRes.data.answers) {
            userAnswers.value[a.question_id] = a.user_answer
          }
          // 恢复已用时间
          if (draftRes.data.time_used_seconds > 0) {
            remainingSeconds.value = Math.max(0, p.time_limit_minutes * 60 - draftRes.data.time_used_seconds)
            examStartTime.value = Date.now() - draftRes.data.time_used_seconds * 1000
          }
          if (draftRes.data.current_index > 0) {
            currentIndex.value = draftRes.data.current_index
          }
          resolve(true)
        })
        if (hasDraft) {
          // 提示用户已恢复草稿
          setTimeout(() => {
            alert(`已恢复上次未完成的答题进度（已答${draftRes.data.answers.length}题）`)
          }, 500)
        }
      }
    } catch (draftErr) {
      console.error('检查草稿失败', draftErr)
    }

    mode.value = 'exam'
    startTimer()
  } catch (e) {
    console.error('加载试卷详情失败', e)
  }
}

function startTimer() {
  if (timer) clearInterval(timer)
  timer = setInterval(() => {
    remainingSeconds.value--
    if (remainingSeconds.value <= 0) {
      clearInterval(timer)
      remainingSeconds.value = 0
      // 时间到，提示后自动交卷
      alert('⏰ 考试时间已到，系统将自动交卷！')
      submitExam()
    }
  }, 1000)
}

function isOptionSelected(key) {
  const ans = userAnswers.value[currentQuestion.value.id]
  if (!ans) return false
  return ans.includes(key)
}

function selectOption(key) {
  const q = currentQuestion.value
  if (q.question_type === 'X') {
    // 多选题：切换选择
    let current = userAnswers.value[q.id] || ''
    if (current.includes(key)) {
      current = current.replace(key, '')
    } else {
      current += key
      current = current.split('').sort().join('')
    }
    userAnswers.value[q.id] = current
  } else {
    // 单选题
    userAnswers.value[q.id] = key
  }
}

function goTo(index) {
  if (index >= 0 && index < questions.value.length) {
    currentIndex.value = index
  }
}

async function saveProgress() {
  if (!paper.value || saving.value) return
  saving.value = true
  const timeUsed = examStartTime.value
    ? Math.floor((Date.now() - examStartTime.value) / 1000)
    : 0
  const answers = questions.value.map(q => ({
    question_id: q.id,
    user_answer: userAnswers.value[q.id] || ''
  }))
  try {
    await examApi.saveDraft(paper.value.id, answers, timeUsed, currentIndex.value)
    alert(`进度已保存！已答${answeredCount.value}/${questions.value.length}题，下次进入可继续答题。`)
  } catch (e) {
    console.error('保存进度失败', e)
    alert('保存进度失败，请重试')
  } finally {
    saving.value = false
  }
}

async function exitExam() {
  const answered = answeredCount.value
  const total = questions.value.length
  const msg = answered > 0
    ? `确定要退出考试吗？已答${answered}/${total}题。\n\n点击「确定」将保存进度并退出，\n下次进入可继续答题。\n点击「取消」继续考试。`
    : '确定要退出考试吗？'
  if (confirm(msg)) {
    if (timer) clearInterval(timer)
    // 保存草稿
    if (answered > 0 && paper.value) {
      const timeUsed = examStartTime.value
        ? Math.floor((Date.now() - examStartTime.value) / 1000)
        : 0
      const answers = questions.value.map(q => ({
        question_id: q.id,
        user_answer: userAnswers.value[q.id] || ''
      }))
      try {
        await examApi.saveDraft(paper.value.id, answers, timeUsed, currentIndex.value)
      } catch (e) {
        console.error('保存草稿失败', e)
      }
    }
    mode.value = 'list'
    loadPapers()
    loadAttempts()
  }
}

function confirmSubmit() {
  const unanswered = questions.value.length - answeredCount.value
  const msg = unanswered > 0
    ? `还有${unanswered}题未作答，确定要交卷吗？`
    : '确定要交卷吗？'
  if (confirm(msg)) {
    submitExam()
  }
}

async function submitExam() {
  if (timer) clearInterval(timer)
  // 计算实际用时
  const timeUsed = examStartTime.value
    ? Math.floor((Date.now() - examStartTime.value) / 1000)
    : 0
  const answers = questions.value.map(q => ({
    question_id: q.id,
    user_answer: userAnswers.value[q.id] || ''
  }))
  try {
    const res = await examApi.submit(paper.value.id, answers, timeUsed)
    result.value = res.data
    mode.value = 'result'
    // 提交成功后删除草稿
    try {
      await examApi.deleteDraft(paper.value.id)
    } catch (e) {
      // 忽略草稿删除失败
    }
    await loadAttempts() // 刷新考试记录
  } catch (e) {
    console.error('提交失败', e)
    alert('提交失败，请重试')
  }
}

async function viewResult(attemptId) {
  try {
    const res = await examApi.attemptDetail(attemptId)
    result.value = res.data
    mode.value = 'result'
  } catch (e) {
    console.error('加载记录失败', e)
  }
}

function backToList() {
  mode.value = 'list'
  loadPapers()
  loadAttempts()
}

function retryExam() {
  if (paper.value) {
    startExam(paper.value)
  } else {
    backToList()
  }
}

function typeLabel(type) {
  const labels = { A: 'A型题', B: 'B型题', C: 'C型题', X: 'X型题' }
  return labels[type] || type
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<style scoped>
.exam-page {
  min-height: 100vh;
  background:
    radial-gradient(ellipse at 20% 0%, rgba(24,144,255,0.06) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 100%, rgba(24,144,255,0.04) 0%, transparent 50%),
    linear-gradient(180deg, #f0f5ff 0%, #f5f7fa 40%, #f5f7fa 100%);
}

/* ===== 试卷列表页 ===== */
.exam-list-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 28px 24px;
}

.page-header {
  text-align: center;
  margin-bottom: 24px;
  padding: 24px 20px;
  background:
    radial-gradient(ellipse at 30% 0%, rgba(255,255,255,0.15) 0%, transparent 60%),
    linear-gradient(135deg, #1890ff 0%, #096dd9 50%, #0050b3 100%);
  border-radius: 16px;
  color: #fff;
  position: relative;
  overflow: hidden;
  box-shadow:
    0 6px 20px rgba(24,144,255,0.2),
    inset 0 1px 0 rgba(255,255,255,0.2);
}

.page-header::before {
  content: '';
  position: absolute;
  top: -40px;
  right: -40px;
  width: 160px;
  height: 160px;
  background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
  border-radius: 50%;
}

.page-header::after {
  content: '';
  position: absolute;
  bottom: -50px;
  left: -30px;
  width: 130px;
  height: 130px;
  background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
  border-radius: 50%;
}

.page-header h1 {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 4px;
  letter-spacing: 2px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.15);
  position: relative;
  z-index: 1;
}

.subtitle {
  color: rgba(255,255,255,0.9);
  font-size: 13px;
  letter-spacing: 0.5px;
  position: relative;
  z-index: 1;
}

.loading-box, .empty-box {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e8e8e8;
  border-top-color: #1890ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.paper-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}

.paper-card {
  background: rgba(255,255,255,0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 26px;
  box-shadow:
    0 4px 20px rgba(24,144,255,0.06),
    0 1px 3px rgba(0,0,0,0.04);
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(232,232,232,0.8);
  position: relative;
  overflow: hidden;
}

.paper-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #1890ff 0%, #40a9ff 50%, #69c0ff 100%);
  opacity: 0.9;
}

.paper-card::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(24,144,255,0.03) 0%, transparent 60%);
  opacity: 0;
  transition: opacity 0.35s;
  pointer-events: none;
}

.paper-card:hover {
  box-shadow:
    0 12px 36px rgba(24,144,255,0.15),
    0 4px 12px rgba(24,144,255,0.08);
  transform: translateY(-6px);
  border-color: rgba(145,213,255,0.6);
}

.paper-card:hover::after {
  opacity: 1;
}

.paper-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.paper-year {
  font-size: 24px;
  font-weight: 800;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.paper-badge {
  background: linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%);
  color: #096dd9;
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid rgba(24,144,255,0.15);
}

.paper-title {
  font-size: 15px;
  color: #333;
  margin: 0 0 12px;
  line-height: 1.5;
}

.paper-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #888;
  margin-bottom: 12px;
}

.paper-stats {
  margin-bottom: 16px;
}

.attempt-count {
  font-size: 12px;
  color: #999;
}

.btn-start {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
  letter-spacing: 2px;
  box-shadow: 0 4px 12px rgba(24,144,255,0.25);
  position: relative;
  overflow: hidden;
}

.btn-start::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
  transition: left 0.5s;
}

.btn-start:hover:not(:disabled)::before {
  left: 100%;
}

.btn-start:hover:not(:disabled) {
  background: linear-gradient(135deg, #40a9ff 0%, #1890ff 100%);
  box-shadow: 0 4px 12px rgba(24,144,255,0.3);
}

.btn-start:disabled {
  background: #d9d9d9;
  cursor: not-allowed;
}

/* 历史记录 */
.history-section {
  margin-top: 40px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #333;
  margin: 0 0 16px;
}

.attempt-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attempt-item {
  display: flex;
  align-items: center;
  gap: 16px;
  background: rgba(255,255,255,0.9);
  backdrop-filter: blur(8px);
  padding: 16px 22px;
  border-radius: 12px;
  border: 1px solid rgba(232,232,232,0.6);
  cursor: pointer;
  transition: all 0.25s;
}

.attempt-item:hover {
  border-color: #91d5ff;
  box-shadow: 0 4px 16px rgba(24,144,255,0.1);
  transform: translateX(4px);
}

.attempt-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.attempt-title {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

.attempt-date {
  font-size: 12px;
  color: #999;
}

.attempt-score {
  font-size: 20px;
  font-weight: 700;
  min-width: 60px;
  text-align: right;
}

.attempt-score.passed { color: #10b981; }
.attempt-score.failed { color: #ef4444; }

.attempt-detail {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #888;
}

/* 分页控件 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
}

.page-btn {
  padding: 6px 16px;
  border-radius: 8px;
  border: 1px solid #d9d9d9;
  background: #fff;
  color: #333;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  border-color: #1890ff;
  color: #1890ff;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-numbers {
  display: flex;
  gap: 6px;
}

.page-num {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid #d9d9d9;
  background: #fff;
  color: #333;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.page-num:hover {
  border-color: #1890ff;
  color: #1890ff;
}

.page-num.active {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  border-color: #1890ff;
  color: #fff;
  box-shadow: 0 2px 8px rgba(24,144,255,0.3);
}

/* ===== 考试中页面 ===== */
.exam-taking-page {
  height: 100vh;
  overflow: hidden;
  background: linear-gradient(180deg, #f0f5ff 0%, #f5f7fa 100%);
  display: flex;
  flex-direction: column;
}

.exam-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 28px;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 2px 20px rgba(24,144,255,0.08);
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid rgba(24,144,255,0.12);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.btn-back {
  padding: 7px 16px;
  background: #f0f5ff;
  border: 1px solid #adc6ff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #1890ff;
  transition: all 0.2s;
}

.btn-back:hover {
  background: #1890ff;
  color: #fff;
  border-color: #1890ff;
}

.exam-title-text {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.timer {
  font-size: 18px;
  font-weight: 700;
  color: #096dd9;
  font-family: 'Courier New', monospace;
  background: linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%);
  padding: 6px 16px;
  border-radius: 10px;
  border: 1px solid rgba(24,144,255,0.15);
  box-shadow: 0 2px 8px rgba(24,144,255,0.1);
}

.timer-warning {
  color: #ef4444;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  50% { opacity: 0.6; }
}

.btn-submit {
  padding: 9px 26px;
  background: linear-gradient(135deg, #ff4d4f 0%, #cf1322 100%);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.25s;
  box-shadow: 0 4px 12px rgba(255,77,79,0.25);
}

.btn-submit:hover {
  box-shadow: 0 4px 12px rgba(255,77,79,0.3);
}

.exam-body {
  display: flex;
  gap: 24px;
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 24px;
  flex: 1;
  width: 100%;
  height: calc(100vh - 60px);
  overflow: hidden;
}

.question-area {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding-right: 8px;
}

.shared-stem-box {
  background: linear-gradient(135deg, #fffbe6 0%, #fff7e6 100%);
  border: 1px solid #ffe58f;
  border-left: 4px solid #faad14;
  border-radius: 8px;
  padding: 18px 22px;
  margin-bottom: 16px;
}

.shared-stem-label {
  font-size: 12px;
  font-weight: 700;
  color: #d48806;
  margin-bottom: 8px;
  display: inline-block;
  background: #faad14;
  color: #fff;
  padding: 2px 10px;
  border-radius: 4px;
}

.shared-stem-text {
  font-size: 14px;
  color: #555;
  line-height: 1.8;
}

.question-box {
  background: rgba(255,255,255,0.98);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 30px;
  box-shadow:
    0 4px 24px rgba(24,144,255,0.06),
    0 1px 4px rgba(0,0,0,0.03);
  border: 1px solid rgba(24,144,255,0.06);
}

.question-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.question-num {
  font-size: 17px;
  font-weight: 700;
  color: #1890ff;
}

.question-type-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.type-A { background: #dbeafe; color: #2563eb; }
.type-B { background: #dcfce7; color: #16a34a; }
.type-C { background: #fef3c7; color: #d97706; }
.type-X { background: #fce7f3; color: #db2777; }

.question-stem {
  font-size: 15px;
  color: #333;
  line-height: 1.7;
  flex: 1;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border: 2px solid #eaeaea;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: rgba(250,251,252,0.8);
}

.option-item:hover {
  border-color: #91d5ff;
  background: linear-gradient(135deg, #f0f8ff 0%, #e6f7ff 100%);
  transform: translateX(6px);
  box-shadow: 0 2px 12px rgba(24,144,255,0.08);
}

.option-item.selected {
  border-color: #1890ff;
  background: linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%);
  box-shadow: 0 4px 16px rgba(24,144,255,0.12);
}

.option-key {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%);
  font-weight: 700;
  font-size: 14px;
  color: #666;
  flex-shrink: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.option-item:hover .option-key {
  background: linear-gradient(135deg, #91d5ff 0%, #69c0ff 100%);
  color: #fff;
}

.option-item.selected .option-key {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(24,144,255,0.4);
  transform: scale(1.1);
}

.option-text {
  font-size: 14px;
  color: #333;
  line-height: 1.5;
}

.question-nav {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

.btn-nav {
  padding: 10px 24px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  cursor: pointer;
  color: #666;
}

.btn-nav:hover:not(:disabled) {
  border-color: #1890ff;
  color: #1890ff;
}

.btn-nav:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-next {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  color: #fff;
  border-color: #096dd9;
  box-shadow: 0 4px 12px rgba(24,144,255,0.2);
}

.btn-next:hover:not(:disabled) {
  background: linear-gradient(135deg, #40a9ff 0%, #1890ff 100%);
  box-shadow: 0 4px 10px rgba(24,144,255,0.3);
}

/* 答题卡 */
.answer-card {
  width: 340px;
  flex-shrink: 0;
  background: rgba(255,255,255,0.98);
  backdrop-filter: blur(12px);
  border-radius: 16px;
  padding: 16px;
  box-shadow:
    0 10px 40px rgba(0,0,0,0.08),
    0 2px 12px rgba(24,144,255,0.06);
  height: calc(100vh - 320px);
  align-self: flex-start;
  overflow: hidden;
  border: 1px solid rgba(24,144,255,0.1);
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: 10px;
  margin-bottom: 12px;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  box-shadow: 0 4px 16px rgba(24,144,255,0.3);
  flex-shrink: 0;
}

.card-title {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
}

.card-badge {
  background: rgba(255,255,255,0.25);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 20px;
  backdrop-filter: blur(4px);
}

.card-progress-section {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.card-progress-bar {
  flex: 1;
  height: 6px;
  background: #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
}

.card-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1890ff 0%, #40a9ff 100%);
  border-radius: 4px;
  transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.card-progress-text {
  font-size: 12px;
  font-weight: 600;
  color: #1890ff;
  min-width: 32px;
  text-align: right;
}

.card-scroll-area {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-right: 4px;
  margin-right: -4px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}

.card-cell {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #d9d9d9;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  color: #666;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  background: #fff;
  user-select: none;
}

.card-cell:hover {
  border-color: #1890ff;
  color: #1890ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(24,144,255,0.2);
}

.card-cell.answered {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  color: #fff;
  border-color: #096dd9;
  box-shadow: 0 2px 8px rgba(24,144,255,0.3);
}

.card-cell.answered:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(24,144,255,0.45);
}

.card-cell.current {
  border: 2.5px solid #faad14;
  font-weight: 700;
  box-shadow: 0 0 0 3px rgba(250,173,20,0.2);
  background: linear-gradient(135deg, #fffbe6 0%, #fff7e6 100%);
  color: #d48806;
}

.card-cell.current.answered {
  border: 2.5px solid #faad14;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  color: #fff;
}

.card-footer {
  flex-shrink: 0;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
  margin-top: 8px;
}

.card-legend {
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: #888;
  margin-bottom: 10px;
  justify-content: center;
}

.dot {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1.5px solid #d9d9d9;
  margin-right: 4px;
  vertical-align: middle;
  background: #fff;
}

.dot.answered {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  border-color: #096dd9;
}

.dot.current {
  border: 2px solid #faad14;
  background: linear-gradient(135deg, #fffbe6 0%, #fff7e6 100%);
}

.btn-save-progress {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(135deg, #52c41a 0%, #389e0d 100%);
  box-shadow: 0 4px 12px rgba(82,196,26,0.3);
  transition: all 0.25s ease;
}

.btn-save-progress:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(82,196,26,0.4);
}

.btn-save-progress:active:not(:disabled) {
  transform: translateY(0);
}

.btn-save-progress:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ===== 结果页 ===== */
.result-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 20px;
  background: linear-gradient(180deg, #f0f5ff 0%, #f5f7fa 100%);
  min-height: 100vh;
}

.result-header {
  text-align: center;
  background:
    radial-gradient(ellipse at 30% 0%, rgba(255,255,255,0.15) 0%, transparent 60%),
    linear-gradient(135deg, #1890ff 0%, #096dd9 50%, #0050b3 100%);
  border-radius: 24px;
  padding: 52px 20px;
  margin-bottom: 20px;
  box-shadow:
    0 12px 40px rgba(24,144,255,0.25),
    0 4px 12px rgba(0,80,179,0.12),
    inset 0 1px 0 rgba(255,255,255,0.2);
  color: #fff;
  position: relative;
  overflow: hidden;
}

.result-header::before {
  content: '';
  position: absolute;
  top: -70px;
  right: -70px;
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
  border-radius: 50%;
}

.result-header::after {
  content: '';
  position: absolute;
  bottom: -90px;
  left: -50px;
  width: 220px;
  height: 220px;
  background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
  border-radius: 50%;
}

.result-score {
  font-size: 60px;
  font-weight: 800;
  margin-bottom: 8px;
  text-shadow: 0 4px 16px rgba(0,0,0,0.15);
  position: relative;
  z-index: 1;
}

.result-score.passed { color: #fff; }
.result-score.failed { color: #fff; }

.score-unit {
  font-size: 22px;
  margin-left: 4px;
}

.result-status {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 10px;
  color: #fff;
  position: relative;
  z-index: 1;
}

.result-meta {
  font-size: 14px;
  color: rgba(255,255,255,0.85);
  position: relative;
  z-index: 1;
}

.result-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.summary-item {
  flex: 1;
  text-align: center;
  background: rgba(255,255,255,0.98);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 26px;
  box-shadow:
    0 4px 20px rgba(0,0,0,0.04),
    0 1px 4px rgba(0,0,0,0.02);
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  border-top: 3px solid transparent;
}

.summary-item:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.08);
}

.summary-item.correct { border-top-color: #52c41a; }
.summary-item.wrong { border-top-color: #ff4d4f; }
.summary-item.unanswered { border-top-color: #bfbfbf; }

.summary-num {
  display: block;
  font-size: 28px;
  font-weight: 700;
}

.summary-label {
  font-size: 13px;
  color: #888;
}

.summary-item.correct .summary-num { color: #52c41a; }
.summary-item.wrong .summary-num { color: #ff4d4f; }
.summary-item.unanswered .summary-num { color: #bfbfbf; }

/* 答题详情 */
.answer-detail-list {
  background: rgba(255,255,255,0.98);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 26px;
  box-shadow:
    0 4px 24px rgba(24,144,255,0.06),
    0 1px 4px rgba(0,0,0,0.03);
  border: 1px solid rgba(24,144,255,0.06);
}

.detail-header {
  font-size: 17px;
  font-weight: 700;
  color: #1890ff;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 2px solid #e6f7ff;
}

.answer-detail-item {
  padding: 16px 0;
  border-bottom: 1px solid #f0f0f0;
}

.answer-detail-item:last-child {
  border-bottom: none;
}

.detail-shared-stem {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #555;
  line-height: 1.6;
}

.detail-question {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.detail-num {
  font-weight: 700;
  color: #333;
}

.detail-type {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}

.detail-stem {
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  flex: 1;
}

.detail-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.detail-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 13px;
}

.detail-option.correct-answer {
  background: #f6ffed;
  color: #389e0d;
  border: 1px solid #b7eb8f;
}

.detail-option.user-correct {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.detail-option.user-wrong {
  background: #fff2f0;
  color: #cf1322;
  border: 1px solid #ffccc7;
}

.detail-answer-row {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.correct-text { color: #52c41a; }
.wrong-text { color: #ff4d4f; }

.detail-explanation {
  background: #f0f8ff;
  border-left: 3px solid #1890ff;
  border-radius: 6px;
  padding: 12px 16px;
  font-size: 13px;
  color: #555;
  line-height: 1.7;
}

.exp-label {
  font-weight: 600;
  color: #1890ff;
  margin-right: 4px;
}

.result-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-top: 24px;
}

.btn-action {
  padding: 10px 32px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  color: #666;
}

.btn-action:hover {
  border-color: #1890ff;
  color: #1890ff;
}

.btn-retry {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  color: #fff;
  border-color: #1890ff;
}

.btn-retry:hover {
  background: linear-gradient(135deg, #40a9ff 0%, #1890ff 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(24,144,255,0.3);
}

/* 响应式 */
@media (max-width: 768px) {
  .exam-body {
    flex-direction: column;
    height: auto;
    overflow: visible;
  }
  .answer-card {
    width: 100%;
    position: static;
    height: auto;
    max-height: 400px;
  }
  .question-area {
    overflow-y: visible;
  }
  .paper-grid {
    grid-template-columns: 1fr;
  }
  .result-summary {
    flex-direction: column;
  }
}
</style>
