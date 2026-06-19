<template>
  <div class="flex h-screen">
    <aside class="w-64 bg-dark-900 border-r border-dark-800 flex flex-col">
      <div class="p-6 border-b border-dark-800">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-primary-500 rounded-xl flex items-center justify-center">
            <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12.5 3.5c-4.1 0-7.5 3.4-7.5 7.5s3.4 7.5 7.5 7.5 7.5-3.4 7.5-7.5-3.4-7.5-7.5-7.5zm.5 11.5h-1v-1h1v1zm0-2h-1v-4h1v4z"/>
            </svg>
          </div>
          <div>
            <h1 class="text-lg font-bold text-white">BTC Monitor</h1>
            <p class="text-xs text-dark-400">预警中心 v2.0</p>
          </div>
        </div>
      </div>

      <nav class="flex-1 p-4 space-y-2">
        <router-link v-for="item in menuItems" :key="item.path" :to="item.path"
          class="flex items-center gap-3 px-4 py-3 rounded-lg transition-colors relative"
          :class="[
            $route.path === item.path || (item.path === '/events' && $route.path === '/history')
              ? 'bg-primary-500/10 text-primary-500'
              : 'text-dark-300 hover:bg-dark-800 hover:text-white'
          ]">
          <component :is="item.icon" class="w-5 h-5" />
          <span>{{ item.name }}</span>
          <span v-if="item.badge && item.badge() > 0"
            class="ml-auto px-2 py-0.5 text-xs rounded-full bg-red-500 text-white font-medium">
            {{ item.badge() }}
          </span>
        </router-link>
      </nav>

      <div class="p-4 border-t border-dark-800">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-10 h-10 bg-dark-700 rounded-full flex items-center justify-center">
            <span class="text-sm font-medium">{{ authStore.user?.username?.charAt(0).toUpperCase() }}</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-white truncate">{{ authStore.user?.username }}</p>
            <p class="text-xs text-dark-400">{{ authStore.isAdmin ? '管理员' : '用户' }}</p>
          </div>
        </div>
        <button @click="handleLogout" class="w-full px-4 py-2 text-sm text-dark-300 hover:text-white hover:bg-dark-800 rounded-lg transition-colors">
          退出登录
        </button>
      </div>
    </aside>

    <main class="flex-1 overflow-auto">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, h } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useWsStore } from '../stores/ws'

const router = useRouter()
const authStore = useAuthStore()
const wsStore = useWsStore()

const DashboardIcon = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('rect', { x: '3', y: '3', width: '7', height: '7', rx: '1' }),
  h('rect', { x: '14', y: '3', width: '7', height: '7', rx: '1' }),
  h('rect', { x: '3', y: '14', width: '7', height: '7', rx: '1' }),
  h('rect', { x: '14', y: '14', width: '7', height: '7', rx: '1' })
])
const AlertIcon = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('path', { d: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9' }),
  h('path', { d: 'M13.73 21a2 2 0 0 1-3.46 0' })
])
const EventIcon = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('circle', { cx: '12', cy: '12', r: '10' }),
  h('polyline', { points: '12 6 12 12 16 14' })
])
const UsersIcon = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
  h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: '9', cy: '7', r: '4' }),
  h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
  h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
])

const pendingCount = () => wsStore.stats.open_triggered + wsStore.stats.recovered_pending

const menuItems = computed(() => {
  const items = [
    { path: '/', name: '仪表盘', icon: DashboardIcon, badge: null },
    { path: '/alerts', name: '预警管理', icon: AlertIcon, badge: null },
    { path: '/events', name: '事件中心', icon: EventIcon, badge: pendingCount }
  ]
  if (authStore.isAdmin) {
    items.push({ path: '/users', name: '用户管理', icon: UsersIcon, badge: null })
  }
  return items
})

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>
