import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])
  let id = 0

  function show({ type = 'info', title, message = '', duration = 4000 }) {
    const toastId = ++id
    toasts.value.push({ id: toastId, type, title, message, duration })
    return toastId
  }

  function remove(toastId) {
    const index = toasts.value.findIndex(t => t.id === toastId)
    if (index > -1) {
      toasts.value.splice(index, 1)
    }
  }

  function success(title, message = '') {
    return show({ type: 'success', title, message })
  }

  function error(title, message = '') {
    return show({ type: 'error', title, message })
  }

  function warning(title, message = '') {
    return show({ type: 'warning', title, message })
  }

  function info(title, message = '') {
    return show({ type: 'info', title, message })
  }

  return { toasts, show, remove, success, error, warning, info }
})
