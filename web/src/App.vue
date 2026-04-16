<template>
  <div class="app-shell">
    <SetupPage v-if="needSetup" @configured="onSetupDone" />

    <div
      v-else-if="!authenticated"
      class="mx-auto flex min-h-[calc(100vh-2rem)] max-w-6xl items-center justify-center"
    >
      <div class="grid w-full gap-6 lg:grid-cols-[1.12fr_0.88fr]">
        <section class="app-card hidden overflow-hidden p-8 lg:block xl:p-10">
          <div class="flex h-full flex-col justify-between gap-10">
            <div class="space-y-6">
              <span class="app-chip border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
                AutoTeam Control Deck
              </span>
              <div class="space-y-4">
                <h1 class="text-4xl font-bold leading-tight text-white">
                  把轮转、同步和 Team 管理收进一个真正能用的面板里。
                </h1>
                <p class="max-w-xl text-base leading-7 text-slate-300">
                  这里集中处理账号池健康、管理员登录、OAuth 补录和任务历史。先看状态，再做动作，避免在一堆生硬按钮里瞎点。
                </p>
              </div>
            </div>

            <div class="grid gap-4 sm:grid-cols-3">
              <article class="app-card-soft p-4">
                <div class="metric-label">账号池视角</div>
                <div class="mt-3 text-lg font-semibold text-white">状态先行</div>
                <p class="mt-2 text-sm leading-6 text-slate-400">
                  一眼看出可用账号、待命账号和额度风险。
                </p>
              </article>
              <article class="app-card-soft p-4">
                <div class="metric-label">操作安全</div>
                <div class="mt-3 text-lg font-semibold text-white">减少误触</div>
                <p class="mt-2 text-sm leading-6 text-slate-400">
                  忙碌态、确认态、输入态统一显示，知道系统现在在做什么。
                </p>
              </article>
              <article class="app-card-soft p-4">
                <div class="metric-label">排障效率</div>
                <div class="mt-3 text-lg font-semibold text-white">任务可追踪</div>
                <p class="mt-2 text-sm leading-6 text-slate-400">
                  同步、日志、任务历史都在同一套界面里闭环。
                </p>
              </article>
            </div>
          </div>
        </section>

        <section class="app-card p-6 sm:p-8">
          <div class="mb-8 space-y-3">
            <span class="app-chip">
              需要 API Key
            </span>
            <div>
              <h2 class="text-3xl font-bold tracking-tight text-white">
                登录 AutoTeam
              </h2>
              <p class="mt-2 text-sm leading-6 text-slate-400">
                输入后端配置好的 API Key，进入控制台继续处理账号池和 Team 任务。
              </p>
            </div>
          </div>

          <div
            v-if="authError"
            class="mb-4 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
          >
            {{ authError }}
          </div>

          <label class="mb-2 block text-sm font-medium text-slate-300">
            API Key
          </label>
          <input
            v-model.trim="inputKey"
            type="password"
            placeholder="输入 API Key"
            @keyup.enter="doLogin"
            class="app-input"
          />

          <button
            @click="doLogin"
            :disabled="!inputKey || authLoading"
            class="app-button-primary mt-5 w-full"
          >
            {{ authLoading ? '验证中...' : '进入控制台' }}
          </button>

          <div class="mt-6 app-card-soft p-4 text-sm leading-6 text-slate-400">
            <div class="font-medium text-slate-200">登录后会看到什么</div>
            <p class="mt-2">
              账号池总览、管理员状态、轮转与同步动作、任务历史，以及实时日志都会在同一个工作区里展开。
            </p>
          </div>
        </section>
      </div>
    </div>

    <div v-else class="app-frame">
      <Sidebar
        :active="currentPage"
        :loading="loading"
        :auth-required="authRequired"
        :status="status"
        :admin-status="adminStatus"
        :busy-task="busyTask"
        :tasks="tasks"
        @navigate="navigate"
        @refresh="refresh"
        @logout="doLogout"
      />

      <div class="min-w-0 flex-1 space-y-4 md:space-y-6">
        <header class="app-card sticky top-4 z-20 overflow-hidden px-5 py-5 md:px-6 md:py-6">
          <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.14),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(56,189,248,0.1),transparent_28%)]"></div>
          <div class="relative space-y-5">
            <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div class="space-y-4">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="app-chip">
                    Workspace
                    <strong class="text-white">{{ workspaceLabel }}</strong>
                  </span>
                  <span :class="['status-pill', adminPillClass]">
                    <span class="h-2 w-2 rounded-full bg-current"></span>
                    {{ adminPillLabel }}
                  </span>
                  <span v-if="busyLabel" class="status-pill border-amber-400/20 bg-amber-500/10 text-amber-200">
                    <span class="h-2 w-2 animate-pulse rounded-full bg-current"></span>
                    {{ busyLabel }}
                  </span>
                </div>

                <div>
                  <h1 class="text-3xl font-bold tracking-tight text-white md:text-4xl">
                    AutoTeam 控制台
                  </h1>
                  <p class="mt-2 max-w-3xl text-sm leading-7 text-slate-300 md:text-base">
                    先看账号池健康、管理员准备状态和后台任务，再决定是轮转、同步还是补录登录流程。
                  </p>
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-3">
                <span class="app-chip">
                  最近更新
                  <strong class="text-white">{{ lastUpdatedLabel }}</strong>
                </span>
                <button
                  @click="refresh"
                  :disabled="loading"
                  class="app-button-secondary"
                >
                  {{ loading ? '刷新中...' : '立即刷新' }}
                </button>
              </div>
            </div>

            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <article
                v-for="card in overviewCards"
                :key="card.label"
                class="app-card-soft p-4"
              >
                <div class="metric-label">{{ card.label }}</div>
                <div class="mt-3 flex items-end justify-between gap-3">
                  <div class="metric-value">{{ card.value }}</div>
                  <span :class="['status-pill', card.tone]">
                    {{ card.badge }}
                  </span>
                </div>
                <p class="mt-3 text-sm leading-6 text-slate-400">
                  {{ card.copy }}
                </p>
              </article>
            </div>
          </div>
        </header>

        <Transition name="page-fade" mode="out-in">
          <main :key="currentPage" class="pb-24 md:pb-6">
            <Dashboard
              v-if="currentPage === 'dashboard'"
              :status="status"
              :loading="loading"
              :running-task="busyTask"
              :admin-status="adminStatus"
              @refresh="refresh"
            />

            <TeamMembers v-else-if="currentPage === 'team'" />

            <PoolPage
              v-else-if="currentPage === 'pool'"
              :running-task="busyTask"
              :admin-status="adminStatus"
              @task-started="onTaskStarted"
              @refresh="refresh"
            />

            <SyncPage
              v-else-if="currentPage === 'sync'"
              :running-task="busyTask"
              :admin-status="adminStatus"
              @task-started="onTaskStarted"
              @refresh="refresh"
            />

            <OAuthPage
              v-else-if="currentPage === 'oauth'"
              :manual-account-status="manualAccountStatus"
              @refresh="refresh"
              @progress="onAdminProgress"
            />

            <TaskHistoryPage v-else-if="currentPage === 'tasks'" :tasks="tasks" />

            <LogViewer v-else-if="currentPage === 'logs'" />

            <Settings
              v-else-if="currentPage === 'settings'"
              :admin-status="adminStatus"
              :codex-status="codexStatus"
              @refresh="refresh"
              @admin-progress="onAdminProgress"
            />
          </main>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { api, setApiKey, clearApiKey } from './api.js'
import SetupPage from './components/SetupPage.vue'
import Sidebar from './components/Sidebar.vue'
import Dashboard from './components/Dashboard.vue'
import TeamMembers from './components/TeamMembers.vue'
import PoolPage from './components/PoolPage.vue'
import SyncPage from './components/SyncPage.vue'
import TaskHistoryPage from './components/TaskHistoryPage.vue'
import LogViewer from './components/LogViewer.vue'
import OAuthPage from './components/OAuthPage.vue'
import Settings from './components/Settings.vue'

const IDLE_POLL_MS = 60000
const ACTIVE_POLL_MS = 8000
const PAGE_KEY = 'autoteam_current_page'

const needSetup = ref(false)
const authenticated = ref(false)
const authRequired = ref(false)
const authLoading = ref(false)
const authError = ref('')
const inputKey = ref('')
const currentPage = ref('dashboard')

const status = ref(null)
const adminStatus = ref(null)
const codexStatus = ref(null)
const manualAccountStatus = ref(null)
const tasks = ref([])
const loading = ref(false)
const runningTask = ref(null)
const lastUpdated = ref(0)

const busyTask = computed(() => {
  if (adminStatus.value?.login_in_progress) {
    return { command: 'admin-login' }
  }
  if (codexStatus.value?.in_progress) {
    return { command: 'main-codex-sync' }
  }
  return runningTask.value
})

const workspaceLabel = computed(() => adminStatus.value?.workspace_name || '未连接')
const adminPillLabel = computed(() => {
  if (adminStatus.value?.login_in_progress) return '管理员登录进行中'
  if (adminStatus.value?.configured) return '管理员已就绪'
  return '管理员未配置'
})
const adminPillClass = computed(() => {
  if (adminStatus.value?.login_in_progress) {
    return 'border-amber-400/20 bg-amber-500/10 text-amber-200'
  }
  if (adminStatus.value?.configured) {
    return 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
  }
  return 'border-slate-500/20 bg-slate-500/10 text-slate-300'
})
const busyLabel = computed(() => {
  if (manualAccountStatus.value?.in_progress) return 'OAuth 登录进行中'
  if (!busyTask.value) return ''
  if (busyTask.value.command === 'admin-login') return '管理员登录进行中'
  if (busyTask.value.command === 'main-codex-sync') return '主号 Codex 同步中'
  return `${busyTask.value.command} 执行中`
})
const tasksInFlight = computed(() => tasks.value.filter(task => task.status === 'running' || task.status === 'pending').length)
const overviewCards = computed(() => {
  const summary = status.value?.summary || {}
  const total = summary.total || 0
  const active = summary.active || 0
  const exhausted = summary.exhausted || 0
  const standby = summary.standby || 0
  return [
    {
      label: '账号总量',
      value: total,
      badge: total > 0 ? `${active} 活跃` : '等待数据',
      tone: total > 0 ? 'border-cyan-400/20 bg-cyan-500/10 text-cyan-200' : 'border-slate-500/20 bg-slate-500/10 text-slate-300',
      copy: total > 0 ? '账号池总规模，包含活跃、待命和额度耗尽账号。' : '刷新后会在这里显示账号池规模。',
    },
    {
      label: '待处理风险',
      value: exhausted,
      badge: exhausted > 0 ? '需要关注' : '状态健康',
      tone: exhausted > 0 ? 'border-rose-400/20 bg-rose-500/10 text-rose-200' : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
      copy: exhausted > 0 ? '这些账号已经没有额度，需要轮转、补满或等待恢复。' : '当前没有额度耗尽账号，池子相对稳定。',
    },
    {
      label: '待命账号',
      value: standby,
      badge: standby > 0 ? '可补位' : '暂无储备',
      tone: standby > 0 ? 'border-amber-400/20 bg-amber-500/10 text-amber-200' : 'border-slate-500/20 bg-slate-500/10 text-slate-300',
      copy: standby > 0 ? '待命账号足够时，轮转和补位会更从容。' : '没有待命账号时，轮转空间会明显变小。',
    },
    {
      label: '后台任务',
      value: tasksInFlight.value,
      badge: tasksInFlight.value > 0 ? '系统忙碌' : '当前空闲',
      tone: tasksInFlight.value > 0 ? 'border-violet-400/20 bg-violet-500/10 text-violet-200' : 'border-slate-500/20 bg-slate-500/10 text-slate-300',
      copy: tasksInFlight.value > 0 ? '有任务正在执行时，前台操作会自动限流，减少冲突。' : '当前没有排队中的后台任务，可以安全发起新动作。',
    },
  ]
})
const lastUpdatedLabel = computed(() => formatLastUpdated(lastUpdated.value))

let pollTimer = null

async function checkAuth() {
  try {
    const result = await api.checkAuth()
    authenticated.value = result.authenticated
    authRequired.value = result.auth_required
    return result.authenticated
  } catch (e) {
    if (e.status === 401) {
      authenticated.value = false
      authRequired.value = true
      return false
    }
    authenticated.value = true
    authRequired.value = false
    return true
  }
}

async function doLogin() {
  authError.value = ''
  authLoading.value = true
  try {
    setApiKey(inputKey.value)
    const ok = await checkAuth()
    if (!ok) {
      clearApiKey()
      authError.value = 'API Key 无效'
    } else {
      inputKey.value = ''
      await refresh()
      startPolling(IDLE_POLL_MS)
    }
  } catch (e) {
    clearApiKey()
    authError.value = e.message
  } finally {
    authLoading.value = false
  }
}

function doLogout() {
  clearApiKey()
  authenticated.value = false
  stopPolling()
}

async function refresh() {
  loading.value = true
  try {
    const [s, t, admin, codex, manualAccount] = await Promise.all([
      api.getStatus(),
      api.getTasks(),
      api.getAdminStatus(),
      api.getMainCodexStatus(),
      api.getManualAccountStatus(),
    ])
    status.value = s
    tasks.value = t
    adminStatus.value = admin
    codexStatus.value = codex
    manualAccountStatus.value = manualAccount
    runningTask.value = t.find(task => task.status === 'running' || task.status === 'pending') || null
    lastUpdated.value = Date.now()
  } catch (e) {
    if (e.status === 401) {
      authenticated.value = false
      return
    }
    console.error('刷新失败:', e)
  } finally {
    loading.value = false
  }
}

function navigate(page) {
  currentPage.value = page
  try {
    localStorage.setItem(PAGE_KEY, page)
  } catch {}
}

function onTaskStarted() {
  startPolling(ACTIVE_POLL_MS)
  refresh()
}

function onAdminProgress() {
  startPolling(ACTIVE_POLL_MS)
  refresh()
}

function startPolling(interval = IDLE_POLL_MS) {
  stopPolling()
  pollTimer = setInterval(async () => {
    await refresh()
    if (!busyTask.value && !manualAccountStatus.value?.in_progress && interval < IDLE_POLL_MS) {
      startPolling(IDLE_POLL_MS)
    }
  }, interval)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function checkSetup() {
  try {
    const result = await api.getSetupStatus()
    return result.configured
  } catch {
    return true
  }
}

function onSetupDone() {
  needSetup.value = false
  checkAuth().then(async ok => {
    if (ok) {
      await refresh()
      startPolling(IDLE_POLL_MS)
    }
  })
}

function formatLastUpdated(timestamp) {
  if (!timestamp) return '未同步'
  const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
  if (diffSeconds < 10) return '刚刚'
  if (diffSeconds < 60) return `${diffSeconds} 秒前`
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)} 分钟前`
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(timestamp)
}

onMounted(async () => {
  try {
    const savedPage = localStorage.getItem(PAGE_KEY)
    if (savedPage) {
      currentPage.value = savedPage
    }
  } catch {}

  const setupOk = await checkSetup()
  if (!setupOk) {
    needSetup.value = true
    return
  }

  const ok = await checkAuth()
  if (ok) {
    await refresh()
    startPolling(IDLE_POLL_MS)
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>
