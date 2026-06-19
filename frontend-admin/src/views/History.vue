<template>
  <div class="p-6 space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-white">预警事件中心</h1>
      <p class="text-dark-400 mt-1">查看所有预警触发、恢复和确认记录</p>
    </div>

    <div class="flex items-center gap-3 flex-wrap">
      <button
        v-for="f in filters"
        :key="f.value"
        @click="activeFilter = f.value"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        :class="activeFilter === f.value
          ? 'bg-primary-500 text-white'
          : 'bg-dark-800 text-dark-300 hover:bg-dark-700'"
      >
        {{ f.label }}
        <span v-if="counts[f.value] !== undefined" class="ml-1 opacity-75">({{ counts[f.value] }})</span>
      </button>
    </div>

    <div class="card">
      <div v-if="loading" class="text-center py-8 text-dark-400">加载中...</div>

      <div v-else-if="filteredEvents.length === 0" class="text-center py-12">
        <div class="w-16 h-16 bg-dark-800 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-dark-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <p class="text-dark-400">暂无事件记录</p>
        <p class="text-dark-500 text-sm mt-1">当预警被触发时，事件会显示在这里</p>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="event in filteredEvents"
          :key="event.id"
          class="p-4 rounded-lg border transition-colors"
          :class="eventCardClass(event)"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-3 flex-1 min-w-0">
              <div
                class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                :class="eventIconBg(event)"
              >
                <svg v-if="event.status === 'triggered'" class="w-5 h-5 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                <svg v-else-if="event.status === 'recovered'" class="w-5 h-5 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                <svg v-else class="w-5 h-5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-medium text-white">事件 #{{ event.id }}</span>
                  <span
                    class="px-2 py-0.5 rounded text-xs font-medium"
                    :class="eventStatusClass(event.status)"
                  >{{ eventStatusLabel(event.status) }}</span>
                </div>
                <p class="text-sm text-dark-300">{{ event.trigger_message }}</p>
                <p v-if="event.recovery_message" class="text-sm text-dark-400 mt-1">{{ event.recovery_message }}</p>

                <div class="flex items-center gap-4 mt-2 text-xs text-dark-500 flex-wrap">
                  <span>触发价: <span class="font-mono text-white">${{ formatPrice(event.trigger_price) }}</span></span>
                  <span v-if="event.recovery_price">恢复价: <span class="font-mono text-white">${{ formatPrice(event.recovery_price) }}</span></span>
                  <span>触发时间: {{ formatDateTime(event.triggered_at) }}</span>
                  <span v-if="event.recovered_at">恢复时间: {{ formatDateTime(event.recovered_at) }}</span>
                  <span v-if="event.acknowledged_at">确认时间: {{ formatDateTime(event.acknowledged_at) }}</span>
                </div>
                <p v-if="event.note" class="text-xs text-dark-400 mt-2 italic">备注: {{ event.note }}</p>
              </div>
            </div>

            <div class="flex-shrink-0">
              <button
                v-if="event.status !== 'acknowledged'"
                @click="acknowledgeEvent(event)"
                class="btn btn-primary btn-sm"
              >确认</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showAckModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card w-full max-w-md">
        <h3 class="text-lg font-medium text-white mb-4">确认事件 #{{ ackTarget?.id }}</h3>
        <p class="text-dark-400 text-sm mb-4">{{ ackTarget?.trigger_message }}</p>
        <div class="mb-4">
          <label class="block text-sm text-dark-300 mb-2">备注（可选）</label>
          <textarea v-model="ackNote" class="input" rows="3" placeholder="添加处理备注..."></textarea>
        </div>
        <div class="flex gap-3">
          <button @click="showAckModal = false" class="btn btn-secondary flex-1">取消</button>
          <button @click="doAcknowledge" class="btn btn-primary flex-1" :disabled="ackLoading">{{ ackLoading ? '确认中...' : '确认事件' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import dayjs from 'dayjs'
import api from '../api'
import { useToastStore } from '../stores/toast'
import { useAuthStore } from '../stores/auth'

const toast = useToastStore()
const authStore = useAuthStore()

const events = ref([])
const loading = ref(true)
const activeFilter = ref('all')
const showAckModal = ref(false)
const ackTarget = ref(null)
const ackNote = ref('')
const ackLoading = ref(false)
let ws = null
let reconnectTimer = null

const filters = [
  { label: '全部', value: 'all' },
  { label: '待确认', value: 'pending' },
  { label: '已触发', value: 'triggered' },
  { label: '已恢复', value: 'recovered' },
  { label: '已确认', value: 'acknowledged' }
]

const counts = computed(() => ({
  all: events.value.length,
  pending: events.value.filter(e => e.status !== 'acknowledged').length,
  triggered: events.value.filter(e => e.status === 'triggered').length,
  recovered: events.value.filter(e => e.status === 'recovered').length,
  acknowledged: events.value.filter(e => e.status === 'acknowledged').length
}))

const filteredEvents = computed(() => {
  if (activeFilter.value === 'all') return events.value
  if (activeFilter.value === 'pending') return events.value.filter(e => e.status !== 'acknowledged')
  return events.value.filter(e => e.status === activeFilter.value)
})

function eventStatusLabel(s) {
  return { triggered: '已触发·未恢复', recovered: '已恢复·待确认', acknowledged: '已确认' }[s] || s
}
function eventStatusClass(s) {
  return {
    'bg-red-500/10 text-red-400': s === 'triggered',
    'bg-blue-500/10 text-blue-400': s === 'recovered',
    'bg-green-500/10 text-green-400': s === 'acknowledged'
  }
}
function eventCardClass(e) {
  if (e.status === 'triggered') return 'bg-red-500/5 border-red-500/30'
  if (e.status === 'recovered') return 'bg-blue-500/5 border-blue-500/30'
  return 'border-dark-700'
}
function eventIconBg(e) {
  if (e.status === 'triggered') return 'bg-red-500/10'
  if (e.status === 'recovered') return 'bg-blue-500/10'
  return 'bg-green-500/10'
}
function formatPrice(p) {
  if (!p) return '0.00'
  return Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function formatDateTime(d) {
  if (!d) return ''
  return dayjs(d).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchEvents() {
  try {
    const response = await api.get('/api/alerts/events', { params: { limit: 200 } })
    events.value = response.data
  } catch (error) {
    toast.error('获取事件失败')
  } finally {
    loading.value = false
  }
}

function acknowledgeEvent(event) {
  ackTarget.value = event
  ackNote.value = ''
  showAckModal.value = true
}

async function doAcknowledge() {
  if (!ackTarget.value) return
  ackLoading.value = true
  try {
    await api.post(`/api/alerts/events/${ackTarget.value.id}/acknowledge`, { note: ackNote.value || null })
    toast.success('事件已确认')
    showAckModal.value = false
    await fetchEvents()
  } catch (error) {
    toast.error('确认失败', error.response?.data?.detail || '请稍后重试')
  } finally {
    ackLoading.value = false
  }
}

function connectWebSocket() {
  const token = authStore.token
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/price?token=${encodeURIComponent(token || '')}`
  ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    try {
      if (event.data === 'pong') return
      const message = JSON.parse(event.data)
      if (['alert_triggered', 'alert_recovered', 'alert_state_changed'].includes(message.type)) {
        fetchEvents()
      }
    } catch (e) {}
  }
  ws.onclose = () => {
    reconnectTimer = setTimeout(connectWebSocket, 5000)
  }
}

onMounted(() => {
  fetchEvents()
  connectWebSocket()
})
onUnmounted(() => {
  if (ws) ws.close()
  if (reconnectTimer) clearTimeout(reconnectTimer)
})
</script>
