// src/renderer/src/stores/refereeStore.js
import {defineStore} from 'pinia'
import axios from 'axios'

const API_BASE = 'http://127.0.0.1:8000'

export const useRefereeStore = defineStore('referee', {
  state: () => ({
    // 结构: { 1: { total: 0, plus: 0, minus: 0, name: "Referee 1" } }
    referees: {},
    isConnected: false,
    ws: null
  }),

  actions: {
    // 1. 初始化 WebSocket 连接 (接收实时分数)
    connectWebSocket() {
      if (this.ws) return
      this.ws = new WebSocket('ws://127.0.0.1:8000/ws')
      this.ws.onopen = () => { this.isConnected = true; console.log('WS Connected') }

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          // 【修改点】同时监听 score_update 和 status_update
          if (msg.type === 'score_update' || msg.type === 'status_update') {
            this.updateScore(msg.payload)
          }
        } catch (e) {
          console.error("WS Message Parse Error", e)
        }
      }

      this.ws.onclose = () => {
        this.isConnected = false
        this.ws = null
        // 断线自动重连
        setTimeout(() => this.connectWebSocket(), 3000)
      }

      this.ws.onerror = (err) => {
        console.error('WS Error', err)
        this.ws.close()
      }
    },

    // 内部方法：更新本地分数状态
    updateScore(payload) {
      // payload: { index: 1, score: {total, plus, minus}, status: {pri, sec} }
      const {index, score, status} = payload

      if (!this.referees[index]) {
        this.referees[index] = {name: `Referee ${index}`}
      }

      this.referees[index] = {
        ...this.referees[index],
        total: score.total,
        plus: score.plus,
        minus: score.minus,
        status: status // 保存状态对象 {pri: 'connected', sec: ...}
      }
    },

    // 2. 扫描设备 (支持后台缓存 + 强制刷新)
    // isRefresh = false: 获取后台缓存（瞬间返回）
    // isRefresh = true:  清空缓存并重新扫描（需等待）
    async scanDevices(isRefresh = false) {
      try {
        const res = await axios.get(`${API_BASE}/scan?flush=${isRefresh}`)
        return res.data.devices || [] // 返回 [{name, address, rssi, is_target}, ...]
      } catch (e) {
        console.error("Scan failed:", e)
        throw e
      }
    },

    // 3. 配置裁判并连接设备
    async setupReferees(config) {
      try {
        await axios.post(`${API_BASE}/setup`, config)

        // 初始化本地状态，默认状态为 connecting
        config.referees.forEach(r => {
          this.referees[r.index] = {
            name: r.name || `Referee ${r.index}`,
            total: 0, plus: 0, minus: 0,
            status: {pri: 'connecting', sec: r.mode === 'DUAL' ? 'connecting' : 'n/a'}
          }
        })
      } catch (e) {
        console.error("Setup failed:", e)
        throw e
      }
    },

    // 4. 重置所有分数 (归零)
    async resetAll() {
      try {
        await axios.post(`${API_BASE}/reset`)
        // 乐观更新：不等后端返回，直接将界面归零，体验更好
        for (const key in this.referees) {
          this.referees[key].total = 0
          this.referees[key].plus = 0
          this.referees[key].minus = 0
        }
      } catch (e) {
        console.error("Reset failed:", e)
      }
    },

    // 5. 结束比赛 (Teardown)
    // 断开所有蓝牙连接，并清理本地状态，以便开始下一场
    async stopMatch() {
      try {
        await axios.post(`${API_BASE}/teardown`)
        console.log("Match stopped, devices disconnected.")
      } catch (e) {
        console.error("Failed to teardown match:", e)
      } finally {
        // 无论后端是否成功，前端都要清空状态
        this.referees = {}
      }
    }
  }
})
