<template>
  <div class="p-6 space-y-6">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">仪表盘</h1>
        <p class="text-dark-400 mt-1">实时监控BTC行情数据</p>
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

    <!-- 价格概览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      <!-- 当前价格 - 大卡片 -->
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

      <!-- 24h 最高 -->
      <div class="card">
        <p class="text-dark-400 text-xs mb-1">24h 最高</p>
        <p class="text-xl font-semibold text-white">${{ formatPrice(priceData.high_24h) }}</p>
      </div>

      <!-- 24h 最低 -->
      <div class="card">
        <p class="text-dark-400 text-xs mb-1">24h 最低</p>
        <p class="text-xl font-semibold text-white">${{ formatPrice(priceData.low_24h) }}</p>
      </div>

      <!-- 24h 涨跌额 -->
      <div class="card">
        <p class="text-dark-400 text-xs mb-1">24h 涨跌</p>
        <p class="text-xl font-semibold" :class="priceData.price_change_24h >= 0 ? 'text-green-400' : 'text-red-400'">
          {{ priceData.price_change_24h >= 0 ? '+' : '' }}${{ formatPrice(Math.abs(priceData.price_change_24h)) }}
        </p>
      </div>
    </div>

    <!-- K线图 -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-4">
          <h3 class="text-lg font-medium text-white">价格走势</h3>
          <span class="text-dark-500 text-sm">成交量: {{ formatVolume(priceData.volume_24h) }}</span>
        </div>
        <div class="flex gap-1 bg-dark-900 p-1 rounded-lg">
          <button
            v-for="interval in intervals"
            :key="interval.value"
            @click="selectedInterval = interval.value"
            class="px-3 py-1.5 text-sm rounded-md transition-colors"
            :class="selectedInterval === interval.value ? 'bg-primary-500 text-white' : 'text-dark-400 hover:text-white'"
          >
            {{ interval.label }}
          </button>
        </div>
      </div>
      <div ref="chartRef" class="h-80"></div>
    </div>

    <!-- 快速操作 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <router-link to="/alerts" class="card hover:border-primary-500/50 transition-colors group">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 bg-primary-500/10 rounded-xl flex items-center justify-center group-hover:bg-primary-500/20 transition-colors">
            <svg class="w-6 h-6 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
          </div>
          <div>
            <p class="text-white font-medium group-hover:text-primary-400 transition-colors">创建预警</p>
            <p class="text-dark-400 text-sm">设置价格预警，及时获取通知</p>
          </div>
          <svg class="w-5 h-5 text-dark-500 ml-auto group-hover:text-primary-400 transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>
      </router-link>
      <router-link to="/history" class="card hover:border-green-500/50 transition-colors group">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 bg-green-500/10 rounded-xl flex items-center justify-center group-hover:bg-green-500/20 transition-colors">
            <svg class="w-6 h-6 text-green-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          </div>
          <div>
            <p class="text-white font-medium group-hover:text-green-400 transition-colors">触发历史</p>
            <p class="text-dark-400 text-sm">查看预警触发记录</p>
          </div>
          <svg class="w-5 h-5 text-dark-500 ml-auto group-hover:text-green-400 transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { useToastStore } from '../stores/toast'

const toast = useToastStore()

const priceData = ref({
  price: 0,
  price_change_24h: 0,
  price_change_percentage_24h: 0,
  high_24h: 0,
  low_24h: 0,
  volume_24h: 0
})

const chartRef = ref(null)
const wsConnected = ref(false)
let chart = null
let ws = null
let reconnectTimer = null
let heartbeatTimer = null

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

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/price`
  
  ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log('WebSocket connected')
    wsConnected.value = true
    
    // 启动心跳
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000)
  }
  
  ws.onmessage = (event) => {
    try {
      if (event.data === 'pong') return
      
      const message = JSON.parse(event.data)
      
      if (message.type === 'price_update' && message.data) {
        priceData.value = message.data
      } else if (message.type === 'alert_triggered' && message.data) {
        // 显示预警通知
        toast.warning(
          `🔔 ${message.data.alert_name}`,
          message.data.message || `当前价格: $${formatPrice(message.data.current_price)}`
        )
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e)
    }
  }
  
  ws.onclose = () => {
    console.log('WebSocket disconnected')
    wsConnected.value = false
    clearInterval(heartbeatTimer)
    
    // 5秒后重连
    reconnectTimer = setTimeout(connectWebSocket, 5000)
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
  }
}

async function fetchPrice() {
  try {
    const response = await api.get('/api/price/current')
    priceData.value = response.data
  } catch (error) {
    console.error('Failed to fetch price:', error)
  }
}

async function fetchHistory() {
  try {
    const response = await api.get('/api/price/history', {
      params: { interval: selectedInterval.value, limit: 100 }
    })
    updateChart(response.data.data)
  } catch (error) {
    console.error('Failed to fetch history:', error)
  }
}

function updateChart(data) {
  if (!chart) return

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
      { left: '10%', right: '10%', top: '10%', height: '60%' },
      { left: '10%', right: '10%', top: '75%', height: '15%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#3f4145' } },
        axisLabel: { color: '#a0a2a8' }
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

watch(selectedInterval, () => {
  fetchHistory()
})

onMounted(() => {
  // 先获取一次价格
  fetchPrice()
  
  // 连接WebSocket实时推送
  connectWebSocket()

  chart = echarts.init(chartRef.value)
  fetchHistory()

  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  // 清理WebSocket
  if (ws) {
    ws.close()
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
  }
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
  }
  
  chart?.dispose()
})
</script>
