import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('./views/Home.vue')
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('./views/Upload.vue')
  },
  {
    path: '/questions',
    name: 'Questions',
    component: () => import('./views/Questions.vue')
  },
  {
    path: '/stats',
    name: 'Stats',
    component: () => import('./views/Stats.vue')
  },
  {
    path: '/pdf-view/:id',
    name: 'PDFView',
    component: () => import('./views/PDFView.vue')
  },
  {
    path: '/exam',
    name: 'Exam',
    component: () => import('./views/Exam.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
