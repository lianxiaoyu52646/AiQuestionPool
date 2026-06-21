import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0'
  }
})

// PDF 相关
export const pdfApi = {
  upload: (file, pdfType = 'combined', linkedPdfId = null) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('pdf_type', pdfType)
    if (linkedPdfId) {
      formData.append('linked_pdf_id', linkedPdfId)
    }
    return api.post('/pdf/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  parse: (id) => api.post(`/pdf/${id}/parse`),
  parseStatus: (id) => api.get(`/pdf/${id}/parse-status`),
  list: () => api.get('/pdf/list'),
  getFile: (id) => `/api/pdf/${id}/file`,
  delete: (id) => api.delete(`/pdf/${id}`)
}

// 题目相关
export const questionApi = {
  list: (params) => api.get('/questions/list', { params }),
  get: (id) => api.get(`/questions/${id}`),
  update: (id, data) => api.put(`/questions/${id}`, data),
  addTag: (qid, tid) => api.post(`/questions/${qid}/tags/${tid}`),
  removeTag: (qid, tid) => api.delete(`/questions/${qid}/tags/${tid}`),
  categories: () => api.get('/questions/categories/list')
}

// 学习相关
export const studyApi = {
  queue: (params) => api.get('/study/queue', { params }),
  dueCount: () => api.get('/study/due-count'),
  review: (data) => api.post('/study/review', data),
  stats: () => api.get('/study/stats'),
  statsByCategory: () => api.get('/study/stats/by-category'),
  history: (params) => api.get('/study/review-history', { params }),
  wrongQuestions: (params) => api.get('/study/wrong-questions', { params }),
  sessionSummary: (params) => api.get('/study/session-summary', { params })
}

// 标签相关
export const tagApi = {
  list: () => api.get('/tags/list'),
  create: (data) => api.post('/tags/create', data),
  delete: (id) => api.delete(`/tags/${id}`),
  initDefaults: () => api.post('/tags/init-defaults')
}

// 真题模考相关
export const examApi = {
  papers: () => api.get('/exam/papers'),
  paperDetail: (id) => api.get(`/exam/papers/${id}`),
  paperReview: (id) => api.get(`/exam/papers/${id}/review`),
  submit: (paperId, answers, timeUsedSeconds = 0) => api.post('/exam/attempts', { paper_id: paperId, answers, time_used_seconds: timeUsedSeconds }),
  attempts: (params) => api.get('/exam/attempts', { params }),
  attemptDetail: (id) => api.get(`/exam/attempts/${id}`),
  saveDraft: (paperId, answers, timeUsedSeconds, currentIndex) => api.post('/exam/drafts', { paper_id: paperId, answers, time_used_seconds: timeUsedSeconds, current_index: currentIndex }),
  getDraft: (paperId) => api.get(`/exam/drafts/${paperId}`),
  deleteDraft: (paperId) => api.delete(`/exam/drafts/${paperId}`)
}

export default api
