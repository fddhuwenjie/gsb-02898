import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    
    // 统一错误格式处理
    if (error.response?.data) {
      const data = error.response.data
      // 如果是新的错误格式 {code, message, detail}
      if (data.message) {
        error.response.data.detail = data.message
      }
    }
    
    return Promise.reject(error)
  }
)

export default api
