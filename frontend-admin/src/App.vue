<template>
  <div class="min-h-screen">
    <router-view />
    <ToastContainer />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import ToastContainer from './components/ToastContainer.vue'

const authStore = useAuthStore()

onMounted(() => {
  authStore.initAuth()
})
</script>
