import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(null)

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin || false)

  function initAuth() {
    const savedToken = localStorage.getItem('token')
    const savedUser = localStorage.getItem('user')
    
    if (savedToken && savedUser) {
      token.value = savedToken
      user.value = JSON.parse(savedUser)
      api.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`
    }
  }

  async function login(username, password) {
    const response = await api.post('/api/auth/login', { username, password })
    const data = response.data
    
    token.value = data.access_token
    user.value = data.user
    
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
    
    return data
  }

  async function register(username, password, email) {
    const response = await api.post('/api/auth/register', { username, password, email })
    const data = response.data
    
    token.value = data.access_token
    user.value = data.user
    
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
    
    return data
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    delete api.defaults.headers.common['Authorization']
  }

  return {
    user,
    token,
    isAuthenticated,
    isAdmin,
    initAuth,
    login,
    register,
    logout
  }
})
