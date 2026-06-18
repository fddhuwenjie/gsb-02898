<template>
  <div class="min-h-screen flex items-center justify-center bg-dark-950 p-4">
    <!-- 背景装饰 -->
    <div class="absolute inset-0 overflow-hidden">
      <div class="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/10 rounded-full blur-3xl"></div>
      <div class="absolute -bottom-40 -left-40 w-80 h-80 bg-primary-500/5 rounded-full blur-3xl"></div>
    </div>

    <div class="relative w-full max-w-md">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 bg-primary-500 rounded-2xl mb-4 animate-pulse-glow">
          <svg class="w-10 h-10 text-white" viewBox="0 0 32 32" fill="currentColor">
            <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" stroke-width="2"/>
            <path d="M22.5 14.1c.3-2-1.2-3.1-3.3-3.8l.7-2.7-1.6-.4-.7 2.6c-.4-.1-.8-.2-1.3-.3l.7-2.6-1.6-.4-.7 2.7c-.3-.1-.7-.2-1-.3l-2.2-.5-.4 1.7s1.2.3 1.2.3c.7.2.8.6.8 1l-.8 3.2c0 0 .1 0 .2.1-.1 0-.1 0-.2 0l-1.1 4.5c-.1.2-.3.5-.8.4 0 0-1.2-.3-1.2-.3l-.8 1.8 2.1.5c.4.1.8.2 1.2.3l-.7 2.7 1.6.4.7-2.7c.4.1.9.2 1.3.3l-.7 2.7 1.6.4.7-2.7c2.8.5 4.9.3 5.8-2.2.7-2-.1-3.2-1.5-3.9 1.1-.3 1.9-1 2.1-2.5z"/>
          </svg>
        </div>
        <h1 class="text-3xl font-bold text-white mb-2">BTC Monitor</h1>
        <p class="text-dark-400">行情监控预警系统</p>
      </div>

      <!-- 登录表单 -->
      <div class="card">
        <div class="flex mb-6">
          <button
            @click="isLogin = true"
            class="flex-1 py-2 text-center transition-colors"
            :class="isLogin ? 'text-primary-500 border-b-2 border-primary-500' : 'text-dark-400 border-b border-dark-700'"
          >
            登录
          </button>
          <button
            @click="isLogin = false"
            class="flex-1 py-2 text-center transition-colors"
            :class="!isLogin ? 'text-primary-500 border-b-2 border-primary-500' : 'text-dark-400 border-b border-dark-700'"
          >
            注册
          </button>
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-sm text-dark-300 mb-2">用户名</label>
            <input
              v-model="form.username"
              type="text"
              class="input"
              placeholder="请输入用户名"
              required
            />
          </div>

          <div v-if="!isLogin">
            <label class="block text-sm text-dark-300 mb-2">邮箱（可选）</label>
            <input
              v-model="form.email"
              type="email"
              class="input"
              placeholder="请输入邮箱"
            />
          </div>

          <div>
            <label class="block text-sm text-dark-300 mb-2">密码</label>
            <input
              v-model="form.password"
              type="password"
              class="input"
              placeholder="请输入密码"
              required
            />
          </div>

          <div v-if="error" class="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            {{ error }}
          </div>

          <button
            type="submit"
            class="btn btn-primary w-full py-3"
            :disabled="loading"
          >
            {{ loading ? '处理中...' : (isLogin ? '登录' : '注册') }}
          </button>
        </form>
      </div>

      <!-- 版权信息 -->
      <p class="text-center text-dark-500 text-xs mt-6">© 2026 BTC Monitor. All rights reserved.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isLogin = ref(true)
const loading = ref(false)
const error = ref('')

const form = reactive({
  username: '',
  password: '',
  email: ''
})

async function handleSubmit() {
  loading.value = true
  error.value = ''

  try {
    if (isLogin.value) {
      await authStore.login(form.username, form.password)
    } else {
      await authStore.register(form.username, form.password, form.email || undefined)
    }
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>
