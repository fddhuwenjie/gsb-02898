<template>
  <div class="fixed top-6 right-6 z-50 flex flex-col gap-3">
    <Toast
      v-for="toast in toastStore.toasts"
      :key="toast.id"
      :type="toast.type"
      :title="toast.title"
      :message="toast.message"
      :duration="toast.duration"
      @close="toastStore.remove(toast.id)"
    />
  </div>
</template>

<script setup>
import { useToastStore } from '../stores/toast'
import Toast from './Toast.vue'

const toastStore = useToastStore()
</script>
