<template>
  <div class="min-h-screen">
    <router-view />
    <ToastContainer />
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import { useAuthStore } from './stores/auth'
import { useWsStore } from './stores/ws'
import ToastContainer from './components/ToastContainer.vue'

const authStore = useAuthStore()
const wsStore = useWsStore()

onMounted(() => {
  authStore.initAuth()
})

watch(() => authStore.isAuthenticated, (isAuth) => {
  if (isAuth) {
    wsStore.connect()
  } else {
    wsStore.reset()
  }
}, { immediate: true })
</script>
