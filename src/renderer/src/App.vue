<template>
  <div v-if="isOverlayWindow" class="app-container transparent-bg">
    <OverlayView />
  </div>

  <div v-else class="app-container">
    <NavBar />

    <div class="main-content">
      <HomeView
        v-if="currentView === 'home'"
        :initialMode="homeInitialMode"
        @navigate="handleNavigate"
        @view-report="handleViewReport"
      />

      <SetupWizard
        v-else-if="currentView === 'setup'"
        @cancel="returnToHome('default')"
        @finished="currentView = 'scoreboard'"
      />

      <ScoreBoard
        v-else-if="currentView === 'scoreboard'"
        @stop="handleStopMatch"
      />

      <ReportView
        v-else-if="currentView === 'report'"
        :projectDir="targetProjectDir"
        @back="returnToHome('history')"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import NavBar from './components/NavBar.vue'
import HomeView from './components/HomeView.vue'
import SetupWizard from './components/SetupWizard.vue'
import ScoreBoard from './components/ScoreBoard.vue'
import OverlayView from './components/OverlayView.vue'
import ReportView from './components/ReportView.vue'
import { useRefereeStore } from './stores/refereeStore'

const currentView = ref('home')
const targetProjectDir = ref(null) // 用于传递给 ReportView
const homeInitialMode = ref('default') // 新增：控制 HomeView 初始显示状态 (default | history)
const store = useRefereeStore()

const isOverlayWindow = computed(() => {
  return new URLSearchParams(window.location.search).get('mode') === 'overlay'
})

onMounted(() => {
  store.connectWebSocket()
})

const handleNavigate = (view) => {
  currentView.value = view
}

// 处理查看报表的跳转
const handleViewReport = (dirName) => {
  targetProjectDir.value = dirName
  currentView.value = 'report'
}

const handleStopMatch = async () => {
  await store.stopMatch()
  // 停止比赛后返回默认首页
  returnToHome('default')
}

// 统一的返回首页逻辑
const returnToHome = (mode = 'default') => {
  homeInitialMode.value = mode
  currentView.value = 'home'
}
</script>

<style>
/* 全局重置 */
body { margin: 0; overflow: hidden; }

/* 默认应用背景：深灰 */
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #1e1e1e; /* 这里定义默认背景 */
  transition: background-color 0.3s;
}

/* 【关键】悬浮模式下的透明背景 */
.transparent-bg {
  background-color: transparent !important;
}
.main-content { flex: 1; position: relative; overflow: hidden; }
</style>
