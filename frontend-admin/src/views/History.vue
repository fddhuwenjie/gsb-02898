<template>
  <div class="p-6 space-y-6">
    <!-- 页面标题 -->
    <div>
      <h1 class="text-2xl font-bold text-white">触发历史</h1>
      <p class="text-dark-400 mt-1">查看预警触发记录</p>
    </div>

    <!-- 历史列表 -->
    <div class="card">
      <div v-if="loading" class="text-center py-8 text-dark-400">
        加载中...
      </div>

      <div v-else-if="histories.length === 0" class="text-center py-12">
        <div class="w-16 h-16 bg-dark-800 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-dark-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <p class="text-dark-400">暂无触发记录</p>
        <p class="text-dark-500 text-sm mt-1">当预警被触发时，记录会显示在这里</p>
      </div>

      <div v-else class="space-y-4">
        <div
          v-for="history in histories"
          :key="history.id"
          class="p-4 bg-dark-900 rounded-lg border border-dark-800 hover:border-dark-700 transition-colors"
        >
          <div class="flex items-start justify-between">
            <div class="flex items-start gap-4">
              <div class="w-10 h-10 bg-primary-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
                <svg class="w-5 h-5 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                  <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
              </div>
              <div>
                <p class="text-white font-medium">{{ history.message }}</p>
                <p class="text-dark-400 text-sm mt-1">
                  触发价格: <span class="text-primary-400 font-mono">${{ formatPrice(history.triggered_price) }}</span>
                </p>
              </div>
            </div>
            <span class="text-dark-500 text-sm">{{ formatDate(history.triggered_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import api from '../api'

const histories = ref([])
const loading = ref(true)

function formatPrice(price) {
  if (!price) return '0.00'
  return Number(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(date) {
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchHistories() {
  try {
    const response = await api.get('/api/alerts/histories')
    histories.value = response.data
  } catch (error) {
    console.error('Failed to fetch histories:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchHistories()
})
</script>
