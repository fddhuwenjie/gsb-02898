<template>
  <div class="p-6 space-y-6">
    <!-- 页面标题 -->
    <div>
      <h1 class="text-2xl font-bold text-white">用户管理</h1>
      <p class="text-dark-400 mt-1">管理系统用户</p>
    </div>

    <!-- 用户列表 -->
    <div class="card">
      <div v-if="loading" class="text-center py-8 text-dark-400">
        加载中...
      </div>

      <div v-else class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th>角色</th>
              <th>状态</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td class="text-dark-400">{{ user.id }}</td>
              <td class="font-medium text-white">{{ user.username }}</td>
              <td class="text-dark-400">{{ user.email || '-' }}</td>
              <td>
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="user.is_admin ? 'bg-primary-500/10 text-primary-400' : 'bg-dark-700 text-dark-300'"
                >
                  {{ user.is_admin ? '管理员' : '用户' }}
                </span>
              </td>
              <td>
                <span
                  class="px-2 py-1 rounded text-xs font-medium"
                  :class="user.is_active ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'"
                >
                  {{ user.is_active ? '正常' : '禁用' }}
                </span>
              </td>
              <td class="text-dark-400 text-sm">{{ formatDate(user.created_at) }}</td>
              <td>
                <button
                  v-if="!user.is_admin"
                  @click="toggleUserStatus(user.id)"
                  class="px-3 py-1 text-sm rounded-lg transition-colors"
                  :class="user.is_active ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20' : 'bg-green-500/10 text-green-400 hover:bg-green-500/20'"
                >
                  {{ user.is_active ? '禁用' : '启用' }}
                </button>
                <span v-else class="text-dark-500 text-sm">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import api from '../api'
import { useToastStore } from '../stores/toast'

const toast = useToastStore()
const users = ref([])
const loading = ref(true)

function formatDate(date) {
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

async function fetchUsers() {
  try {
    const response = await api.get('/api/users')
    users.value = response.data
  } catch (error) {
    toast.error('获取用户列表失败', error.response?.data?.detail || '请稍后重试')
  } finally {
    loading.value = false
  }
}

async function toggleUserStatus(userId) {
  try {
    const response = await api.put(`/api/users/${userId}/toggle-active`)
    toast.success('操作成功', response.data.message)
    await fetchUsers()
  } catch (error) {
    toast.error('操作失败', error.response?.data?.detail || '请稍后重试')
  }
}

onMounted(() => {
  fetchUsers()
})
</script>
