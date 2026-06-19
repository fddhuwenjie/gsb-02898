<template>
  <div class="p-6 space-y-6">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">预警管理</h1>
        <p class="text-dark-400 mt-1">每个用户可维护多组规则，触发后自动落库并产生事件</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="flex items-center gap-2 text-xs text-dark-400">
          <span
            class="w-2 h-2 rounded-full"
            :class="wsConnected ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'"
          ></span>
          {{ wsConnected ? '实时同步中' : '离线' }}
        </span>
        <button @click="openCreate" class="btn btn-primary flex items-center gap-2">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          创建预警
        </button>
      </div>
    </div>

    <!-- 当前价格 + 状态汇总 -->
    <div class="grid grid-cols-1 md:grid-cols-6 gap-4">
      <div class="card md:col-span-2 bg-gradient-to-r from-primary-500/10 to-transparent border-primary-500/20">
        <p class="text-dark-400 text-sm">BTC 当前价格</p>
        <p class="text-3xl font-bold text-white mt-1">${{ formatPrice(currentPrice) }}</p>
      </div>
      <div class="card">
        <p class="text-dark-400 text-xs">激活</p>
        <p class="text-2xl font-bold text-green-400 mt-1">{{ stats.active }}</p>
      </div>
      <div class="card">
        <p class="text-dark-400 text-xs">触发中</p>
        <p class="text-2xl font-bold text-red-400 mt-1">{{ stats.firing }}</p>
      </div>
      <div class="card">
        <p class="text-dark-400 text-xs">冷却中</p>
        <p class="text-2xl font-bold text-blue-300 mt-1">{{ stats.cooldown }}</p>
      </div>
      <div class="card">
        <p class="text-dark-400 text-xs">待确认</p>
        <p class="text-2xl font-bold text-yellow-400 mt-1">{{ stats.pending }}</p>
      </div>
    </div>

    <!-- 规则列表 -->
    <div class="card">
      <h3 class="text-lg font-medium text-white mb-4">我的规则</h3>

      <div v-if="loading" class="text-center py-8 text-dark-400">加载中...</div>

      <div v-else-if="alerts.length === 0" class="text-center py-12">
        <p class="text-dark-400">暂无预警，点击右上方按钮创建第一条规则</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>目标价</th>
              <th>规则状态</th>
              <th>冷却</th>
              <th>累计触发</th>
              <th>最近触发</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="alert in alerts" :key="alert.id">
              <td>
                <div class="font-medium text-white">{{ alert.name }}</div>
                <div class="text-xs text-dark-500">{{ alert.symbol }}</div>
              </td>
              <td>
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="alert.alert_type === 'above' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'"
                >
                  {{ alert.alert_type === 'above' ? '高于' : '低于' }}
                </span>
              </td>
              <td class="font-mono">${{ formatPrice(alert.target_price) }}</td>
              <td>
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="statusClass(alert.status)"
                >
                  {{ statusMap[alert.status] || alert.status }}
                </span>
                <div
                  v-if="cooldownRemaining(alert) > 0"
                  class="text-[10px] text-dark-400 mt-1"
                >
                  剩余冷却 {{ cooldownRemaining(alert) }}s
                </div>
              </td>
              <td class="text-dark-300 text-sm">{{ alert.cooldown_seconds }}s</td>
              <td class="text-dark-300 text-sm">{{ alert.trigger_count }}</td>
              <td class="text-dark-400 text-xs">
                {{ alert.last_triggered_at ? formatDate(alert.last_triggered_at) : '—' }}
              </td>
              <td>
                <div class="flex items-center gap-1">
                  <button
                    v-if="['firing','pending_ack'].includes(alert.status)"
                    @click="ackAll(alert)"
                    class="px-2 py-1 text-xs rounded bg-yellow-500/10 text-yellow-300 hover:bg-yellow-500/20"
                    title="确认该规则下全部未确认事件"
                  >
                    确认
                  </button>
                  <button
                    @click="toggleStatus(alert)"
                    class="p-2 hover:bg-dark-700 rounded-lg transition-colors"
                    :title="alert.status === 'disabled' ? '启用' : '禁用'"
                  >
                    <svg v-if="alert.status !== 'disabled'" class="w-4 h-4 text-yellow-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <line x1="10" y1="15" x2="10" y2="9"/>
                      <line x1="14" y1="15" x2="14" y2="9"/>
                    </svg>
                    <svg v-else class="w-4 h-4 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                  </button>
                  <button
                    @click="confirmDelete(alert.id)"
                    class="p-2 hover:bg-dark-700 rounded-lg transition-colors text-red-400"
                    title="删除"
                  >
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 创建预警弹窗 -->
    <div v-if="showModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card w-full max-w-md">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-lg font-medium text-white">创建预警</h3>
          <button @click="closeModal" class="p-2 hover:bg-dark-700 rounded-lg transition-colors">
            <svg class="w-5 h-5 text-dark-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <form @submit.prevent="createAlert" class="space-y-4">
          <div>
            <label class="block text-sm text-dark-300 mb-2">预警名称</label>
            <input
              v-model="form.name"
              type="text"
              class="input"
              placeholder="例如：BTC突破10万"
              maxlength="100"
            />
          </div>

          <div>
            <label class="block text-sm text-dark-300 mb-2">预警类型</label>
            <div class="grid grid-cols-2 gap-3">
              <button
                type="button"
                @click="form.alert_type = 'above'"
                class="p-3 rounded-lg border-2 transition-colors text-left"
                :class="form.alert_type === 'above' ? 'border-green-500 bg-green-500/10' : 'border-dark-700 hover:border-dark-600'"
              >
                <p class="text-white font-medium">价格高于</p>
                <p class="text-dark-400 text-xs mt-1">price ≥ 目标价</p>
              </button>
              <button
                type="button"
                @click="form.alert_type = 'below'"
                class="p-3 rounded-lg border-2 transition-colors text-left"
                :class="form.alert_type === 'below' ? 'border-red-500 bg-red-500/10' : 'border-dark-700 hover:border-dark-600'"
              >
                <p class="text-white font-medium">价格低于</p>
                <p class="text-dark-400 text-xs mt-1">price ≤ 目标价</p>
              </button>
            </div>
          </div>

          <div>
            <label class="block text-sm text-dark-300 mb-2">目标价格 (USD)</label>
            <input
              v-model.number="form.target_price"
              type="number"
              step="0.01"
              min="0"
              class="input"
              placeholder="输入目标价格"
            />
            <p class="text-dark-500 text-xs mt-1">当前: ${{ formatPrice(currentPrice) }}</p>
          </div>

          <div>
            <label class="block text-sm text-dark-300 mb-2">冷却时间（秒）</label>
            <input
              v-model.number="form.cooldown_seconds"
              type="number"
              min="10"
              max="86400"
              class="input"
            />
            <p class="text-dark-500 text-xs mt-1">同一规则两次触发的最小间隔，避免短时反复刷新</p>
          </div>

          <div class="flex items-center gap-3">
            <input v-model="form.is_repeat" type="checkbox" id="is_repeat"
              class="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500" />
            <label for="is_repeat" class="text-sm text-dark-300">允许冷却结束后再次触发</label>
          </div>

          <div class="flex gap-3 pt-4">
            <button type="button" @click="closeModal" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1" :disabled="submitting">
              {{ submitting ? '创建中...' : '创建预警' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <Transition name="modal">
      <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div class="card w-full max-w-sm text-center">
          <h3 class="text-xl font-semibold text-white mb-2">确认删除</h3>
          <p class="text-dark-400 mb-6">删除后将连同所有事件一起移除，确定要删除吗？</p>
          <div class="flex gap-3">
            <button @click="showDeleteConfirm = false" class="btn btn-secondary flex-1">取消</button>
            <button @click="deleteAlert" class="btn btn-danger flex-1">确认删除</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import dayjs from 'dayjs'
import api from '../api'
import { useToastStore } from '../stores/toast'
import { useAuthStore } from '../stores/auth'

const toast = useToastStore()
const authStore = useAuthStore()
const alerts = ref([])
const loading = ref(true)
const showModal = ref(false)
const submitting = ref(false)
const currentPrice = ref(0)
const showDeleteConfirm = ref(false)
const deleteTargetId = ref(null)
const wsConnected = ref(false)
const nowTs = ref(Date.now())

let ws = null
let reconnectTimer = null
let heartbeatTimer = null
let tickerTimer = null

const statusMap = {
  active: '激活',
  cooldown: '冷却中',
  firing: '已触发未恢复',
  pending_ack: '已恢复待确认',
  disabled: '已禁用'
}

const form = reactive({
  name: '',
  alert_type: 'above',
  target_price: null,
  is_repeat: true,
  cooldown_seconds: 300,
})

const stats = computed(() => {
  const s = { active: 0, cooldown: 0, firing: 0, pending: 0, disabled: 0 }
  for (const a of alerts.value) {
    if (a.status === 'active') s.active += 1
    else if (a.status === 'cooldown') s.cooldown += 1
    else if (a.status === 'firing') s.firing += 1
    else if (a.status === 'pending_ack') s.pending += 1
    else if (a.status === 'disabled') s.disabled += 1
  }
  return s
})

function statusClass(status) {
  switch (status) {
    case 'active': return 'bg-green-500/10 text-green-400'
    case 'firing': return 'bg-red-500/10 text-red-400 animate-pulse'
    case 'cooldown': return 'bg-blue-500/10 text-blue-300'
    case 'pending_ack': return 'bg-yellow-500/10 text-yellow-300'
    case 'disabled': return 'bg-dark-600 text-dark-400'
    default: return 'bg-dark-600 text-dark-400'
  }
}

function formatPrice(p) {
  if (!p && p !== 0) return '0.00'
  return Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(d) {
  return dayjs(d).format('MM-DD HH:mm:ss')
}

function cooldownRemaining(alert) {
  // 仅对 cooldown / pending_ack 显示，且需要 cooldown_until
  if (!alert.cooldown_until) return 0
  if (!['cooldown', 'pending_ack'].includes(alert.status)) return 0
  const left = Math.floor((new Date(alert.cooldown_until).getTime() - nowTs.value) / 1000)
  return left > 0 ? left : 0
}

function openCreate() {
  showModal.value = true
}

function resetForm() {
  form.name = ''
  form.alert_type = 'above'
  form.target_price = null
  form.is_repeat = true
  form.cooldown_seconds = 300
}

function closeModal() {
  showModal.value = false
  resetForm()
}

async function fetchAlerts() {
  try {
    const response = await api.get('/api/alerts')
    alerts.value = response.data
  } catch (error) {
    toast.error('获取预警失败', error.response?.data?.detail || '请稍后重试')
  } finally {
    loading.value = false
  }
}

async function fetchPrice() {
  try {
    const response = await api.get('/api/price/current')
    currentPrice.value = response.data.price
  } catch (e) { /* ignore */ }
}

async function createAlert() {
  if (!form.name.trim()) {
    toast.warning('请填写名称')
    return
  }
  if (!form.target_price || form.target_price <= 0) {
    toast.warning('请填写有效目标价')
    return
  }
  submitting.value = true
  try {
    await api.post('/api/alerts', {
      name: form.name.trim(),
      alert_type: form.alert_type,
      target_price: Number(form.target_price),
      is_repeat: form.is_repeat,
      cooldown_seconds: Number(form.cooldown_seconds) || 300,
    })
    closeModal()
    toast.success('创建成功')
    await fetchAlerts()
  } catch (error) {
    toast.error('创建失败', error.response?.data?.detail || '请稍后重试')
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(item) {
  const newStatus = item.status === 'disabled' ? 'active' : 'disabled'
  try {
    await api.put(`/api/alerts/${item.id}`, { status: newStatus })
    toast.success(newStatus === 'active' ? '已启用' : '已禁用')
    await fetchAlerts()
  } catch (error) {
    toast.error('更新失败', error.response?.data?.detail)
  }
}

async function ackAll(item) {
  try {
    const res = await api.post(`/api/alerts/${item.id}/ack-all`)
    toast.success('已确认', `共确认 ${res.data?.data?.acked ?? 0} 条事件`)
    await fetchAlerts()
  } catch (error) {
    toast.error('确认失败', error.response?.data?.detail)
  }
}

function confirmDelete(id) {
  deleteTargetId.value = id
  showDeleteConfirm.value = true
}

async function deleteAlert() {
  if (!deleteTargetId.value) return
  try {
    await api.delete(`/api/alerts/${deleteTargetId.value}`)
    toast.success('删除成功')
    showDeleteConfirm.value = false
    deleteTargetId.value = null
    await fetchAlerts()
  } catch (error) {
    toast.error('删除失败', error.response?.data?.detail)
  }
}

// ----- WebSocket：实时同步规则状态 -----
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
      if (msg.type === 'price_update') {
        currentPrice.value = msg.data.price
      } else if (msg.type === 'alert_triggered' || msg.type === 'alert_resolved') {
        // 服务端已经落库，这里只刷新规则列表保持一致
        const a = msg.data?.alert
        if (a) {
          const idx = alerts.value.findIndex(x => x.id === a.id)
          if (idx !== -1) {
            alerts.value[idx] = { ...alerts.value[idx], ...a }
          }
        }
        if (msg.type === 'alert_triggered') {
          toast.warning(`🔔 ${a?.name || '预警'} 已触发`,
            `当前价格 $${formatPrice(msg.data?.current_price)}`)
        } else {
          toast.info(`✅ ${a?.name || '预警'} 已恢复`,
            `当前价格 $${formatPrice(msg.data?.current_price)}`)
        }
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
  fetchAlerts()
  fetchPrice()
  connectWebSocket()
  // 每秒刷新时间戳，让"剩余冷却"自然滚动；冷却到 0 时主动拉一次让状态变 ACTIVE
  tickerTimer = setInterval(() => {
    const before = nowTs.value
    nowTs.value = Date.now()
    const justExpired = alerts.value.some(a =>
      a.cooldown_until &&
      ['cooldown', 'pending_ack'].includes(a.status) &&
      new Date(a.cooldown_until).getTime() <= nowTs.value &&
      new Date(a.cooldown_until).getTime() > before
    )
    if (justExpired) fetchAlerts()
  }, 1000)
})

onUnmounted(() => {
  if (ws) ws.close()
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  if (tickerTimer) clearInterval(tickerTimer)
})
</script>
