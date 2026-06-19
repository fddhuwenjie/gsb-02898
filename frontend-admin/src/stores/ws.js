import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'
import { useToastStore } from './toast'

export const useWsStore = defineStore('ws', () => {
  const connected = ref(false)
  const rules = ref([])
  const openEvents = ref([])
  const stats = ref({
    total_events: 0,
    open_triggered: 0,
    recovered_pending: 0,
    active_rules: 0,
    triggered_rules: 0,
    cooldown_rules: 0
  })

  let ws = null
  let reconnectTimer = null
  let heartbeatTimer = null
  const listeners = new Set()

  function onMessage(handler) {
    listeners.add(handler)
    return () => listeners.delete(handler)
  }

  function _dispatch(message) {
    listeners.forEach(h => {
      try { h(message) } catch (e) { console.error('WS handler error:', e) }
    })
  }

  function _findRule(id) {
    return rules.value.find(r => r.id === id)
  }

  function _findEvent(id) {
    return openEvents.value.find(e => e.id === id)
  }

  function _handleMessage(msg) {
    const toast = useToastStore()
    const type = msg.type
    const data = msg.data

    switch (type) {
      case 'price_update':
        _dispatch(msg)
        break
      case 'rules_init':
        rules.value = Array.isArray(data) ? data : []
        _dispatch(msg)
        break
      case 'events_init':
        openEvents.value = Array.isArray(data) ? data : []
        _dispatch(msg)
        break
      case 'stats_update':
        if (data) stats.value = { ...stats.value, ...data }
        _dispatch(msg)
        break
      case 'alert_triggered':
        if (data) {
          toast.warning(`🔔 ${data.alert_name || '预警触发'}`, data.message || `触发价格: $${Number(data.trigger_price).toLocaleString()}`)
          const existing = _findEvent(data.id)
          if (!existing) {
            openEvents.value.unshift(data)
          } else {
            Object.assign(existing, data)
          }
          if (data.alert_id) {
            const rule = _findRule(data.alert_id)
            if (rule) {
              rule.state = 'triggered'
              rule.open_event = data
              rule.current_trigger_price = data.trigger_price
              rule.current_trigger_at = data.triggered_at
              rule.last_triggered_at = data.triggered_at
            }
          }
        }
        _dispatch(msg)
        break
      case 'alert_recovered':
        if (data) {
          toast.info(`✅ ${data.alert_name || '预警恢复'}`, data.message || '价格已恢复到安全区间')
          const ev = _findEvent(data.id)
          if (ev) {
            Object.assign(ev, data)
          } else {
            openEvents.value.unshift(data)
          }
          if (data.alert_id) {
            const rule = _findRule(data.alert_id)
            if (rule) {
              rule.open_event = data
              rule.current_trigger_price = null
              rule.current_trigger_at = null
            }
          }
        }
        _dispatch(msg)
        break
      case 'event_acknowledged':
        if (data) {
          openEvents.value = openEvents.value.filter(e => e.id !== data.id)
          toast.success('事件已确认', `${data.alert_name || ''} 事件已标记为已处理`)
        }
        _dispatch(msg)
        break
      case 'rule_state_changed':
        if (data) {
          const existing = _findRule(data.id)
          if (existing) {
            Object.assign(existing, data)
          } else {
            rules.value.push(data)
          }
        }
        _dispatch(msg)
        break
      case 'rule_deleted':
        if (data) {
          rules.value = rules.value.filter(r => r.id !== data.id)
          openEvents.value = openEvents.value.filter(e => e.alert_id !== data.id)
        }
        _dispatch(msg)
        break
      default:
        _dispatch(msg)
    }
  }

  function connect() {
    const auth = useAuthStore()
    if (!auth.token) {
      connected.value = false
      return
    }
    disconnect()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/price?token=${encodeURIComponent(auth.token)}`
    ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      connected.value = true
      heartbeatTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 30000)
    }
    ws.onmessage = (event) => {
      if (event.data === 'pong') return
      try {
        const msg = JSON.parse(event.data)
        _handleMessage(msg)
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }
    ws.onclose = () => {
      connected.value = false
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
      if (auth.token) {
        reconnectTimer = setTimeout(connect, 5000)
      }
    }
    ws.onerror = () => {}
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (ws) {
      try { ws.close() } catch (e) {}
      ws = null
    }
    connected.value = false
  }

  function reset() {
    disconnect()
    rules.value = []
    openEvents.value = []
    stats.value = {
      total_events: 0,
      open_triggered: 0,
      recovered_pending: 0,
      active_rules: 0,
      triggered_rules: 0,
      cooldown_rules: 0
    }
    listeners.clear()
  }

  async function acknowledgeEvent(eventId, api) {
    await api.post(`/api/alerts/events/${eventId}/acknowledge`)
  }

  function getRuleDisplayState(rule) {
    if (!rule) return { label: '未知', color: 'bg-dark-600 text-dark-400' }
    const openEvt = rule.open_event
    if (rule.state === 'disabled') return { label: '已禁用', color: 'bg-dark-600 text-dark-400' }
    if (rule.state === 'cooldown') return { label: '冷却中', color: 'bg-blue-500/10 text-blue-400' }
    if (rule.state === 'triggered') {
      if (openEvt && openEvt.status === 'recovered') {
        return { label: '已恢复待确认', color: 'bg-yellow-500/10 text-yellow-400' }
      }
      return { label: '已触发未恢复', color: 'bg-red-500/10 text-red-400' }
    }
    if (rule.needs_reset) {
      return { label: '待价格回归', color: 'bg-orange-500/10 text-orange-400' }
    }
    return { label: '监控中', color: 'bg-green-500/10 text-green-400' }
  }

  function getEventDisplayStatus(event) {
    if (!event) return { label: '未知', color: 'bg-dark-600 text-dark-400' }
    switch (event.status) {
      case 'triggered': return { label: '已触发', color: 'bg-red-500/10 text-red-400' }
      case 'recovered': return { label: '待确认', color: 'bg-yellow-500/10 text-yellow-400' }
      case 'acknowledged': return { label: '已确认', color: 'bg-green-500/10 text-green-400' }
      default: return { label: event.status, color: 'bg-dark-600 text-dark-400' }
    }
  }

  return {
    connected, rules, openEvents, stats,
    onMessage, connect, disconnect, reset, acknowledgeEvent,
    getRuleDisplayState, getEventDisplayStatus
  }
})
