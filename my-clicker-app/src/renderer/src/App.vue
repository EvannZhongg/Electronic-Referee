<template>
  <div class="app-container">
    <NavBar />

    <div class="main-content">
      <HomeView
        v-if="currentView === 'home'"
        @navigate="handleNavigate"
      />

      <SetupWizard
        v-else-if="currentView === 'setup'"
        @cancel="currentView = 'home'"
        @finished="currentView = 'scoreboard'"
      />

      <ScoreBoard
        v-else-if="currentView === 'scoreboard'"
        @stop="handleStopMatch"
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

// 【关键修复】应用启动时立即建立 WebSocket 连接
// 这样在 SetupWizard 页面也能收到 "Connected" 状态更新
onMounted(() => {
  console.log("App mounted, connecting to backend...")
  store.connectWebSocket()
})

const handleNavigate = (view) => {
  currentView.value = view
}

const handleStopMatch = async () => {
  await store.stopMatch()
  currentView.value = 'home'
}
</script>

<style>
body { margin: 0; font-family: 'Segoe UI', sans-serif; background: #1e1e1e; overflow: hidden; }
.app-container { display: flex; flex-direction: column; height: 100vh; }
.main-content { flex: 1; overflow-y: auto; position: relative; }

::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: #2b2b2b; }
::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #777; }
</style>
