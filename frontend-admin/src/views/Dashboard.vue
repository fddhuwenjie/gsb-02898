<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">仪表盘</h1>
        <p class="text-dark-400 mt-1">实时监控BTC行情与预警状态</p>
      </div>
      <div class="flex items-center gap-2 text-sm">
        <span class="w-2 h-2 rounded-full" :class="wsStore.connected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'"></span>
        <span :class="wsStore.connected ? 'text-green-400' : 'text-yellow-400'">
          {{ wsStore.connected ? '实时连接中' : '连接中...' }}
        </span>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">当前价格</p>
        <p class="text-lg font-bold text-white">${{ formatPrice(priceData.price) }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">监控中规则</p>
        <p class="text-lg font-bold text-green-400">{{ wsStore.stats.active_rules }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">已触发未恢复</p>
        <p class="text-lg font-bold text-red-400">{{ wsStore.stats.open_triggered }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">待确认事件</p>
        <p class="text-lg font-bold text-yellow-400">{{ wsStore.stats.recovered_pending }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">冷却中规则</p>
        <p class="text-lg font-bold text-blue-400">{{ wsStore.stats.cooldown_rules }}</p>
      </div>
      <div class="card !p-4">
        <p class="text-dark-400 text-xs mb-1">历史总事件</p>
        <p class="text-lg font-bold text-dark-300">{{ wsStore.stats.total_events }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      <div class="card lg:col-span-2 bg-gradient-to-br from-dark-800 to-dark-900">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-dark-400 text-sm">BTC/USDT</p>
            <div class="flex items-baseline gap-3 mt-1">
              <span class="text-3xl font-bold text-white">${{ formatPrice(priceData.price) }}</span>
              <span class="text-base font-medium px-2 py-0.5 rounded"
                :class="priceChange >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'">
                {{ priceChange >= 0 ? '+' : '' }}{{ priceChange?.toFixed(2) }}%
              </span>
            </div>
          </div>
          <div class="w-14 h-14 bg-primary-500/10 rounded-2xl flex items-center justify-center">
            <svg class="w-8 h-8 text-primary-500" viewBox="0 0 32 32" fill="currentColor">
              <path d="M22.5 14.1c.3-2-1.2-3.1-3.3-3.8l.7-2.7-1.6-.4-.7 2.6c-.4-.1-.8-.2-1.3-.3l.7-2.6-1.6-.4-.7 2.7c-.3-.1-.7-.2-1-.3l-2.2-.5-.4 1.7s1.2.3 1.2.3c.7.2.8.6.8 1l-.8 3.2c0 0 .1 0 .2.1-.1 0-.1 0-.2 0l-1.1 4.5c-.1.2-.3.5-.8.4 0 0-1.2-.3-1.2-.3l-.8 1.8 2.1.5c.4.1.8.2 1.2.3l-.7 2.7 1.6.4.7-2.7c.4.1.9.2 1.3.3l-.7 2.7 1.6.4.7-2.7c2.8.5 4.9.3 5.8-2.2.7-2-.1-3.2-1.5-3.9 1.1-.3 1.9-1 2.1-2.5z"/>
            </svg>
          </div>
        </div>
      </div>
      <div class="card">
        <p class="text-dark-400 text-xs mb-1">24h 最高</p>
        <p class="text-xl font-semibold text-white">${{ formatPrice(priceData.high_24h) }}</p>
      </div>
      <div class="card">
        <p class="text-dark-400 text-xs mb-1">24h 最低</p>
        <p class="text-xl font-semibold text-white">${{ formatPrice(priceData.low_24h) }}</p>
      </div>
      <div class="card">
        <p class="text-dark-400 text-xs mb-1">24h 涨跌</p>
        <p class="text-xl font-semibold" :class="priceChangeAmount >= 0 ? 'text-green-400' : 'text-red-400'">
          {{ priceChangeAmount >= 0 ? '+' : '' }}${{ formatPrice(Math.abs(priceChangeAmount)) }}
        </p>
      </div>
    </div>

    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-4">
          <h3 class="text-lg font-medium text-white">价格走势</h3>
          <span class="text-dark-500 text-sm">成交量: {{ formatVolume(priceData.volume_24h) }}</span>
        </div>
        <div class="flex gap-1 bg-dark-900 p-1 rounded-lg">
          <button v-for="interval in intervals" :key="interval.value"
            @click="selectedInterval = interval.value"
            class="px-3 py-1.5 text-sm rounded-md transition-colors"
            :class="selectedInterval === interval.value ? 'bg-primary-500 text-white' : 'text-dark-400 hover:text-white'">
            {{ interval.label }}
          </button>
        </div>
      </div>
      <div ref="chartRef" class="h-80"></div>
    </div>

    <div v-if="wsStore.openEvents.length > 0" class="card border-red-500/30 bg-red-500/5">
      <h3 class="text-lg font-medium text-white mb-3 flex items-center gap-2">
        <span class="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
        待处理事件 ({{ wsStore.openEvents.length }})
      </h3>
      <div class="space-y-2 max-h-64 overflow-y-auto">
        <div v-for="evt in wsStore.openEvents.slice(0, 5)" :key="evt.id"
          class="flex items-center justify-between p-3 bg-dark-900/50 rounded-lg">
          <div>
            <p class="text-white text-sm font-medium">{{ evt.alert_name || '未知预警' }}</p>
            <p class="text-dark-400 text-xs mt-0.5">{{ evt.message }}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="px-2 py-1 rounded text-xs" :class="wsStore.getEventDisplayStatus(evt).color">
              {{ wsStore.getEventDisplayStatus(evt).label }}
            </span>
            <button v-if="evt.status === 'recovered'" @click="acknowledgeEvent(evt.id)"
              class="px-3 py-1 text-xs bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors">
              确认
            </button>
          </div>
        </div>
      </div>
      <router-link to="/events" class="block text-center text-primary-400 text-sm mt-3 hover:text-primary-300">查看全部事件 →</router-link>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <router-link to="/alerts" class="card hover:border-primary-500/50 transition-colors group">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 bg-primary-500/10 rounded-xl flex items-center justify-center group-hover:bg-primary-500/20 transition-colors">
            <svg class="w-6 h-6 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
          </div>
          <div>
            <p class="text-white font-medium group-hover:text-primary-400 transition-colors">预警管理</p>
            <p class="text-dark-400 text-sm">管理价格预警规则</p>
          </div>
        </div>
      </router-link>
      <router-link to="/events" class="card hover:border-yellow-500/50 transition-colors group">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 bg-yellow-500/10 rounded-xl flex items-center justify-center group-hover:bg-yellow-500/20 transition-colors">
            <svg class="w-6 h-6 text-yellow-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div>
            <p class="text-white font-medium group-hover:text-yellow-400 transition-colors">事件中心</p>
            <p class="text-dark-400 text-sm">查看和确认预警事件</p>
          </div>
        </div>
      </router-link>
      <router-link v-if="authStore.isAdmin" to="/users" class="card hover:border-green-500/50 transition-colors group">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 bg-green-500/10 rounded-xl flex items-center justify-center group-hover:bg-green-500/20 transition-colors">
            <svg class="w-6 h-6 text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
            </svg>
          </div>
          <div>
            <p class="text-white font-medium group-hover:text-green-400 transition-colors">用户管理</p>
            <p class="text-dark-400 text-sm">管理系统用户</p>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { useWsStore } from '../stores/ws'
import { useToastStore } from '../stores/toast'

const authStore = useAuthStore()
const wsStore = useWsStore()
const toast = useToastStore()

const priceData = ref({ price: 0, price_change_24h: 0, price_change_percentage_24h: 0, high_24h: 0, low_24h: 0, volume_24h: 0 })
const chartRef = ref(null)
let chart = null
let wsUnsub = null

const priceChange = computed(() => priceData.value.price_change_percentage_24h ?? 0)
const priceChangeAmount = computed(() => priceData.value.price_change_24h ?? 0)

const intervals = [
  { label: '1小时', value: '1h' },
  { label: '4小时', value: '4h' },
  { label: '1天', value: '1d' }
]
const selectedInterval = ref('1h')

function formatPrice(price) {
  if (!price) return '0.00'
  return Number(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function formatVolume(volume) {
  if (!volume) return '0'
  if (volume >= 1e9) return (volume / 1e9).toFixed(2) + 'B'
  if (volume >= 1e6) return (volume / 1e6).toFixed(2) + 'M'
  if (volume >= 1e3) return (volume / 1e3).toFixed(2) + 'K'
  return volume.toFixed(2)
}

async function acknowledgeEvent(id) {
  try {
    await api.post(`/api/alerts/events/${id}/acknowledge`)
    toast.success('已确认', '事件已标记为已处理')
  } catch (e) {
    toast.error('操作失败', e.response?.data?.detail || '请稍后重试')
  }
}

async function fetchPrice() {
  try {
    const response = await api.get('/api/price/current')
    priceData.value = response.data
  } catch (e) { console.error(e) }
}

async function fetchHistory() {
  try {
    const response = await api.get('/api/price/history', { params: { interval: selectedInterval.value, limit: 100 } })
    updateChart(response.data.data)
  } catch (e) { console.error(e) }
}

function updateChart(data) {
  if (!chart || !data) return
  const dates = data.map(item => {
    const d = new Date(item.timestamp)
    return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  })
  const prices = data.map(item => [item.open, item.close, item.low, item.high])
  const volumes = data.map(item => item.volume)
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' }, backgroundColor: '#1a1b1e', borderColor: '#3f4145', textStyle: { color: '#e2e3e5' } },
    grid: [{ left: '10%', right: '10%', top: '10%', height: '60%' }, { left: '10%', right: '10%', top: '75%', height: '15%' }],
    xAxis: [
      { type: 'category', data: dates, axisLine: { lineStyle: { color: '#3f4145' } }, axisLabel: { color: '#a0a2a8' } },
      { type: 'category', gridIndex: 1, data: dates, axisLine: { lineStyle: { color: '#3f4145' } }, axisLabel: { show: false } }
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { color: '#3f4145', type: 'dashed' } }, axisLine: { lineStyle: { color: '#3f4145' } }, axisLabel: { color: '#a0a2a8' } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, splitLine: { show: false } }
    ],
    series: [
      { name: 'K线', type: 'candlestick', data: prices, itemStyle: { color: '#10b981', color0: '#ef4444', borderColor: '#10b981', borderColor0: '#ef4444' } },
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes, itemStyle: { color: '#f07316', opacity: 0.5 } }
    ]
  })
}

watch(selectedInterval, () => fetchHistory())

onMounted(() => {
  fetchPrice()
  chart = echarts.init(chartRef.value)
  fetchHistory()
  wsUnsub = wsStore.onMessage((msg) => {
    if (msg.type === 'price_update' && msg.data) {
      priceData.value = msg.data
    }
  })
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  if (wsUnsub) wsUnsub()
  chart?.dispose()
})
</script>
