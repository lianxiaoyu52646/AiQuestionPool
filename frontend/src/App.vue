<template>
  <div class="min-h-screen flex flex-col">
    <!-- 导航栏 -->
    <nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <router-link to="/" class="flex items-center space-x-2">
              <span class="text-2xl">📚</span>
              <span class="text-xl font-bold text-gray-900">智能题库</span>
            </router-link>
          </div>
          <div class="flex items-center space-x-1">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              :class="[
                'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                $route.path === item.path
                  ? 'bg-blue-50 text-primary'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              ]"
            >
              <span class="mr-1">{{ item.icon }}</span>
              {{ item.name }}
            </router-link>
          </div>
        </div>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 页脚 -->
    <footer class="bg-white border-t border-gray-200 mt-auto">
      <div class="max-w-7xl mx-auto px-4 py-4 text-center text-sm text-gray-500">
        智能题库系统 - 基于 FSRS 间隔重复算法
      </div>
    </footer>
  </div>
</template>

<script setup>
const navItems = [
  { path: '/', name: '首页', icon: '🏠' },
  { path: '/upload', name: '上传PDF', icon: '📤' },
  { path: '/questions', name: '题库', icon: '📝' },
  { path: '/exam', name: '真题模考', icon: '✍️' },
  { path: '/stats', name: '统计', icon: '📊' },
]
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
