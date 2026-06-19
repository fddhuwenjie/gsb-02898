<template>
  <div class="p-6 space-y-6">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">预警事件</h1>
        <p class="text-dark-400 mt-1">完整事件流：触发 → 恢复 → 已确认</p>
      </div>
      <div class="flex items-center gap-2 text-xs">
        <span class="flex items-center gap-2 text-dark-400">
          <span
            class="w-2 h-2 rounded-full"
            :class="wsConnected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'"
          ></span>
          {{ wsConnected ? '实时同步中' : '离线' }}
        </span>
      </div>
    </div>

    <!-- 过滤栏 -->
    <div class="card flex flex-wrap items-center gap-3">
      <span class="text-sm text-dark-400">事件状态：</span>
      <button
        v-for="opt in filterOptions"
        :key="opt.value || 'all'"
        @click="filterStatus = opt.value; fetchHistories()"
        class="px-3 py-1.5 text-xs rounded-md transition-colors"
        :class="filterStatus === opt.value
          ? 'bg-primary-500 text-white'
          : 'bg-dark-800 text-dark-300 hover:bg-dark-700'"
      >
        {{ opt.label }}
      </button>
      <button @click="fetchHistories" class="ml-auto btn btn-secondary text-xs px-3 py-1.5">
        刷新
      </button>
    </div>

    <!-- 事件列表 -->
    <div class="card">
      <div v-if="loading" class="text-center py-8 text-dark-400">加载中...</div>

      <div v-else-if="histories.length === 0" class="text-center py-12">
        <p class="text-dark-400">暂无事件记录</p>
        <p class="text-dark-500 text-sm mt-1">当预警被触发时记录会出现在这里</p>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="h in histories"
          :key="h.id"
          class="p-4 bg-dark-900 rounded-lg border border-dark-800 hover:border-dark-700 transition-colors"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-start gap-3 min-w-0 flex-1">
              <div
                class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                :class="iconBg(h.event_status)"
              >
                <span class="text-base">{{ iconText(h.event_status) }}</span>
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <span
                    class="px-2 py-0.5 rounded text-xs font-medium"
                    :class="statusClass(h.event_status)"
                  >
                    {{ statusMap[h.event_status] }}
                  </span>
                  <span
                    class="px-2 py-0.5 rounded text-xs"
                    :class="h.alert_type === 'above' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'"
                  >
                    {{ h.alert_type === 'above' ? '高于' : '低于' }} ${{ formatPrice(h.target_price) }}
                  </span>
                  <span class="text-xs text-dark-500">事件 #{{ h.id }} · 规则 #{{ h.alert_id }}</span>
                </div>
                <p class="text-white font-medium mt-1 truncate">{{ h.message }}</p>
                <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-dark-400">
                  <span>触发价：<span class="text-primary-400 font-mono">${{ formatPrice(h.triggered_price) }}</span></span>
                  <span v-if="h.resolved_price !== null && h.resolved_price !== undefined">
                    恢复价：<span class="text-green-400 font-mono">${{ formatPrice(h.resolved_price) }}</span>
                  </span>
                  <span>触发于 {{ formatDate(h.triggered_at) }}</span>
                  <span v-if="h.resolved_at">恢复于 {{ formatDate(h.resolved_at) }}</span>
                  <span v-if="h.acked_at">确认于 {{ formatDate(h.acked_at) }}</span>
                </div>
              </div>
            </div>
            <div class="flex-shrink-0">
              <button
                v-if="h.event_status !== 'acked'"
                @click="ackOne(h)"
                class="px-3 py-1.5 text-xs rounded bg-yellow-500/10 text-yellow-300 hover:bg-yellow-500/20"
              >
                确认
              </button>
              <span v-else class="text-xs text-dark-500">已确认</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import dayjs from 'dayjs'
import api from '../api'
import { useToastStore } from '../stores/toast'
import { useAuthStore } from '../stores/auth'

const toast = useToastStore()
const authStore = useAuthStore()

const histories = ref([])
const loading = ref(true)
const filterStatus = ref(null)
const wsConnected = ref(false)

let ws = null
let reconnectTimer = null
let heartbeatTimer = null

const filterOptions = [
  { label: '全部', value: null },
  { label: '触发中', value: 'firing' },
  { label: '已恢复', value: 'resolved' },
  { label: '已确认', value: 'acked' },
]

const statusMap = {
  firing: '触发中',
  resolved: '已恢复',
  acked: '已确认',
}

function statusClass(s) {
  if (s === 'firing') return 'bg-red-500/15 text-red-400'
  if (s === 'resolved') return 'bg-blue-500/15 text-blue-300'
  return 'bg-dark-700 text-dark-300'
}

function iconBg(s) {
  if (s === 'firing') return 'bg-red-500/15'
  if (s === 'resolved') return 'bg-blue-500/15'
  return 'bg-dark-800'
}

function iconText(s) {
  if (s === 'firing') return '🔔'
  if (s === 'resolved') return '✅'
  return '☑️'
}

function formatPrice(p) {
  if (p === null || p === undefined) return '-'
  return Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(d) {
  return dayjs(d).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchHistories() {
  loading.value = true
  try {
    const params = { limit: 200 }
    if (filterStatus.value) params.event_status = filterStatus.value
    const response = await api.get('/api/alerts/histories', { params })
    histories.value = response.data
  } catch (error) {
    toast.error('获取事件失败', error.response?.data?.detail)
  } finally {
    loading.value = false
  }
}

async function ackOne(h) {
  try {
    await api.post(`/api/alerts/histories/${h.id}/ack`)
    toast.success('已确认')
    await fetchHistories()
  } catch (error) {
    toast.error('确认失败', error.response?.data?.detail)
  }
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = authStore.token
  const url = `${protocol}//${window.location.host}/ws/price${token ? `?token=${encodeURIComponent(token)}` : ''}`
  ws = new WebSocket(url)

  ws.onopen = () => {
    wsConnected.value = true
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 30000)
  }

  ws.onmessage = (event) => {
    if (event.data === 'pong') return
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'alert_triggered' || msg.type === 'alert_resolved') {
        // 一致性策略：服务端已先落库，再推送 -> 收到广播后立即重拉一次列表
        fetchHistories()
      }
    } catch (e) { /* ignore */ }
  }

  ws.onclose = () => {
    wsConnected.value = false
    clearInterval(heartbeatTimer)
    reconnectTimer = setTimeout(connectWebSocket, 5000)
  }
  ws.onerror = () => {}
}

onMounted(() => {
  fetchHistories()
  connectWebSocket()
})

onUnmounted(() => {
  if (ws) ws.close()
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (heartbeatTimer) clearInterval(heartbeatTimer)
})
</script>
