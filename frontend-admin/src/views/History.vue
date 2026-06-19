<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">预警事件中心</h1>
        <p class="text-dark-400 mt-1">查看所有预警触发、恢复和确认记录</p>
      </div>
      <div class="flex items-center gap-2 text-sm">
        <span
          class="w-2 h-2 rounded-full"
          :class="wsConnected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'"
        ></span>
        <span :class="wsConnected ? 'text-green-400' : 'text-yellow-400'">
          {{ wsConnected ? '实时同步' : '连接中...' }}
        </span>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="card text-center">
        <p class="text-3xl font-bold text-red-400">{{ stats.open }}</p>
        <p class="text-dark-400 text-sm mt-1">待处理</p>
      </div>
      <div class="card text-center">
        <p class="text-3xl font-bold text-yellow-400">{{ stats.recovered }}</p>
        <p class="text-dark-400 text-sm mt-1">已恢复待确认</p>
      </div>
      <div class="card text-center">
        <p class="text-3xl font-bold text-blue-400">{{ stats.acknowledged }}</p>
        <p class="text-dark-400 text-sm mt-1">已确认</p>
      </div>
      <div class="card text-center">
        <p class="text-3xl font-bold text-dark-400">{{ stats.total }}</p>
        <p class="text-dark-400 text-sm mt-1">总事件</p>
      </div>
    </div>

    <div class="flex gap-2 flex-wrap">
      <button
        v-for="f in filters"
        :key="f.value"
        @click="currentFilter = f.value; fetchEvents()"
        class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
        :class="currentFilter === f.value
          ? 'bg-primary-500 text-white'
          : 'bg-dark-800 text-dark-300 hover:bg-dark-700'"
      >
        {{ f.label }}
      </button>
    </div>

    <div class="card">
      <div v-if="loading" class="text-center py-8 text-dark-400">
        加载中...
      </div>

      <div v-else-if="events.length === 0" class="text-center py-12">
        <div class="w-16 h-16 bg-dark-800 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-dark-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <p class="text-dark-400">暂无预警事件</p>
        <p class="text-dark-500 text-sm mt-1">当预警规则被触发时，事件会显示在这里</p>
      </div>

      <div v-else class="space-y-4">
        <div
          v-for="event in events"
          :key="event.id"
          class="p-4 rounded-xl border transition-all"
          :class="eventCardClass(event)"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-4 flex-1 min-w-0">
              <div
                class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                :class="eventIconBg(event)"
              >
                <svg v-if="event.event_type === 'triggered'" class="w-5 h-5" :class="eventIconColor(event)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                  <line x1="12" y1="9" x2="12" y2="13"/>
                  <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
                <svg v-else-if="event.event_type === 'recovered'" class="w-5 h-5" :class="eventIconColor(event)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
                <svg v-else class="w-5 h-5" :class="eventIconColor(event)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h4 class="text-white font-semibold truncate">
                    {{ event.alert_name || `预警 #${event.alert_id}` }}
                  </h4>
                  <span
                    class="px-2 py-0.5 rounded text-xs font-medium"
                    :class="eventTypeClass(event)"
                  >
                    {{ eventTypeLabel(event) }}
                  </span>
                  <span
                    class="px-2 py-0.5 rounded text-xs font-medium"
                    :class="eventStatusClass(event)"
                  >
                    {{ eventStatusLabel(event) }}
                  </span>
                </div>

                <p class="text-dark-400 text-sm mb-2">{{ event.message }}</p>

                <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-dark-500">
                  <span v-if="event.triggered_price">
                    触发: <span class="text-red-400 font-mono">${{ formatPrice(event.triggered_price) }}</span>
                    <span class="ml-1">{{ formatDate(event.triggered_at) }}</span>
                  </span>
                  <span v-if="event.recovered_price">
                    恢复: <span class="text-green-400 font-mono">${{ formatPrice(event.recovered_price) }}</span>
                    <span class="ml-1">{{ formatDate(event.recovered_at) }}</span>
                  </span>
                  <span v-if="event.acknowledged_at">
                    确认: {{ formatDate(event.acknowledged_at) }}
                  </span>
                </div>
              </div>
            </div>

            <div class="shrink-0">
              <button
                v-if="event.status === 'open'"
                @click="acknowledgeEvent(event)"
                class="px-4 py-2 bg-primary-500/20 text-primary-400 text-sm rounded-lg hover:bg-primary-500/30 transition-colors font-medium"
                :disabled="acknowledgingId === event.id"
              >
                {{ acknowledgingId === event.id ? '确认中...' : '确认' }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="hasMore" class="text-center pt-4">
          <button @click="loadMore" class="btn btn-secondary" :disabled="loadingMore">
            {{ loadingMore ? '加载中...' : '加载更多' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, onUnmounted } from 'vue'
import dayjs from 'dayjs'
import api from '../api'
import { useToastStore } from '../stores/toast'
import { useWebSocket } from '../composables/useWebSocket'

const toast = useToastStore()
const { wsConnected, connect, on, off } = useWebSocket()

const events = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const acknowledgingId = ref(null)
const currentFilter = ref(null)
const total = ref(0)
const pageSize = 20

const filters = [
  { label: '全部', value: null },
  { label: '待处理', value: 'open' },
  { label: '已确认', value: 'acknowledged' },
  { label: '已关闭', value: 'closed' }
]

const stats = computed(() => {
  const s = { open: 0, recovered: 0, acknowledged: 0, total: total.value }
  events.value.forEach(e => {
    if (e.status === 'open' && e.event_type === 'triggered') s.open++
    if (e.status === 'open' && e.event_type === 'recovered') s.recovered++
    if (e.status === 'acknowledged') s.acknowledged++
  })
  return s
})

const hasMore = computed(() => events.value.length < total.value)

function eventTypeLabel(event) {
  const map = { triggered: '已触发', recovered: '已恢复', acknowledged: '已确认' }
  return map[event.event_type] || event.event_type
}

function eventStatusLabel(event) {
  const map = { open: '待处理', acknowledged: '已确认', closed: '已关闭' }
  return map[event.status] || event.status
}

function eventCardClass(event) {
  if (event.status === 'acknowledged' || event.status === 'closed') {
    return 'bg-dark-900/50 border-dark-800'
  }
  if (event.event_type === 'triggered') {
    return 'bg-dark-900 border-red-500/30'
  }
  if (event.event_type === 'recovered') {
    return 'bg-dark-900 border-yellow-500/30'
  }
  return 'bg-dark-900 border-dark-700'
}

function eventIconBg(event) {
  if (event.status === 'acknowledged') return 'bg-blue-500/10'
  if (event.event_type === 'triggered') return 'bg-red-500/10'
  if (event.event_type === 'recovered') return 'bg-yellow-500/10'
  return 'bg-dark-700'
}

function eventIconColor(event) {
  if (event.status === 'acknowledged') return 'text-blue-400'
  if (event.event_type === 'triggered') return 'text-red-400'
  if (event.event_type === 'recovered') return 'text-yellow-400'
  return 'text-dark-400'
}

function eventTypeClass(event) {
  if (event.event_type === 'triggered') return 'bg-red-500/10 text-red-400'
  if (event.event_type === 'recovered') return 'bg-yellow-500/10 text-yellow-400'
  return 'bg-blue-500/10 text-blue-400'
}

function eventStatusClass(event) {
  if (event.status === 'open') return 'bg-dark-700 text-dark-300'
  if (event.status === 'acknowledged') return 'bg-green-500/10 text-green-400'
  return 'bg-dark-600 text-dark-400'
}

function formatPrice(price) {
  if (!price && price !== 0) return '0.00'
  return Number(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(date) {
  if (!date) return ''
  return dayjs(date).format('MM-DD HH:mm:ss')
}

async function fetchEvents(append = false) {
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }

  try {
    const params = { limit: pageSize, offset: append ? events.value.length : 0 }
    if (currentFilter.value) {
      params.status = currentFilter.value
    }
    const response = await api.get('/api/alerts/events', { params })
    if (append) {
      events.value = [...events.value, ...response.data.items]
    } else {
      events.value = response.data.items
    }
    total.value = response.data.total
  } catch (error) {
    toast.error('获取事件失败', error.response?.data?.detail || '请稍后重试')
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  await fetchEvents(true)
}

async function acknowledgeEvent(event) {
  acknowledgingId.value = event.id
  try {
    await api.post(`/api/alerts/events/${event.id}/acknowledge`)
    toast.success('已确认', '事件已标记为已确认')
    event.status = 'acknowledged'
    event.acknowledged_at = new Date().toISOString()
  } catch (error) {
    toast.error('确认失败', error.response?.data?.detail || '请稍后重试')
  } finally {
    acknowledgingId.value = null
  }
}

function handleNewEvent() {
  fetchEvents(false)
}

onMounted(() => {
  fetchEvents()
  connect()
  on('alert_triggered', handleNewEvent)
  on('alert_recovered', handleNewEvent)
  on('alert_state_changed', handleNewEvent)
})

onUnmounted(() => {
  off('alert_triggered', handleNewEvent)
  off('alert_recovered', handleNewEvent)
  off('alert_state_changed', handleNewEvent)
})
</script>
