<template>
  <div class="setup-wizard">
    <div class="steps-header">
      <div :class="['step', { active: currentStep === 1 }]">{{ $t('wiz_step1') }}</div>
      <div class="divider"></div>
      <div :class="['step', { active: currentStep === 2 }]">{{ $t('wiz_step2') }}</div>
    </div>

    <div v-if="currentStep === 1" class="step-content">
       <h2>{{ $t('wiz_step1') }}</h2>
       <div class="form-group">
        <label>{{ $t('wiz_proj_name') }}</label>
        <input v-model="form.projectName" type="text" placeholder="Enter match name..." />
      </div>
      <div class="form-group">
        <label>{{ $t('wiz_mode') }}</label>
        <div class="radio-group">
          <label :class="{ checked: form.mode === 'FREE' }">
            <input type="radio" v-model="form.mode" value="FREE" /> {{ $t('wiz_mode_free') }}
          </label>
          <label :class="{ checked: form.mode === 'TOURNAMENT' }">
            <input type="radio" v-model="form.mode" value="TOURNAMENT" /> {{ $t('wiz_mode_tourn') }}
          </label>
        </div>
      </div>
      <div class="form-group" v-if="form.mode === 'FREE'">
        <label>{{ $t('wiz_ref_count') }}</label>
        <input type="number" v-model.number="form.refereeCount" min="1" max="5" />
      </div>
      <div class="actions">
        <button class="btn-secondary" @click="$emit('cancel')">Cancel</button>
        <button class="btn-primary" @click="goToStep2">{{ $t('btn_next') }} >></button>
      </div>
    </div>

    <div v-else class="step-content">
      <div class="scan-bar">
        <h2>{{ $t('wiz_step2') }}</h2>
        <div class="scan-controls">
          <span v-if="isScanning" class="status scanning">
            <Loader2 class="spin" :size="16"/> {{ $t('status_scanning') }}
          </span>
          <span v-else class="status">
            {{ $t('status_found', { count: scannedDevices.length }) }}
          </span>
          <button class="btn-scan" @click="startScan(true)" :disabled="isScanning">
            <RefreshCw :size="16" /> {{ $t('btn_scan') }}
          </button>
        </div>
      </div>

      <div class="device-list-container">
        <div v-for="(bind, index) in bindings" :key="index" class="ref-card">
          <div class="card-header">Referee {{ bind.index }}</div>
          <div class="card-body">
            <div class="row">
              <label>Mode</label>
              <select v-model="bind.mode" @change="onModeChange(bind)">
                <option value="SINGLE">Single Device (单机)</option>
                <option value="DUAL">Dual Device (双机)</option>
              </select>
            </div>
            <div class="row">
              <label>Primary Device</label>
              <select v-model="bind.pri_addr">
                <option value="">-- Select Device --</option>
                <option v-for="d in getAvailableDevices(index, 'pri')" :key="d.address" :value="d.address">
                  {{ d.name }} ({{ d.address }})
                </option>
              </select>
            </div>
            <div class="row" v-if="bind.mode === 'DUAL'">
              <label>Secondary Device</label>
              <select v-model="bind.sec_addr">
                <option value="">-- Select Device --</option>
                <option v-for="d in getAvailableDevices(index, 'sec')" :key="d.address" :value="d.address">
                  {{ d.name }} ({{ d.address }})
                </option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="actions">
        <button class="btn-secondary" @click="currentStep = 1">&lt;&lt; Back</button>
        <button class="btn-success" @click="finishSetup">{{ $t('btn_start') }}</button>
      </div>
    </div>

    <div v-if="isConnecting" class="overlay">
      <div class="connect-dialog">
        <h3>Connecting to Devices...</h3>
        <div class="status-list">
          <div v-for="b in bindings" :key="b.index" class="status-row">
            <span class="label">Referee {{ b.index }}:</span>

            <span v-if="b.pri_addr" class="tag" :class="getRefStatus(b.index, 'pri')">
              Pri: {{ getRefStatus(b.index, 'pri') }}
            </span>
            <span v-else class="tag gray">Pri: None</span>

            <template v-if="b.mode === 'DUAL'">
              <span v-if="b.sec_addr" class="tag" :class="getRefStatus(b.index, 'sec')">
                Sec: {{ getRefStatus(b.index, 'sec') }}
              </span>
              <span v-else class="tag gray">Sec: None</span>
            </template>
          </div>
        </div>

        <div class="dialog-actions">
          <div v-if="!showForceEntry" class="loading-area">
            <Loader2 class="spin" :size="24" />
            <span>Waiting for connection...</span>
          </div>
          <div v-else class="force-area">
            <p class="warn-text">Some devices failed to connect.</p>
            <button class="btn-secondary" @click="cancelConnect">Cancel</button>
            <button class="btn-primary" @click="confirmForceEnter">Enter Anyway</button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRefereeStore } from '../stores/refereeStore'
import { Loader2, RefreshCw } from 'lucide-vue-next'

const emit = defineEmits(['cancel', 'finished'])
const store = useRefereeStore()

const currentStep = ref(1)
const isScanning = ref(false)
const scannedDevices = ref([])
const form = reactive({ projectName: 'New Match', mode: 'FREE', refereeCount: 1 })
const bindings = ref([])

// 新增连接状态控制
const isConnecting = ref(false)
const showForceEntry = ref(false)
let connectTimer = null

const goToStep2 = () => {
  if (bindings.value.length !== form.refereeCount) {
    bindings.value = Array.from({ length: form.refereeCount }, (_, index) => ({
      index: index + 1, name: `Referee ${index + 1}`, mode: 'SINGLE', pri_addr: '', sec_addr: ''
    }))
  }
  currentStep.value = 2
  if (scannedDevices.value.length === 0) startScan(false)
}

const startScan = async (isRefresh = true) => {
  isScanning.value = true
  try {
    const allDevices = await store.scanDevices(isRefresh)
    scannedDevices.value = allDevices
  } catch (e) {
    console.error("Scan failed", e)
  } finally {
    isScanning.value = false
  }
}

const onModeChange = (binding) => {
  if (binding.mode === 'SINGLE') binding.sec_addr = ''
}

const getAvailableDevices = (currentIndex, currentType) => {
  const usedAddresses = new Set()
  bindings.value.forEach((b, idx) => {
    if (b.pri_addr && (idx !== currentIndex || currentType !== 'pri')) usedAddresses.add(b.pri_addr)
    if (b.mode === 'DUAL' && b.sec_addr && (idx !== currentIndex || currentType !== 'sec')) usedAddresses.add(b.sec_addr)
  })
  return scannedDevices.value.filter(d => !usedAddresses.has(d.address))
}

// 获取 Store 中的连接状态 (connecting / connected / error)
const getRefStatus = (index, role) => {
  const refState = store.referees[index]
  if (!refState || !refState.status) return 'waiting'
  return refState.status[role] || 'waiting'
}

// 【关键修改】点击 Start Match 后执行
const finishSetup = async () => {
  // 1. 发送配置到后端
  await store.setupReferees({ referees: bindings.value })

  // 2. 显示遮罩，开始轮询状态
  isConnecting.value = true
  showForceEntry.value = false

  // 设置超时：10秒连不上则显示“强制进入”按钮
  const timeout = setTimeout(() => {
    showForceEntry.value = true
  }, 10000)

  // 轮询检查是否全部 Connected
  connectTimer = setInterval(() => {
    if (checkAllConnected()) {
      clearTimeout(timeout)
      clearInterval(connectTimer)
      // 全部连接成功，跳转！
      isConnecting.value = false
      emit('finished')
    } else if (checkAnyError()) {
      // 如果有设备报错，提前显示强制按钮
      showForceEntry.value = true
    }
  }, 500)
}

// 检查是否所有已配置的设备都变成了 'connected'
const checkAllConnected = () => {
  for (const b of bindings.value) {
    const status = store.referees[b.index]?.status
    if (!status) return false

    // 检查主设备
    if (b.pri_addr && status.pri !== 'connected') return false
    // 检查副设备
    if (b.mode === 'DUAL' && b.sec_addr && status.sec !== 'connected') return false
  }
  return true
}

const checkAnyError = () => {
  for (const b of bindings.value) {
    const status = store.referees[b.index]?.status
    if (status && (status.pri === 'error' || status.sec === 'error')) return true
  }
  return false
}

const cancelConnect = () => {
  clearInterval(connectTimer)
  isConnecting.value = false
  store.stopMatch() // 取消时断开已连上的设备
}

const confirmForceEnter = () => {
  clearInterval(connectTimer)
  isConnecting.value = false
  emit('finished')
}
</script>

<style scoped lang="scss">
/* 保留原有样式 ... */
.setup-wizard { padding: 30px; color: white; max-width: 800px; margin: 0 auto; }
.steps-header { display: flex; align-items: center; margin-bottom: 30px;
  .step { font-size: 1.2rem; color: #555; font-weight: bold; &.active { color: #3498db; } }
  .divider { flex: 1; height: 1px; background: #333; margin: 0 20px; }
}
.form-group { margin-bottom: 20px; label { display: block; margin-bottom: 8px; color: #ccc; }
  input { width: 100%; padding: 10px; background: #252526; border: 1px solid #3d3d3d; color: white; border-radius: 4px; outline: none; &:focus { border-color: #3498db; } }
}
.radio-group { display: flex; gap: 20px; label { cursor: pointer; padding: 10px 20px; background: #252526; border: 1px solid #3d3d3d; border-radius: 4px; &.checked { background: #3498db; } input { display: none; } } }
.scan-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; .scan-controls { display: flex; gap: 15px; align-items: center; } .spin { animation: spin 1s linear infinite; } }
@keyframes spin { 100% { transform: rotate(360deg); } }
.device-list-container { display: grid; gap: 20px; margin-bottom: 30px; }
.ref-card { background: #252526; border: 1px solid #3d3d3d; border-radius: 8px; overflow: hidden; .card-header { background: #333; padding: 10px 15px; font-weight: bold; } .card-body { padding: 15px; } .row { margin-bottom: 10px; label { font-size: 0.9rem; color: #888; } }
  select { width: 100%; padding: 8px; background: #1e1e1e; color: white; border: 1px solid #444; border-radius: 4px; outline: none; }
}
.actions { display: flex; justify-content: flex-end; gap: 15px; margin-top: 30px; button { padding: 10px 25px; border-radius: 4px; font-weight: bold; cursor: pointer; border: none; } .btn-secondary { background: #555; color: white; } .btn-primary { background: #3498db; color: white; } .btn-success { background: #2ecc71; color: white; } .btn-scan { background: #e67e22; color: white; } button:disabled { opacity: 0.5; } }

/* 【新增】遮罩层样式 */
.overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex; justify-content: center; align-items: center;
  z-index: 2000;
}
.connect-dialog {
  background: #252526;
  padding: 30px;
  border-radius: 12px;
  width: 400px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  h3 { margin-top: 0; margin-bottom: 20px; text-align: center; }
}
.status-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #333;
}
.tag {
  padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: bold;
  &.waiting { color: #888; background: #333; }
  &.connecting { color: #f1c40f; background: rgba(241, 196, 15, 0.1); }
  &.connected { color: #2ecc71; background: rgba(46, 204, 113, 0.1); }
  &.error { color: #e74c3c; background: rgba(231, 76, 60, 0.1); }
  &.gray { color: #555; }
}
.dialog-actions { margin-top: 20px; text-align: center; }
.loading-area { display: flex; flex-direction: column; align-items: center; gap: 10px; color: #aaa; }
.force-area {
  .warn-text { color: #e74c3c; margin-bottom: 15px; }
  button { margin: 0 5px; }
}
</style>
