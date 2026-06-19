<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">事件中心</h1>
        <p class="text-dark-400 mt-1">查看预警触发记录、确认恢复事件</p>
      </div>
      <div class="flex items-center gap-2">
        <div class="flex gap-1 bg-dark-900 p-1 rounded-lg">
          <button v-for="f in filters" :key="f.value" @click="activeFilter = f.value; fetchEvents()"
            class="px-3 py-1.5 text-sm rounded-md transition-colors"
            :class="activeFilter === f.value ? 'bg-primary-500 text-white' : 'text-dark-400 hover:text-white'">
            {{ f.label }}
            <span v-if="f.count > 0" class="ml-1 px-1.5 py-0.5 rounded text-xs bg-dark-700">{{ f.count }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">待处理（已触发）</p>
        <p class="text-xl font-bold text-red-400">{{ wsStore.stats.open_triggered }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">待确认（已恢复）</p>
        <p class="text-xl font-bold text-yellow-400">{{ wsStore.stats.recovered_pending }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">历史总事件</p>
        <p class="text-xl font-bold text-dark-200">{{ wsStore.stats.total_events }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">活跃规则</p>
        <p class="text-xl font-bold text-green-400">{{ wsStore.stats.active_rules }}</p>
      </div>
    </div>

    <div class="flex gap-3">
      <button v-if="pendingRecoveredCount > 0" @click="acknowledgeAllRecovered"
        class="btn btn-primary flex items-center gap-2">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        一键确认所有已恢复事件 ({{ pendingRecoveredCount }})
      </button>
      <button @click="fetchEvents()" class="btn btn-secondary flex items-center gap-2">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
        刷新
      </button>
    </div>

    <div class="card">
      <div v-if="loading" class="text-center py-8 text-dark-400">加载中...</div>
      <div v-else-if="events.length === 0" class="text-center py-12">
        <div class="w-16 h-16 bg-dark-800 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-dark-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <p class="text-dark-400">暂无事件记录</p>
        <p class="text-dark-500 text-sm mt-1">当预警触发时，事件会显示在这里</p>
      </div>
      <div v-else class="space-y-3">
        <div v-for="event in events" :key="event.id"
          class="p-4 bg-dark-900 rounded-lg border transition-colors"
          :class="{
            'border-red-500/30 bg-red-500/5': event.status === 'triggered',
            'border-yellow-500/30 bg-yellow-500/5': event.status === 'recovered',
            'border-dark-700': event.status === 'acknowledged'
          }">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-4 flex-1 min-w-0">
              <div class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                :class="{
                  'bg-red-500/20': event.status === 'triggered',
                  'bg-yellow-500/20': event.status === 'recovered',
                  'bg-green-500/20': event.status === 'acknowledged'
                }">
                <svg v-if="event.status === 'triggered'" class="w-5 h-5 text-red-400 animate-pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                <svg v-else-if="event.status === 'recovered'" class="w-5 h-5 text-yellow-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                <svg v-else class="w-5 h-5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <p class="text-white font-medium">{{ getAlertName(event) }}</p>
                  <span class="px-2 py-0.5 rounded text-xs" :class="wsStore.getEventDisplayStatus(event).color">
                    {{ wsStore.getEventDisplayStatus(event).label }}
                  </span>
                </div>
                <p class="text-dark-300 text-sm mt-1">{{ event.message }}</p>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-dark-400">
                  <span>触发价格: <span class="text-red-400 font-mono">${{ formatPrice(event.trigger_price) }}</span></span>
                  <span v-if="event.recovery_price">恢复价格: <span class="text-green-400 font-mono">${{ formatPrice(event.recovery_price) }}</span></span>
                  <span>触发时间: {{ formatDateTime(event.triggered_at) }}</span>
                  <span v-if="event.recovered_at">恢复时间: {{ formatDateTime(event.recovered_at) }}</span>
                  <span v-if="event.acknowledged_at">确认时间: {{ formatDateTime(event.acknowledged_at) }}</span>
                </div>
              </div>
            </div>
            <div class="flex-shrink-0">
              <button v-if="event.status === 'recovered'" @click="acknowledgeEvent(event.id)"
                class="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm rounded-lg transition-colors whitespace-nowrap">
                确认
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import dayjs from 'dayjs'
import api from '../api'
import { useWsStore } from '../stores/ws'
import { useToastStore } from '../stores/toast'

const wsStore = useWsStore()
const toast = useToastStore()
const events = ref([])
const loading = ref(true)
const activeFilter = ref('open')
let wsUnsub = null

const filters = computed(() => [
  { label: '待处理', value: 'open', count: wsStore.stats.open_triggered + wsStore.stats.recovered_pending },
  { label: '已触发', value: 'triggered', count: wsStore.stats.open_triggered },
  { label: '待确认', value: 'recovered', count: wsStore.stats.recovered_pending },
  { label: '已确认', value: 'acknowledged', count: 0 },
  { label: '全部', value: 'all', count: wsStore.stats.total_events }
])

const pendingRecoveredCount = computed(() => events.value.filter(e => e.status === 'recovered').length)

function getAlertName(event) {
  const rule = wsStore.rules.find(r => r.id === event.alert_id)
  return event.alert_name || rule?.name || `预警 #${event.alert_id}`
}
function formatPrice(p) { if (!p) return '0.00'; return Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDateTime(d) { return dayjs(d).format('YYYY-MM-DD HH:mm:ss') }

async function fetchEvents() {
  loading.value = true
  try {
    let statusParam = ''
    if (activeFilter.value === 'triggered') statusParam = 'triggered'
    else if (activeFilter.value === 'recovered') statusParam = 'recovered'
    else if (activeFilter.value === 'acknowledged') statusParam = 'acknowledged'
    else if (activeFilter.value === 'open') {
      const [tResp, rResp] = await Promise.all([
        api.get('/api/alerts/events', { params: { status: 'triggered', limit: 200 } }),
        api.get('/api/alerts/events', { params: { status: 'recovered', limit: 200 } })
      ])
      events.value = [...tResp.data, ...rResp.data].sort((a, b) => new Date(b.triggered_at) - new Date(a.triggered_at))
      loading.value = false
      return
    }
    const resp = await api.get('/api/alerts/events', { params: statusParam ? { status: statusParam, limit: 200 } : { limit: 200 } })
    events.value = resp.data
  } catch (e) {
    toast.error('加载失败', e.response?.data?.detail || '请稍后重试')
  } finally {
    loading.value = false
  }
}

async function acknowledgeEvent(id) {
  try {
    await api.post(`/api/alerts/events/${id}/acknowledge`)
    toast.success('已确认', '事件已标记为已处理')
  } catch (e) {
    toast.error('操作失败', e.response?.data?.detail || '请稍后重试')
  }
}

async function acknowledgeAllRecovered() {
  const recovered = events.value.filter(e => e.status === 'recovered')
  if (recovered.length === 0) return
  let success = 0, fail = 0
  for (const evt of recovered) {
    try {
      await api.post(`/api/alerts/events/${evt.id}/acknowledge`)
      success++
    } catch (e) { fail++ }
  }
  toast.success('批量确认完成', `成功 ${success} 个${fail > 0 ? `，失败 ${fail} 个` : ''}`)
}

onMounted(() => {
  fetchEvents()
  wsUnsub = wsStore.onMessage((msg) => {
    if (['alert_triggered', 'alert_recovered', 'event_acknowledged', 'rule_state_changed', 'stats_update'].includes(msg.type)) {
      fetchEvents()
    }
  })
})
onUnmounted(() => { if (wsUnsub) wsUnsub() })
</script>
