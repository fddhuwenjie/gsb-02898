# BTC行情监控预警系统

## How to Run

```bash
# 1. 克隆项目
git clone <repository-url>
cd btc-monitor

# 2. 启动所有服务
docker-compose up --build -d

# 3. 访问服务
# 管理后台: http://localhost:8082
# 后端API: http://localhost:8000
# API文档: http://localhost:8000/docs

# 4. 停止服务
docker-compose down

# 5. 查看日志
docker-compose logs -f
```

## Services

| 服务 | 端口 | 描述 |
|------|------|------|
| backend | 8000 | 后端API服务 (FastAPI) |
| frontend-admin | 8082 | 管理后台 (Vue 3 + Vite) |
| redis | 6379 | 缓存服务 |

## 测试账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 普通用户 | user | user123 |

## 题目内容

使用Python和Web形式设计一个BTC行情监控系统，用于行情预警，打包Docker。

### 功能要求
- BTC实时行情监控
- 价格预警设置（上限/下限）
- 历史价格走势图表
- 预警通知记录
- 用户管理

### 技术栈
- 后端: Python FastAPI + Redis + SQLite + APScheduler + WebSocket
- 前端: Vue 3 + Vite + TailwindCSS + ECharts
- 数据源: CoinGecko API / Binance API

---

## 项目介绍

BTC行情监控预警系统是一个实时监控比特币价格并提供预警功能的Web应用。系统通过CoinGecko和Binance公开API获取实时行情数据，支持用户设置价格预警阈值，当价格触发预警条件时自动记录并通知。

### 核心功能

1. **实时行情监控**
   - WebSocket实时推送BTC/USDT价格
   - 24小时价格变化统计
   - 市值、交易量等关键指标
   - Redis缓存价格数据

2. **价格预警系统**
   - 支持设置价格上限/下限预警
   - 后台定时任务每30秒检查预警条件
   - 预警触发自动记录并通过WebSocket推送通知
   - 支持重复触发模式

3. **数据可视化**
   - K线图展示
   - 价格趋势图
   - 交易量统计图

4. **用户管理**
   - 用户注册/登录
   - JWT Token认证
   - 权限管理

### 系统架构

```
┌─────────────────┐     ┌─────────────────┐
│  frontend-admin │────▶│     backend     │
│   (Vue 3)       │◀───▶│   (FastAPI)     │
│   Port: 8082    │ WS  │   Port: 8000    │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌─────────┐  ┌─────────┐  ┌─────────┐
              │  Redis  │  │ SQLite  │  │Binance/ │
              │  Cache  │  │   DB    │  │CoinGecko│
              └─────────┘  └─────────┘  └─────────┘
                    │
              ┌─────────┐
              │Scheduler│ (每30秒检查预警)
              └─────────┘
```

### 目录结构

```
btc-monitor/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── main.py         # 入口文件
│   ├── Dockerfile
│   └── requirements.txt
├── frontend-admin/          # 管理后台
│   ├── src/
│   │   ├── components/     # 组件
│   │   ├── views/          # 页面
│   │   ├── stores/         # 状态管理
│   │   └── main.js         # 入口文件
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .gitignore
└── README.md
```
