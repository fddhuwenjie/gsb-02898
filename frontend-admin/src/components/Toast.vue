<template>
  <Teleport to="body">
    <Transition name="toast">
      <div
        v-if="visible"
        class="fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-4 rounded-xl shadow-2xl backdrop-blur-sm border max-w-md"
        :class="typeClasses"
      >
        <!-- 图标 -->
        <div class="flex-shrink-0">
          <svg v-if="type === 'success'" class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          <svg v-else-if="type === 'error'" class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <svg v-else-if="type === 'warning'" class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <svg v-else class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        </div>

        <!-- 内容 -->
        <div class="flex-1 min-w-0">
          <p class="font-medium">{{ title }}</p>
          <p v-if="message" class="text-sm opacity-80 mt-0.5">{{ message }}</p>
        </div>

        <!-- 关闭按钮 -->
        <button @click="close" class="flex-shrink-0 p-1 rounded-lg hover:bg-white/10 transition-colors">
          <svg class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>

        <!-- 进度条 -->
        <div class="absolute bottom-0 left-0 right-0 h-1 rounded-b-xl overflow-hidden bg-black/10">
          <div
            class="h-full bg-current opacity-40 transition-all ease-linear"
            :style="{ width: `${progress}%` }"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  type: { type: String, default: 'info' },
  title: { type: String, required: true },
  message: { type: String, default: '' },
  duration: { type: Number, default: 4000 }
})

const emit = defineEmits(['close'])

const visible = ref(false)
const progress = ref(100)
let timer = null
let progressTimer = null

const typeClasses = computed(() => {
  const classes = {
    success: 'bg-emerald-500/90 border-emerald-400/30 text-white',
    error: 'bg-red-500/90 border-red-400/30 text-white',
    warning: 'bg-amber-500/90 border-amber-400/30 text-white',
    info: 'bg-blue-500/90 border-blue-400/30 text-white'
  }
  return classes[props.type] || classes.info
})

function close() {
  visible.value = false
  setTimeout(() => emit('close'), 300)
}

onMounted(() => {
  visible.value = true
  
  if (props.duration > 0) {
    const interval = 20
    const step = (100 / props.duration) * interval
    
    progressTimer = setInterval(() => {
      progress.value -= step
      if (progress.value <= 0) {
        clearInterval(progressTimer)
      }
    }, interval)
    
    timer = setTimeout(close, props.duration)
  }
})

onUnmounted(() => {
  if (timer) clearTimeout(timer)
  if (progressTimer) clearInterval(progressTimer)
})
</script>

<style scoped>
.toast-enter-active {
  animation: toast-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-leave-active {
  animation: toast-out 0.3s cubic-bezier(0.4, 0, 1, 1);
}

@keyframes toast-in {
  0% {
    opacity: 0;
    transform: translateX(100%) scale(0.9);
  }
  100% {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}

@keyframes toast-out {
  0% {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateX(100%) scale(0.9);
  }
}
</style>
