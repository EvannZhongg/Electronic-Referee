<template>
  <div :class="['score-board', { 'overlay-mode': isOverlayMode }]">

    <div class="header" v-if="!isOverlayMode">
      <div class="header-section left">
        <button class="btn-stop" @click="$emit('stop')">
          <span class="icon">←</span> Stop
        </button>
      </div>

      <div class="header-section center">
        <div class="group-label">{{ store.currentContext.groupName || 'Free Mode' }}</div>
        <div class="player-navigator">
          <button class="nav-btn" @click="changePlayer(-1)" :disabled="isFirstPlayer">◀</button>
          <span class="player-name">{{ store.currentContext.contestantName || 'Player 1' }}</span>
          <button class="nav-btn" @click="changePlayer(1)">▶</button>
        </div>
      </div>

      <div class="header-section right">
        <div class="toggle-switch" title="Auto Next">
          <input type="checkbox" id="autoSwitch" v-model="isAutoNext">
          <label for="autoSwitch" class="toggle-label">
            <span class="toggle-switch-handle"></span>
          </label>
          <span class="toggle-text">Auto</span>
        </div>

        <button class="btn-tool btn-overlay" @click="openWindowSelector">🔳 Overlay</button>
        <button class="btn-tool btn-reset" @click="requestReset">⚠ Reset</button>
      </div>
    </div>

    <div v-else
         class="overlay-dock"
         @mouseenter="handleMouseEnter"
         @mouseleave="handleMouseLeave"
    >
      <div class="dock-content">
        <span class="dock-info">{{ store.currentContext.contestantName }}</span>
        <button class="btn-dock" @click="changePlayer(1)">Next ▶</button>
        <button class="btn-dock btn-dock-reset" @click="requestReset">R</button>
        <button class="btn-dock btn-dock-exit" @click="exitOverlay">Exit ✖</button>
      </div>
    </div>

    <div class="panels-container" :class="{ 'overlay-container': isOverlayMode }">
      <div
        v-for="(ref, refKey) in store.referees"
        :key="refKey"
        class="score-card"
        :class="{ 'draggable-card': isOverlayMode }"
        :style="isOverlayMode ? getCardStyle(refKey) : {}"
        @mousedown="isOverlayMode && startDrag($event, refKey)"
        @mouseenter="isOverlayMode && handleMouseEnter()"
        @mouseleave="isOverlayMode && handleMouseLeave()"
      >
        <div class="card-top" v-if="!isOverlayMode">
          <div class="ref-name">{{ ref.name }}</div>
          <div class="status-indicators">
            <div class="status-dot" :class="ref.status?.pri || 'disconnected'"></div>
            <div v-if="ref.status?.sec !== 'n/a'" class="status-dot" :class="ref.status?.sec || 'disconnected'"></div>
          </div>
        </div>

        <div class="overlay-header" v-else>
           <span class="ref-label">{{ ref.name }}</span>
        </div>

        <div class="score-main">{{ ref.total }}</div>

        <div class="score-detail" v-if="!isOverlayMode">
          <span class="plus">+{{ ref.plus }}</span> / <span class="minus">-{{ ref.minus }}</span>
        </div>
      </div>
    </div>

    <div v-if="showWindowSelector" class="modal-overlay">
      <div class="modal-content">
        <h3>Select Game Window</h3>
        <select v-model="selectedTargetWindow" class="win-select">
          <option value="" disabled>-- Select Application --</option>
          <option v-for="w in windowList" :key="w" :value="w">{{ w }}</option>
        </select>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showWindowSelector = false">Cancel</button>
          <button class="btn-confirm" @click="confirmOverlay">Start Overlay</button>
        </div>
      </div>
    </div>

     <div v-if="showResetDialog" class="modal-overlay">
      <div class="modal-content">
        <h3>Confirm Reset</h3>
        <p>Clear all scores?</p>
        <label class="dont-ask-label">
          <input type="checkbox" v-model="dontAskAgainTemp"> Don't ask again
        </label>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showResetDialog = false">Cancel</button>
          <button class="btn-confirm" @click="confirmResetAction">Reset</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRefereeStore } from '../stores/refereeStore'

const emit = defineEmits(['stop', 'overlay-change'])
const store = useRefereeStore()

// 状态
const isAutoNext = ref(false)
const showResetDialog = ref(false)
const dontAskAgainTemp = ref(false)
const isOverlayMode = ref(false)
const showWindowSelector = ref(false)
const windowList = ref([])
const selectedTargetWindow = ref("")

// 拖拽相关
const GRID_SIZE = 20
const cardPositions = reactive({})
let draggingRefKey = null
let dragOffset = { x: 0, y: 0 }
// 【关键】增加一个标志位，判断当前是否正在拖拽中
let isDragging = false

const isFirstPlayer = computed(() => {
  const group = store.projectConfig.groups.find(g => g.name === store.currentContext.groupName)
  if (!group || !group.players) return true
  return group.players.indexOf(store.currentContext.contestantName) <= 0
})

watch(isOverlayMode, (newVal) => {
  emit('overlay-change', newVal)
})

// IPC 通信
const sendOverlayMode = (active, bounds = null) => {
  if (window.electron && window.electron.ipcRenderer) {
    window.electron.ipcRenderer.send('set-overlay-mode', { active, bounds })
  }
}
const setIgnoreMouse = (ignore) => {
  if (window.electron && window.electron.ipcRenderer) {
    window.electron.ipcRenderer.send('set-ignore-mouse', ignore)
  }
}

// 【关键修复】鼠标移入/移出处理
const handleMouseEnter = () => {
  // 移入卡片，禁止穿透（允许点击/拖拽）
  setIgnoreMouse(false)
}

const handleMouseLeave = () => {
  // 移出卡片，如果正在拖拽中，绝对不能开启穿透，否则拖拽事件会断掉！
  if (isDragging) return
  // 只有非拖拽状态下移出，才开启穿透
  setIgnoreMouse(true)
}

// 业务逻辑
const requestReset = () => {
  if (store.appSettings.suppress_reset_confirm || isAutoNext.value) {
    performReset()
  } else {
    dontAskAgainTemp.value = false
    showResetDialog.value = true
  }
}
const confirmResetAction = () => {
  if (dontAskAgainTemp.value) store.updateSetting('suppress_reset_confirm', true)
  showResetDialog.value = false
  performReset()
}
const performReset = async () => {
  await store.resetAll()
  if (isAutoNext.value) setTimeout(() => changePlayer(1), 100)
}
const changePlayer = async (delta) => {
  const groupName = store.currentContext.groupName
  const group = store.projectConfig.groups.find(g => g.name === groupName)
  if (!group || !group.players) return
  const currentIdx = group.players.indexOf(store.currentContext.contestantName)
  const nextIdx = (currentIdx === -1 ? 0 : currentIdx) + delta
  if (nextIdx < 0) return
  if (nextIdx >= group.players.length) {
    if (store.projectConfig.mode === 'FREE') {
      const newPlayerName = `Player ${nextIdx + 1}`
      group.players.push(newPlayerName)
      await store.setMatchContext(groupName, newPlayerName)
    }
  } else {
    await store.setMatchContext(groupName, group.players[nextIdx])
  }
}

// 悬浮窗逻辑
const openWindowSelector = async () => {
  windowList.value = await store.fetchWindows()
  showWindowSelector.value = true
}
const confirmOverlay = async () => {
  if (!selectedTargetWindow.value) return
  const res = await store.getWindowBounds(selectedTargetWindow.value)

  showWindowSelector.value = false
  isOverlayMode.value = true

  sendOverlayMode(true, res.found ? res.bounds : null)
  setIgnoreMouse(true)

  // 【关键修复】初始化布局：使用 Object.keys 确保 refKey 匹配
  const CARD_HEIGHT_WITH_GAP = 140
  const LEFT_PADDING = 20
  const TOP_PADDING = 80

  // 注意：store.referees 的 Key 通常是 "1", "2" 等字符串
  Object.keys(store.referees).forEach((refKey, idx) => {
    if (!cardPositions[refKey]) {
      cardPositions[refKey] = {
        x: LEFT_PADDING,
        y: TOP_PADDING + (idx * CARD_HEIGHT_WITH_GAP)
      }
    }
  })
}

const exitOverlay = () => {
  isOverlayMode.value = false
  sendOverlayMode(false)
  setIgnoreMouse(false)
}

// 【关键修复】拖拽逻辑
const getCardStyle = (refKey) => {
  const pos = cardPositions[refKey] || { x: 0, y: 0 }
  return { left: `${pos.x}px`, top: `${pos.y}px`, zIndex: draggingRefKey === refKey ? 9999 : 1000 }
}

const startDrag = (e, refKey) => {
  if (e.button !== 0) return

  isDragging = true // 标记正在拖拽
  draggingRefKey = refKey

  // 确保拖拽开始时肯定不穿透
  setIgnoreMouse(false)

  const pos = cardPositions[refKey] || { x: 0, y: 0 }
  dragOffset = { x: e.clientX - pos.x, y: e.clientY - pos.y }

  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}

const onDrag = (e) => {
  if (!draggingRefKey) return
  let rawX = e.clientX - dragOffset.x
  let rawY = e.clientY - dragOffset.y
  cardPositions[draggingRefKey] = {
    x: Math.round(rawX / GRID_SIZE) * GRID_SIZE,
    y: Math.round(rawY / GRID_SIZE) * GRID_SIZE
  }
}

const stopDrag = () => {
  isDragging = false // 标记拖拽结束
  draggingRefKey = null

  // 拖拽结束时，如果鼠标还在卡片上，保持不穿透；如果不在（罕见），可以穿透
  // 简单起见，这里不强制设置，交由 mouseleave 处理

  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

const handleKeydown = (e) => { if (e.ctrlKey && e.code === 'KeyG') { e.preventDefault(); requestReset() } }
onMounted(() => { store.connectWebSocket(); store.fetchSettings(); window.addEventListener('keydown', handleKeydown) })
onUnmounted(() => { window.removeEventListener('keydown', handleKeydown); window.removeEventListener('mousemove', onDrag); window.removeEventListener('mouseup', stopDrag) })
</script>

<style scoped lang="scss">
/* 保持原有 CSS 样式不变，直接复用上一次提供的 CSS 即可 */
/* 这里为了节省篇幅省略 CSS 代码，请确保保留了 .overlay-mode, .draggable-card 等所有样式 */
.score-board {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.header {
  height: 70px;
  background: #252526;
  border-bottom: 1px solid #333;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 15px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.3);
  flex-shrink: 0;
}
.header-section { display: flex; align-items: center; gap: 10px; }
.header-section.left { flex: 1; }
.header-section.center { flex: 2; justify-content: center; flex-direction: column; gap: 2px; }
.header-section.right { flex: 1; justify-content: flex-end; }

button { border: none; cursor: pointer; border-radius: 4px; transition: 0.2s; font-weight: bold; }
button:hover { filter: brightness(1.1); }
button:active { transform: translateY(1px); }

.btn-stop { background: #444; color: #ccc; padding: 6px 12px; display: flex; align-items: center; gap: 5px; }
.btn-tool { padding: 6px 12px; font-size: 0.9rem; color: white; margin-left: 5px; }
.btn-overlay { background: #3498db; }
.btn-reset { background: #e74c3c; }

.group-label { font-size: 0.7rem; color: #777; text-transform: uppercase; }
.player-navigator {
  display: flex; align-items: center; gap: 10px; background: #1a1a1a; padding: 4px 10px; border-radius: 6px;
  .nav-btn { background: none; color: #666; font-size: 1rem; padding: 0 4px; &:hover:not(:disabled) { color: #3498db; } &:disabled { opacity: 0.2; } }
  .player-name { font-size: 1.1rem; color: #fff; font-weight: bold; min-width: 100px; text-align: center; }
}

.toggle-switch {
  display: flex; align-items: center; gap: 5px; margin-right: 10px;
  input { display: none; }
  .toggle-label {
    width: 36px; height: 18px; background: #444; border-radius: 18px; position: relative; cursor: pointer; transition: 0.3s;
    .toggle-switch-handle { width: 14px; height: 14px; background: white; border-radius: 50%; position: absolute; top: 2px; left: 2px; transition: 0.3s; }
  }
  input:checked + .toggle-label { background: #2ecc71; }
  input:checked + .toggle-label .toggle-switch-handle { left: 20px; }
  .toggle-text { font-size: 0.8rem; color: #aaa; }
}

.panels-container {
  flex: 1;
  padding: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  grid-auto-rows: max-content;
  gap: 15px;
  overflow-y: auto;
  align-content: start;

  &.overlay-container {
    display: block; position: relative; padding: 0; pointer-events: none;
  }
}

.score-card {
  background: #ecf0f1;
  border-radius: 8px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 4px 8px rgba(0,0,0,0.2);
  color: #2c3e50;

  .card-top { width: 100%; display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 0.9rem; font-weight: bold; }
  .status-indicators { display: flex; gap: 4px; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #bdc3c7; &.connected { background: #2ecc71; } }
  .score-main { font-size: 4rem; font-weight: 800; line-height: 1; margin: 10px 0; }
  .score-detail { font-size: 1rem; color: #666; background: #ddd; padding: 2px 10px; border-radius: 10px; }
}

.score-card.draggable-card {
  position: absolute;
  width: 140px;
  padding: 10px;
  background: rgba(20, 20, 20, 0.85);
  color: white;
  border: 1px solid rgba(255,255,255,0.2);
  border-left: 4px solid #3498db;
  box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
  pointer-events: auto;
  cursor: grab;
  user-select: none;

  &:active { cursor: grabbing; border-color: #3498db; }

  .score-main { font-size: 3.5rem; color: #fff; margin: 0; line-height: 1.1; }
  .overlay-header {
    font-size: 0.85rem;
    color: #ccc;
    width: 100%;
    text-align: left;
    border-bottom: 1px solid #444;
    margin-bottom: 4px;
    padding-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.overlay-dock {
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  z-index: 10000; padding-top: 5px; pointer-events: auto;

  .dock-content {
    background: rgba(0,0,0,0.7); padding: 4px 10px; border-radius: 0 0 8px 8px; display: flex; align-items: center; gap: 8px;
    .dock-info { color: #fff; font-size: 0.8rem; font-weight: bold; margin-right: 5px; }
    .btn-dock { font-size: 0.75rem; padding: 2px 8px; background: #555; color: #fff; }
    .btn-dock-reset { background: #f39c12; }
    .btn-dock-exit { background: #e74c3c; }
  }
}

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; z-index: 2000; }
.modal-content { background: #2b2b2b; padding: 20px; border-radius: 8px; width: 360px; text-align: center; }
.win-select { width: 100%; padding: 8px; margin: 15px 0; background: #111; color: white; border: 1px solid #444; }
.modal-actions { display: flex; justify-content: center; gap: 10px; }
.btn-confirm { background: #3498db; color: white; padding: 6px 15px; }
.btn-cancel { background: #555; color: white; padding: 6px 15px; }
.dont-ask-label { display: block; margin-bottom: 20px; cursor: pointer; color: #aaa; input { margin-right: 5px; } }
</style>
