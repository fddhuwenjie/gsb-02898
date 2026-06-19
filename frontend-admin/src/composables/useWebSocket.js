import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'

export function useWebSocket() {
  const authStore = useAuthStore()
  const toast = useToastStore()

  const wsConnected = ref(false)
  const lastPrice = ref(null)
  let ws = null
  let reconnectTimer = null
  let heartbeatTimer = null
  const listeners = {
    price_update: [],
    alert_triggered: [],
    alert_recovered: [],
    alert_state_changed: []
  }

  function on(event, callback) {
    if (listeners[event]) {
      listeners[event].push(callback)
    }
  }

  function off(event, callback) {
    if (listeners[event]) {
      listeners[event] = listeners[event].filter(cb => cb !== callback)
    }
  }

  function emit(event, data) {
    if (listeners[event]) {
      listeners[event].forEach(cb => cb(data))
    }
  }

  function connect() {
    if (!authStore.token) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/price?token=${encodeURIComponent(authStore.token)}`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      wsConnected.value = true

      heartbeatTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 30000)
    }

    ws.onmessage = (event) => {
      if (event.data === 'pong') return

      try {
        const message = JSON.parse(event.data)

        if (message.type === 'price_update' && message.data) {
          lastPrice.value = message.data
          emit('price_update', message.data)
        } else if (message.type === 'alert_triggered' && message.data) {
          toast.warning(
            `🔔 ${message.data.alert_name}`,
            message.data.message || `当前价格: $${Number(message.data.current_price).toLocaleString()}`
          )
          emit('alert_triggered', message.data)
        } else if (message.type === 'alert_recovered' && message.data) {
          toast.info(
            `✅ ${message.data.alert_name}`,
            message.data.message || '价格已恢复'
          )
          emit('alert_recovered', message.data)
        } else if (message.type === 'alert_state_changed' && message.data) {
          emit('alert_state_changed', message.data)
        } else if (message.type === 'error') {
          console.error('WebSocket error:', message.data)
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onclose = (event) => {
      wsConnected.value = false
      clearInterval(heartbeatTimer)

      if (event.code !== 4001) {
        reconnectTimer = setTimeout(connect, 5000)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
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
      ws.close()
      ws = null
    }
    wsConnected.value = false
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    wsConnected,
    lastPrice,
    connect,
    disconnect,
    on,
    off
  }
}
