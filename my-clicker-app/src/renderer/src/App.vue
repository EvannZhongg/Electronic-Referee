<template>
  <div class="app-container" :class="{ 'transparent-bg': isOverlayMode }">
    <NavBar v-if="!isOverlayMode" />

    <div class="main-content">
      <HomeView v-if="currentView === 'home'" @navigate="handleNavigate" />
      <SetupWizard v-else-if="currentView === 'setup'" @cancel="currentView = 'home'" @finished="currentView = 'scoreboard'" />

      <ScoreBoard
        v-else-if="currentView === 'scoreboard'"
        @stop="handleStopMatch"
        @overlay-change="(val) => isOverlayMode = val"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import NavBar from './components/NavBar.vue'
import HomeView from './components/HomeView.vue'
import SetupWizard from './components/SetupWizard.vue'
import ScoreBoard from './components/ScoreBoard.vue'
import { useRefereeStore } from './stores/refereeStore'

const currentView = ref('home')
const store = useRefereeStore()
const isOverlayMode = ref(false) // 新增状态控制背景

onMounted(() => {
  store.connectWebSocket()
})

const handleNavigate = (view) => {
  currentView.value = view
}

const handleStopMatch = async () => {
  await store.stopMatch()
  currentView.value = 'home'
  isOverlayMode.value = false // 退出时重置
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
.app-container.transparent-bg {
  background-color: transparent !important;
}

.main-content { flex: 1; position: relative; overflow: hidden; }
</style>
