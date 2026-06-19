<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">仪表盘</h1>
        <p class="text-dark-400 mt-1">实时监控BTC行情与预警状态</p>
      </div>
      <div class="flex items-center gap-2 text-sm">
        <span
          class="w-2 h-2 rounded-full"
          :class="wsConnected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'"
        ></span>
        <span :class="wsConnected ? 'text-green-400' : 'text-yellow-400'">
          {{ wsConnected ? '实时连接中' : '连接中...' }}
        </span>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      <div class="card lg:col-span-2 bg-gradient-to-br from-dark-800 to-dark-900">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-dark-400 text-sm">BTC/USDT</p>
            <div class="flex items-baseline gap-3 mt-1">
              <span class="text-3xl font-bold text-white">${{ formatPrice(priceData.price) }}</span>
              <span
                class="text-base font-medium px-2 py-0.5 rounded"
                :class="priceData.price_change_percentage_24h >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'"
              >
                {{ priceData.price_change_percentage_24h >= 0 ? '+' : '' }}{{ priceData.price_change_percentage_24h?.toFixed(2) }}%
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
        <p class="text-xl font-semibold" :class="priceData.price_change_24h >= 0 ? 'text-green-400' : 'text-red-400'">
          {{ priceData.price_change_24h >= 0 ? '+' : '' }}${{ formatPrice(Math.abs(priceData.price_change_24h)) }}
        </p>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <router-link to="/alerts" class="card hover:border-green-500/50 transition-colors cursor-pointer">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-white">{{ alertStats.active }}</p>
            <p class="text-dark-400 text-sm">监控中</p>
          </div>
        </div>
      </router-link>

      <router-link to="/alerts?status=triggered" class="card hover:border-red-500/50 transition-colors cursor-pointer">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-red-500/10 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/>
              <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-white">{{ alertStats.triggered }}</p>
            <p class="text-dark-400 text-sm">已触发</p>
          </div>
        </div>
      </router-link>

      <router-link to="/alerts?status=recovered" class="card hover:border-yellow-500/50 transition-colors cursor-pointer">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-yellow-500/10 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-yellow-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-white">{{ alertStats.recovered }}</p>
            <p class="text-dark-400 text-sm">已恢复待确认</p>
          </div>
        </div>
      </router-link>

      <router-link to="/history" class="card hover:border-blue-500/50 transition-colors cursor-pointer">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div>
            <p class="text-2xl font-bold text-white">{{ alertStats.pendingEvents }}</p>
            <p class="text-dark-400 text-sm">待处理事件</p>
          </div>
        </div>
      </router-link>
    </div>

    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-4">
          <h3 class="text-lg font-medium text-white">价格走势</h3>
          <span class="text-dark-500 text-sm">成交量: {{ formatVolume(priceData.volume_24h) }}</span>
        </div>
      </div>
      <div ref="chartRef" class="h-72"></div>
    </div>

    <div v-if="recentAlerts.length > 0" class="card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-medium text-white">需要关注的预警</h3>
        <router-link to="/alerts" class="text-primary-400 text-sm hover:text-primary-300">
          查看全部 →
        </router-link>
      </div>
      <div class="space-y-3">
        <div
          v-for="alert in recentAlerts"
          :key="alert.id"
          class="p-3 rounded-lg border"
          :class="{
            'bg-red-500/5 border-red-500/20': alert.status === 'triggered',
            'bg-yellow-500/5 border-yellow-500/20': alert.status === 'recovered'
          }"
        >
          <div class="flex items-center justify-between">
            <div>
              <p class="text-white font-medium">{{ alert.name }}</p>
              <p class="text-dark-400 text-sm">
                {{ alert.alert_type === 'above' ? '上涨至' : '下跌至' }}
                <span class="font-mono">${{ formatPrice(alert.target_price) }}</span>
              </p>
            </div>
            <span
              class="px-2 py-0.5 rounded text-xs font-medium"
              :class="{
                'bg-red-500/10 text-red-400': alert.status === 'triggered',
                'bg-yellow-500/10 text-yellow-400': alert.status === 'recovered'
              }"
            >
              {{ alert.status === 'triggered' ? '已触发' : '已恢复' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { useWebSocket } from '../composables/useWebSocket'

const priceData = ref({
  price: 0,
  price_change_24h: 0,
  price_change_percentage_24h: 0,
  high_24h: 0,
  low_24h: 0,
  volume_24h: 0
})

const alerts = ref([])
const chartRef = ref(null)
let chart = null
let reconnectTimer = null

const { wsConnected, lastPrice, connect, disconnect, on, off } = useWebSocket()

const alertStats = computed(() => {
  const stats = { active: 0, triggered: 0, recovered: 0, cooldown: 0, pendingEvents: 0 }
  alerts.value.forEach(a => {
    if (a.status === 'active') stats.active++
    if (a.status === 'triggered') stats.triggered++
    if (a.status === 'recovered') {
      stats.recovered++
      stats.pendingEvents++
    }
    if (a.status === 'triggered') stats.pendingEvents++
  })
  return stats
})

const recentAlerts = computed(() => {
  return alerts.value.filter(a =>
    a.status === 'triggered' || a.status === 'recovered'
  ).slice(0, 5)
})

function formatPrice(price) {
  if (!price && price !== 0) return '0.00'
  return Number(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatVolume(volume) {
  if (!volume) return '0'
  if (volume >= 1e9) return (volume / 1e9).toFixed(2) + 'B'
  if (volume >= 1e6) return (volume / 1e6).toFixed(2) + 'M'
  if (volume >= 1e3) return (volume / 1e3).toFixed(2) + 'K'
  return volume.toFixed(2)
}

async function fetchPrice() {
  try {
    const response = await api.get('/api/price/current')
    priceData.value = response.data
  } catch (error) {
    console.error('Failed to fetch price:', error)
  }
}

async function fetchAlerts() {
  try {
    const response = await api.get('/api/alerts')
    alerts.value = response.data
  } catch (error) {
    console.error('Failed to fetch alerts:', error)
  }
}

async function fetchHistory() {
  try {
    const response = await api.get('/api/price/history', {
      params: { interval: '1h', limit: 100 }
    })
    updateChart(response.data.data)
  } catch (error) {
    console.error('Failed to fetch history:', error)
  }
}

function updateChart(data) {
  if (!chart || !data || !data.length) return

  const dates = data.map(item => {
    const date = new Date(item.timestamp)
    return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  })

  const prices = data.map(item => [item.open, item.close, item.low, item.high])
  const volumes = data.map(item => item.volume)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#1a1b1e',
      borderColor: '#3f4145',
      textStyle: { color: '#e2e3e5' }
    },
    grid: [
      { left: '8%', right: '5%', top: '5%', height: '65%' },
      { left: '8%', right: '5%', top: '78%', height: '15%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#3f4145' } },
        axisLabel: { color: '#a0a2a8', fontSize: 10 }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        axisLine: { lineStyle: { color: '#3f4145' } },
        axisLabel: { show: false }
      }
    ],
    yAxis: [
      {
        scale: true,
        splitLine: { lineStyle: { color: '#3f4145', type: 'dashed' } },
        axisLine: { lineStyle: { color: '#3f4145' } },
        axisLabel: { color: '#a0a2a8' }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: prices,
        itemStyle: {
          color: '#10b981',
          color0: '#ef4444',
          borderColor: '#10b981',
          borderColor0: '#ef4444'
        }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#f07316', opacity: 0.5 }
      }
    ]
  })
}

function handlePriceUpdate(data) {
  priceData.value = data
}

function handleAlertUpdate() {
  fetchAlerts()
}

onMounted(() => {
  fetchPrice()
  fetchAlerts()
  connect()

  chart = echarts.init(chartRef.value)
  fetchHistory()

  window.addEventListener('resize', () => chart?.resize())

  on('price_update', handlePriceUpdate)
  on('alert_triggered', handleAlertUpdate)
  on('alert_recovered', handleAlertUpdate)
  on('alert_state_changed', handleAlertUpdate)
})

onUnmounted(() => {
  if (reconnectTimer) clearTimeout(reconnectTimer)

  off('price_update', handlePriceUpdate)
  off('alert_triggered', handleAlertUpdate)
  off('alert_recovered', handleAlertUpdate)
  off('alert_state_changed', handleAlertUpdate)

  chart?.dispose()
})
</script>
