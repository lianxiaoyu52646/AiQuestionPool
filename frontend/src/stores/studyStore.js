import { defineStore } from 'pinia'
import { ref } from 'vue'
import { studyApi } from '../api'

export const useStudyStore = defineStore('study', () => {
  // 统计数据版本号：每次答题后递增，Stats/Home页面watch此值来刷新
  const statsVersion = ref(0)

  // 缓存的统计数据
  const cachedStats = ref(null)
  const cachedDueCount = ref({ due_today: 0, new_questions: 0 })

  // 递增版本号，通知所有页面刷新统计
  const bumpStatsVersion = () => {
    // 清除缓存，确保下次加载拿到最新数据
    cachedStats.value = null
    cachedDueCount.value = { due_today: 0, new_questions: 0 }
    statsVersion.value++
  }

  // 加载统计数据（带缓存）
  const loadStats = async (force = false) => {
    if (!force && cachedStats.value) return cachedStats.value
    try {
      const res = await studyApi.stats()
      cachedStats.value = res.data
      return res.data
    } catch (e) {
      console.error('加载统计数据失败:', e)
      return null
    }
  }

  // 加载待复习数量
  const loadDueCount = async (force = false) => {
    if (!force && cachedDueCount.value.due_today !== 0) return cachedDueCount.value
    try {
      const res = await studyApi.dueCount()
      cachedDueCount.value = res.data
      return res.data
    } catch (e) {
      console.error('加载待复习数量失败:', e)
      return { due_today: 0, new_questions: 0 }
    }
  }

  return {
    statsVersion,
    cachedStats,
    cachedDueCount,
    bumpStatsVersion,
    loadStats,
    loadDueCount
  }
})
