<template>
  <div class="score-board">
    <div class="header">
      <div class="left-actions">
        <button class="btn-stop" @click="$emit('stop')">← Stop Match</button>
      </div>
      <h2>Live Scoreboard</h2>
      <button class="btn-reset" @click="store.resetAll">⚠ RESET ALL</button>
    </div>

    <div class="panels-container">
      <div
        v-for="(ref, index) in store.referees"
        :key="index"
        class="score-card"
      >
        <div class="card-top">
          <div class="ref-name">{{ ref.name }}</div>

          <div class="status-indicators">
            <div
              class="status-dot"
              :class="ref.status?.pri || 'disconnected'"
              title="Primary Device"
            ></div>

            <div
              v-if="ref.status?.sec !== 'n/a'"
              class="status-dot"
              :class="ref.status?.sec || 'disconnected'"
              title="Secondary Device"
            ></div>
          </div>
        </div>

        <div class="score-main">{{ ref.total }}</div>

        <div class="score-detail">
          <span class="plus">+{{ ref.plus }}</span>
          <span class="divider">/</span>
          <span class="minus">-{{ ref.minus }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRefereeStore } from '../stores/refereeStore'

// 定义向父组件发射的事件
defineEmits(['stop'])

const store = useRefereeStore()

onMounted(() => {
  // 组件挂载时确保 WebSocket 已连接
  store.connectWebSocket()
})
</script>

<style scoped lang="scss">
.score-board {
  padding: 20px;
  color: white;
  background-color: #2b2b2b;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  flex-shrink: 0;
}

.btn-stop {
  background: #7f8c8d;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  font-size: 0.9rem;
  transition: background 0.2s;
  &:hover { background: #95a5a6; }
}

.btn-reset {
  background: #c0392b;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  font-size: 0.9rem;
  transition: background 0.2s;
  &:hover { background: #e74c3c; }
}

.panels-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  overflow-y: auto;
  padding-bottom: 20px;
}

.score-card {
  background: #ecf0f1;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  color: #2c3e50;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
}

/* 新增：卡片顶部布局 */
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.ref-name {
  font-size: 1.2rem;
  font-weight: bold;
  color: #34495e;
}

/* 新增：状态灯样式 */
.status-indicators {
  display: flex;
  gap: 6px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #95a5a6; /* 默认 disconnected (灰色) */
  transition: background-color 0.3s;

  &.connecting {
    background-color: #f1c40f; /* 黄色 */
    animation: pulse 1s infinite;
  }

  &.connected {
    background-color: #2ecc71; /* 绿色 */
    box-shadow: 0 0 5px rgba(46, 204, 113, 0.5);
  }

  &.error {
    background-color: #e74c3c; /* 红色 */
  }
}

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.9); }
  100% { opacity: 1; transform: scale(1); }
}

.score-main {
  font-size: 5rem;
  font-weight: bold;
  line-height: 1;
  margin: 10px 0;
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-detail {
  font-size: 1.1rem;
  color: #7f8c8d;
  margin-top: auto;
  font-weight: 500;

  .plus { color: #27ae60; }
  .divider { margin: 0 8px; color: #bdc3c7; }
  .minus { color: #c0392b; }
}
</style>
