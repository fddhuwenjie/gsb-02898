<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">预警管理</h1>
        <p class="text-dark-400 mt-1">设置和管理价格预警规则，当前BTC价格 <span class="text-primary-400 font-mono">${{ formatPrice(currentPrice) }}</span></p>
      </div>
      <button @click="showModal = true" class="btn btn-primary flex items-center gap-2">
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        创建预警
      </button>
    </div>

    <div class="card">
      <h3 class="text-lg font-medium text-white mb-4">我的预警规则</h3>
      <div v-if="loading" class="text-center py-8 text-dark-400">加载中...</div>
      <div v-else-if="rules.length === 0" class="text-center py-12">
        <div class="w-16 h-16 bg-dark-800 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-dark-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
        </div>
        <p class="text-dark-400">暂无预警规则</p>
        <p class="text-dark-500 text-sm mt-1">点击上方按钮创建第一个预警</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>目标价格</th>
              <th>规则状态</th>
              <th>重复/冷却</th>
              <th>触发时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="rule in rules" :key="rule.id">
              <td class="font-medium text-white">
                {{ rule.name }}
                <div v-if="rule.open_event" class="text-xs text-dark-400 mt-0.5">{{ rule.open_event.message }}</div>
              </td>
              <td>
                <span class="px-2 py-1 rounded text-xs font-medium"
                  :class="rule.alert_type === 'above' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'">
                  {{ rule.alert_type === 'above' ? '价格上涨至' : '价格下跌至' }}
                </span>
              </td>
              <td class="font-mono text-white">${{ formatPrice(rule.target_price) }}</td>
              <td>
                <span class="px-2 py-1 rounded text-xs font-medium whitespace-nowrap" :class="wsStore.getRuleDisplayState(rule).color">
                  {{ wsStore.getRuleDisplayState(rule).label }}
                </span>
                <div v-if="rule.state === 'cooldown' && rule.cooldown_remaining" class="text-xs text-blue-400 mt-0.5">
                  剩余 {{ Math.ceil(rule.cooldown_remaining / 1000) }}s
                </div>
              </td>
              <td>
                <div class="text-sm">
                  <span :class="rule.is_repeat ? 'text-green-400' : 'text-dark-500'">{{ rule.is_repeat ? '重复触发' : '单次触发' }}</span>
                  <div class="text-xs text-dark-500">冷却 {{ rule.cooldown_seconds }}s</div>
                </div>
              </td>
              <td class="text-dark-400 text-sm">
                <div v-if="rule.last_triggered_at">{{ formatDate(rule.last_triggered_at) }}</div>
                <span v-else class="text-dark-600">未触发</span>
              </td>
              <td>
                <div class="flex items-center gap-2">
                  <button @click="toggleRule(rule)" class="p-2 hover:bg-dark-700 rounded-lg transition-colors"
                    :title="rule.state === 'disabled' ? '启用' : '禁用'">
                    <svg v-if="rule.state !== 'disabled'" class="w-4 h-4 text-yellow-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/><line x1="10" y1="15" x2="10" y2="9"/><line x1="14" y1="15" x2="14" y2="9"/>
                    </svg>
                    <svg v-else class="w-4 h-4 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                  </button>
                  <button @click="confirmDelete(rule.id)" class="p-2 hover:bg-dark-700 rounded-lg transition-colors text-red-400" title="删除">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="showModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div class="card w-full max-w-md">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-lg font-medium text-white">创建预警规则</h3>
          <button @click="closeModal" class="p-2 hover:bg-dark-700 rounded-lg transition-colors">
            <svg class="w-5 h-5 text-dark-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <form @submit.prevent="createAlert" class="space-y-4">
          <div>
            <label class="block text-sm text-dark-300 mb-2">预警名称</label>
            <input v-model="form.name" @blur="validateName" type="text" class="input"
              :class="{ 'border-red-500 focus:border-red-500': errors.name }" placeholder="例如：BTC突破10万" />
            <p v-if="errors.name" class="text-red-400 text-xs mt-1">{{ errors.name }}</p>
          </div>
          <div>
            <label class="block text-sm text-dark-300 mb-2">预警类型</label>
            <div class="grid grid-cols-2 gap-3">
              <button type="button" @click="form.alert_type = 'above'" class="p-4 rounded-lg border-2 transition-colors text-left"
                :class="form.alert_type === 'above' ? 'border-green-500 bg-green-500/10' : 'border-dark-700 hover:border-dark-600'">
                <svg class="w-6 h-6 text-green-400 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
                </svg>
                <p class="text-white font-medium">价格上涨</p>
                <p class="text-dark-400 text-xs mt-1">当价格高于目标时触发</p>
              </button>
              <button type="button" @click="form.alert_type = 'below'" class="p-4 rounded-lg border-2 transition-colors text-left"
                :class="form.alert_type === 'below' ? 'border-red-500 bg-red-500/10' : 'border-dark-700 hover:border-dark-600'">
                <svg class="w-6 h-6 text-red-400 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>
                </svg>
                <p class="text-white font-medium">价格下跌</p>
                <p class="text-dark-400 text-xs mt-1">当价格低于目标时触发</p>
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm text-dark-300 mb-2">目标价格 (USD)</label>
            <input v-model.number="form.target_price" @blur="validatePrice" type="number" step="0.01" min="0" class="input"
              :class="{ 'border-red-500 focus:border-red-500': errors.target_price }" placeholder="输入目标价格" />
            <p v-if="errors.target_price" class="text-red-400 text-xs mt-1">{{ errors.target_price }}</p>
            <p v-else class="text-dark-500 text-xs mt-1">当前价格: ${{ formatPrice(currentPrice) }}</p>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="flex items-center gap-3">
              <input v-model="form.is_repeat" type="checkbox" id="is_repeat" class="w-4 h-4 rounded border-dark-600 bg-dark-800 text-primary-500 focus:ring-primary-500" />
              <label for="is_repeat" class="text-sm text-dark-300">重复触发</label>
            </div>
            <div>
              <label class="block text-xs text-dark-400 mb-1">冷却时间(秒)</label>
              <input v-model.number="form.cooldown_seconds" type="number" min="10" max="3600" class="input !py-1.5 text-sm" />
            </div>
          </div>
          <div class="flex gap-3 pt-4">
            <button type="button" @click="closeModal" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1" :disabled="submitting || !isFormValid">
              {{ submitting ? '创建中...' : '创建预警' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <Transition name="modal">
      <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div class="card w-full max-w-sm text-center">
          <div class="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-white mb-2">确认删除</h3>
          <p class="text-dark-400 mb-6">删除后相关事件记录也将被移除，确定要删除这个预警规则吗？</p>
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
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import dayjs from 'dayjs'
import api from '../api'
import { useWsStore } from '../stores/ws'
import { useToastStore } from '../stores/toast'

const wsStore = useWsStore()
const toast = useToastStore()
const loading = ref(true)
const showModal = ref(false)
const submitting = ref(false)
const currentPrice = ref(0)
const showDeleteConfirm = ref(false)
const deleteTargetId = ref(null)
let cooldownTimer = null

const rules = computed(() => wsStore.rules)

const form = reactive({ name: '', alert_type: 'above', target_price: null, is_repeat: false, cooldown_seconds: 60 })
const errors = reactive({ name: '', target_price: '' })

const isFormValid = computed(() =>
  form.name.trim().length > 0 && form.target_price !== null && form.target_price > 0 &&
  form.cooldown_seconds >= 10 && form.cooldown_seconds <= 3600 && !errors.name && !errors.target_price
)

function validateName() {
  if (!form.name.trim()) errors.name = '请输入预警名称'
  else if (form.name.trim().length < 2) errors.name = '名称至少2个字符'
  else if (form.name.trim().length > 50) errors.name = '名称不能超过50个字符'
  else errors.name = ''
}
function validatePrice() {
  if (form.target_price === null || form.target_price === '') errors.target_price = '请输入目标价格'
  else if (form.target_price <= 0) errors.target_price = '价格必须大于0'
  else if (form.target_price > 10000000) errors.target_price = '价格不能超过1000万'
  else errors.target_price = ''
}
function formatPrice(p) { if (!p) return '0.00'; return Number(p).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
function formatDate(d) { return dayjs(d).format('YYYY-MM-DD HH:mm') }

function resetForm() {
  form.name = ''; form.alert_type = 'above'; form.target_price = null; form.is_repeat = false; form.cooldown_seconds = 60
  errors.name = ''; errors.target_price = ''
}

async function fetchAlerts() {
  try {
    const response = await api.get('/api/alerts')
    wsStore.rules = response.data
  } catch (error) {
    toast.error('获取预警列表失败', error.response?.data?.detail || '请稍后重试')
  } finally { loading.value = false }
}
async function fetchPrice() {
  try { const r = await api.get('/api/price/current'); currentPrice.value = r.data.price } catch (e) {}
}

async function createAlert() {
  validateName(); validatePrice()
  if (!isFormValid.value) { toast.warning('表单校验失败', '请检查输入内容'); return }
  submitting.value = true
  try {
    await api.post('/api/alerts', {
      name: form.name.trim(), alert_type: form.alert_type, target_price: Number(form.target_price),
      is_repeat: form.is_repeat, cooldown_seconds: Number(form.cooldown_seconds)
    })
    showModal.value = false; resetForm()
    toast.success('创建成功', '预警规则已创建，开始监控')
    await fetchAlerts()
  } catch (error) {
    toast.error('创建失败', error.response?.data?.detail || '请检查输入后重试')
  } finally { submitting.value = false }
}

async function toggleRule(rule) {
  const newState = rule.state === 'disabled' ? 'active' : 'disabled'
  try {
    await api.put(`/api/alerts/${rule.id}`, { state: newState })
    toast.success('状态已更新', newState === 'active' ? '预警已启用' : '预警已禁用')
  } catch (error) {
    toast.error('更新失败', error.response?.data?.detail || '请稍后重试')
  }
}

function confirmDelete(id) { deleteTargetId.value = id; showDeleteConfirm.value = true }
async function deleteAlert() {
  if (!deleteTargetId.value) return
  try {
    await api.delete(`/api/alerts/${deleteTargetId.value}`)
    toast.success('删除成功', '预警规则已删除')
    showDeleteConfirm.value = false; deleteTargetId.value = null
  } catch (error) {
    toast.error('删除失败', error.response?.data?.detail || '请稍后重试')
  }
}

function closeModal() { showModal.value = false; resetForm() }

function tickCooldowns() {
  const now = Date.now()
  wsStore.rules.forEach(r => {
    if (r.state === 'cooldown' && r.open_event && r.open_event.recovered_at) {
      const recoveredAt = new Date(r.open_event.recovered_at).getTime()
      const elapsed = now - recoveredAt
      r.cooldown_remaining = Math.max(0, r.cooldown_seconds * 1000 - elapsed)
    } else {
      r.cooldown_remaining = 0
    }
  })
}

onMounted(async () => {
  await fetchPrice()
  await fetchAlerts()
  cooldownTimer = setInterval(tickCooldowns, 1000)
  tickCooldowns()
})
onUnmounted(() => { if (cooldownTimer) clearInterval(cooldownTimer) })
</script>
