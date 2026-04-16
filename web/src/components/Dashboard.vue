<template>
  <div class="space-y-6">
    <section class="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
      <article class="app-card overflow-hidden p-5 md:p-6">
        <div class="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div class="space-y-4">
            <span
              :class="[
                'status-pill',
                adminReady
                  ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
                  : 'border-amber-400/20 bg-amber-500/10 text-amber-200',
              ]"
            >
              <span class="h-2 w-2 rounded-full bg-current"></span>
              {{ adminReady ? '管理员已就绪' : '管理员未登录' }}
            </span>

            <div>
              <h2 class="page-title">账号池总览</h2>
              <p class="page-copy mt-3 max-w-3xl">
                先看活跃账号、待命储备和额度风险，再决定是发起轮转、同步账号，还是先补齐管理员登录。
              </p>
            </div>
          </div>

          <div class="flex flex-wrap gap-3">
            <button
              @click="syncAccounts"
              :disabled="syncing"
              class="app-button-primary"
            >
              {{ syncing ? '同步中...' : '同步账号状态' }}
            </button>
            <button
              @click="$emit('refresh')"
              class="app-button-secondary"
            >
              刷新视图
            </button>
          </div>
        </div>

        <div
          v-if="message"
          class="mt-5 rounded-2xl border px-4 py-3 text-sm"
          :class="messageClass"
        >
          {{ message }}
        </div>

        <div
          v-if="!adminReady"
          class="mt-5 rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-4 text-sm text-amber-100"
        >
          <div class="font-medium text-amber-50">管理员尚未完成登录</div>
          <p class="mt-2 leading-6 text-amber-100/80">
            账号轮转、补满、清理和移出 Team 等高风险动作会被锁住。先去「系统设置」完成管理员登录，再回来操作账号池。
          </p>
        </div>

        <div class="mt-6 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
          <article
            v-for="card in cards"
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
      </article>

      <div class="space-y-4">
        <article class="app-card p-5">
          <div class="metric-label">当前状态</div>
          <div class="mt-3 text-lg font-semibold text-white">
            {{ runningTaskLabel }}
          </div>
          <p class="mt-3 text-sm leading-6 text-slate-400">
            {{ runningTaskCopy }}
          </p>
        </article>

        <article class="app-card p-5">
          <div class="metric-label">下一步建议</div>
          <div class="mt-4 space-y-3">
            <div
              v-for="tip in actionTips"
              :key="tip.title"
              class="app-card-soft p-4"
            >
              <div class="text-sm font-semibold text-white">{{ tip.title }}</div>
              <p class="mt-2 text-sm leading-6 text-slate-400">
                {{ tip.copy }}
              </p>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="app-card overflow-hidden p-5 md:p-6">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h3 class="text-2xl font-bold tracking-tight text-white">
            账号列表
          </h3>
          <p class="page-copy mt-2">
            支持按邮箱搜索、按状态筛选。列表默认把更需要处理的账号排在前面。
          </p>
        </div>

        <div class="grid gap-3 sm:grid-cols-[minmax(0,260px)_minmax(0,180px)]">
          <input
            v-model.trim="searchQuery"
            type="search"
            placeholder="搜索邮箱"
            class="app-input"
          />
          <select v-model="sortKey" class="app-input">
            <option value="attention">按风险优先</option>
            <option value="quota">按剩余额度</option>
            <option value="email">按邮箱字母</option>
          </select>
        </div>
      </div>

      <div class="mt-5 flex flex-wrap gap-2">
        <button
          v-for="tab in filterTabs"
          :key="tab.key"
          @click="selectedStatus = tab.key"
          :class="[
            'app-button',
            selectedStatus === tab.key
              ? 'border border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
              : 'border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white',
          ]"
        >
          <span>{{ tab.label }}</span>
          <span class="rounded-full bg-white/10 px-2 py-0.5 text-[11px]">
            {{ tab.count }}
          </span>
        </button>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-3 text-sm text-slate-400">
        <span class="app-chip">
          当前显示
          <strong class="text-white">{{ filteredAccounts.length }}</strong>
        </span>
        <span class="app-chip">
          风险账号
          <strong class="text-white">{{ attentionCount }}</strong>
        </span>
        <button
          v-if="searchQuery || selectedStatus !== 'all' || sortKey !== 'attention'"
          @click="resetFilters"
          class="app-button-ghost px-0 py-0 text-sm"
        >
          清空筛选
        </button>
      </div>

      <div v-if="loading && !statusData" class="mt-6 space-y-3">
        <div
          v-for="i in 3"
          :key="i"
          class="app-card-soft h-44 animate-pulse"
        ></div>
      </div>

      <div
        v-else-if="filteredAccounts.length === 0"
        class="mt-6 rounded-[24px] border border-dashed border-white/10 bg-white/5 px-6 py-12 text-center"
      >
        <div class="text-lg font-semibold text-white">没有匹配的账号</div>
        <p class="mt-3 text-sm leading-6 text-slate-400">
          换个状态筛选，或者直接搜索部分邮箱关键字试试。
        </p>
      </div>

      <div v-else class="mt-6 grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
        <article
          v-for="account in filteredAccounts"
          :key="account.email"
          class="app-card-soft p-4"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-xs font-medium uppercase tracking-[0.24em] text-slate-500">
                {{ statusDescription(account.status) }}
              </div>
              <div class="mt-2 break-all font-mono text-sm text-white">
                {{ account.email }}
              </div>
            </div>
            <span :class="['status-pill shrink-0', statusTone(account.status)]">
              <span class="h-2 w-2 rounded-full bg-current"></span>
              {{ statusLabel(account.status) }}
            </span>
          </div>

          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div class="app-panel p-3">
              <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
                <span>5 小时额度</span>
                <span class="font-mono">{{ quotaText(account, 'primary') }}</span>
              </div>
              <div class="mt-3 h-2 rounded-full bg-slate-900">
                <div
                  class="h-2 rounded-full transition-all"
                  :class="quotaBarTone(quota(account, 'primary'))"
                  :style="{ width: `${quotaBarWidth(account, 'primary')}%` }"
                ></div>
              </div>
              <div class="mt-3 text-xs leading-5 text-slate-500">
                重置时间 {{ quotaReset(account, 'primary') }}
              </div>
            </div>

            <div class="app-panel p-3">
              <div class="flex items-center justify-between gap-2 text-xs text-slate-400">
                <span>周额度</span>
                <span class="font-mono">{{ quotaText(account, 'weekly') }}</span>
              </div>
              <div class="mt-3 h-2 rounded-full bg-slate-900">
                <div
                  class="h-2 rounded-full transition-all"
                  :class="quotaBarTone(quota(account, 'weekly'))"
                  :style="{ width: `${quotaBarWidth(account, 'weekly')}%` }"
                ></div>
              </div>
              <div class="mt-3 text-xs leading-5 text-slate-500">
                重置时间 {{ quotaReset(account, 'weekly') }}
              </div>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap gap-2">
            <button
              v-if="account.status !== 'active'"
              @click="loginAccount(account.email)"
              :disabled="actionDisabled || actionEmail === account.email"
              class="app-button-primary"
            >
              {{ actionEmail === account.email && actionType === 'login' ? '登录中...' : '登录账号' }}
            </button>

            <button
              v-if="account.status === 'active'"
              @click="kickAccount(account.email)"
              :disabled="actionDisabled || actionEmail === account.email"
              class="app-button-secondary"
            >
              {{ actionEmail === account.email && actionType === 'kick' ? '移出中...' : '移出 Team' }}
            </button>

            <button
              v-if="account.status === 'active'"
              @click="exportCodexAuth(account.email)"
              :disabled="actionDisabled || actionEmail === account.email"
              class="app-button-secondary"
            >
              导出 Codex 认证
            </button>

            <button
              @click="removeAccount(account.email)"
              :disabled="actionDisabled || actionEmail === account.email"
              class="app-button-danger"
            >
              {{ actionEmail === account.email && actionType === 'delete' ? '删除中...' : '删除账号' }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <div
      v-if="exportData"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
      @click.self="exportData = null"
    >
      <div class="app-card flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden">
        <div class="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div>
            <h3 class="text-xl font-semibold text-white">Codex CLI 认证文件</h3>
            <p class="mt-1 text-sm text-slate-400">
              将下方内容保存为本地 `auth.json` 后，可直接让 Codex CLI 使用该账号。
            </p>
          </div>
          <button @click="exportData = null" class="app-button-ghost h-10 w-10 rounded-full p-0 text-lg">
            ×
          </button>
        </div>

        <div class="grid gap-5 overflow-y-auto p-5 lg:grid-cols-[0.78fr_1.22fr]">
          <section class="space-y-4">
            <div class="app-card-soft p-4">
              <div class="text-sm font-semibold text-white">使用步骤</div>
              <ol class="mt-3 space-y-2 text-sm leading-6 text-slate-400">
                <li>1. 先退出当前 Codex CLI 会话。</li>
                <li>2. 替换本地认证文件 `~/.codex/auth.json`。</li>
                <li>3. Windows 路径通常是 `%APPDATA%\\codex\\auth.json`。</li>
                <li>4. 重启 Codex CLI，让新认证生效。</li>
              </ol>
            </div>

            <div class="app-card-soft p-4">
              <div class="text-sm font-semibold text-white">为什么要导出</div>
              <p class="mt-3 text-sm leading-6 text-slate-400">
                导出后可以直接复用已经登录成功的账号，少走一次网页登录流程，也能绕开一些代理链路里的不稳定环节。
              </p>
            </div>
          </section>

          <section class="space-y-4">
            <div class="relative">
              <pre class="max-h-[52vh] overflow-x-auto rounded-[24px] border border-white/10 bg-slate-950/90 p-4 text-xs text-slate-200">{{ exportJson }}</pre>
              <button
                @click="copyExport"
                class="app-button-secondary absolute right-3 top-3"
              >
                {{ copied ? '已复制' : '复制内容' }}
              </button>
            </div>

            <div class="flex flex-wrap justify-end gap-3">
              <button @click="downloadExport" class="app-button-primary">
                下载 auth.json
              </button>
              <button @click="exportData = null" class="app-button-secondary">
                关闭
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  status: {
    type: Object,
    default: null,
  },
  loading: Boolean,
  runningTask: {
    type: Object,
    default: null,
  },
  adminStatus: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['refresh', 'accounts-synced'])

const actionEmail = ref('')
const actionType = ref('')
const syncing = ref(false)
const message = ref('')
const exportData = ref(null)
const copied = ref(false)
const messageClass = ref('')
const searchQuery = ref('')
const selectedStatus = ref('all')
const sortKey = ref('attention')
const localStatus = ref(null)

const adminReady = computed(() => !!props.adminStatus?.configured)
const actionDisabled = computed(() => !!props.runningTask || !adminReady.value)
const statusData = computed(() => localStatus.value || props.status || null)
const accounts = computed(() => statusData.value?.accounts || [])

watch(() => props.status, (value) => {
  if (value) {
    localStatus.value = null
  }
})
const filterTabs = computed(() => {
  const counts = {
    all: accounts.value.length,
    active: 0,
    standby: 0,
    exhausted: 0,
    pending: 0,
  }
  for (const account of accounts.value) {
    counts[account.status] = (counts[account.status] || 0) + 1
  }
  return [
    { key: 'all', label: '全部', count: counts.all },
    { key: 'active', label: '可用', count: counts.active },
    { key: 'standby', label: '待命', count: counts.standby },
    { key: 'exhausted', label: '额度耗尽', count: counts.exhausted },
    { key: 'pending', label: '待处理', count: counts.pending },
  ]
})
const attentionCount = computed(() => {
  return accounts.value.filter(account => {
    const primary = quota(account, 'primary')
    return account.status === 'exhausted' || account.status === 'pending' || (primary !== null && primary <= 20)
  }).length
})
const filteredAccounts = computed(() => {
  const query = searchQuery.value.toLowerCase()
  let list = accounts.value.filter(account => {
    const matchStatus = selectedStatus.value === 'all' || account.status === selectedStatus.value
    const matchQuery = !query || account.email.toLowerCase().includes(query)
    return matchStatus && matchQuery
  })

  if (sortKey.value === 'email') {
    return [...list].sort((a, b) => a.email.localeCompare(b.email))
  }

  if (sortKey.value === 'quota') {
    return [...list].sort((a, b) => safeQuota(a) - safeQuota(b))
  }

  return [...list].sort((a, b) => attentionRank(a) - attentionRank(b) || safeQuota(a) - safeQuota(b) || a.email.localeCompare(b.email))
})
const cards = computed(() => {
  if (!statusData.value) return []
  const summary = statusData.value.summary || {}
  return [
    {
      label: '活跃账号',
      value: summary.active || 0,
      badge: (summary.active || 0) > 0 ? '可直接使用' : '暂无可用',
      tone: (summary.active || 0) > 0
        ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
        : 'border-slate-500/20 bg-slate-500/10 text-slate-300',
      copy: '活跃账号越多，轮转与补满空间越大。',
    },
    {
      label: '待命储备',
      value: summary.standby || 0,
      badge: (summary.standby || 0) > 0 ? '可轮转补位' : '储备偏紧',
      tone: (summary.standby || 0) > 0
        ? 'border-amber-400/20 bg-amber-500/10 text-amber-200'
        : 'border-slate-500/20 bg-slate-500/10 text-slate-300',
      copy: '额度恢复中的账号会先进入待命，随后再回到池子里。',
    },
    {
      label: '额度耗尽',
      value: summary.exhausted || 0,
      badge: (summary.exhausted || 0) > 0 ? '需要处理' : '暂无告警',
      tone: (summary.exhausted || 0) > 0
        ? 'border-rose-400/20 bg-rose-500/10 text-rose-200'
        : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
      copy: '这批账号已经无法继续跑任务，优先考虑轮转或清理。',
    },
    {
      label: '总账号数',
      value: summary.total || 0,
      badge: attentionCount.value > 0 ? `${attentionCount.value} 个风险` : '状态稳定',
      tone: attentionCount.value > 0
        ? 'border-violet-400/20 bg-violet-500/10 text-violet-200'
        : 'border-slate-500/20 bg-slate-500/10 text-slate-300',
      copy: '这里展示的是本地记录里的全量账号池规模。',
    },
  ]
})
const runningTaskLabel = computed(() => {
  if (!props.runningTask) return '系统空闲，可以继续操作'
  if (props.runningTask.command === 'admin-login') return '管理员登录进行中'
  if (props.runningTask.command === 'main-codex-sync') return '主号 Codex 同步中'
  return `${props.runningTask.command} 执行中`
})
const runningTaskCopy = computed(() => {
  if (!props.runningTask) {
    return '当前没有排队或执行中的后台任务，账号池操作和同步动作都会更顺手。'
  }
  if (props.runningTask.command === 'admin-login') {
    return '管理员登录未完成前，账号池的高风险动作会自动上锁，避免半登录状态误操作。'
  }
  if (props.runningTask.command === 'main-codex-sync') {
    return '主号 Codex 认证同步期间建议先不要重复触发相似操作，等当前流程走完。'
  }
  return '后台任务进行中时，系统会先保护现场，避免多个动作互相打架。'
})
const actionTips = computed(() => {
  const summary = statusData.value?.summary || {}
  const tips = []

  if (!adminReady.value) {
    tips.push({
      title: '先补管理员登录',
      copy: '没有管理员登录态时，移出 Team、清理成员和一部分账号池动作都不会开放。',
    })
  }

  if ((summary.exhausted || 0) > 0) {
    tips.push({
      title: '优先处理额度耗尽账号',
      copy: '可以先去账号池页发起轮转或清理，把已经没额度的账号尽快从活跃流程里挪开。',
    })
  }

  if ((summary.standby || 0) === 0) {
    tips.push({
      title: '补一点待命储备',
      copy: '待命账号为 0 时，轮转空间会很紧，适合先补成员或同步账号状态。',
    })
  }

  if (tips.length === 0) {
    tips.push({
      title: '状态看起来还不错',
      copy: '管理员就绪、活跃账号稳定、也有待命储备。现在更适合做同步、导出或例行巡检。',
    })
  }

  return tips.slice(0, 3)
})
const exportJson = computed(() => {
  if (!exportData.value) return ''
  return JSON.stringify(exportData.value.codex_auth, null, 2)
})

function statusTone(status) {
  return {
    active: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
    exhausted: 'border-rose-400/20 bg-rose-500/10 text-rose-200',
    standby: 'border-amber-400/20 bg-amber-500/10 text-amber-200',
    pending: 'border-slate-500/20 bg-slate-500/10 text-slate-300',
  }[status] || 'border-slate-500/20 bg-slate-500/10 text-slate-300'
}

function statusLabel(status) {
  return {
    active: '可用',
    exhausted: '额度耗尽',
    standby: '待命',
    pending: '待处理',
  }[status] || status
}

function statusDescription(status) {
  return {
    active: '账号在线',
    exhausted: '额度告警',
    standby: '等待轮转',
    pending: '登录处理中',
  }[status] || '账号状态'
}

function quota(account, type) {
  const quotaInfo = statusData.value?.quota_cache?.[account.email] || account.last_quota
  if (!quotaInfo) return null
  const pct = type === 'primary' ? quotaInfo.primary_pct : quotaInfo.weekly_pct
  return 100 - (pct || 0)
}

function quotaText(account, type) {
  const value = quota(account, type)
  return value === null ? '暂无数据' : `${value}%`
}

function quotaReset(account, type) {
  const quotaInfo = statusData.value?.quota_cache?.[account.email] || account.last_quota
  if (!quotaInfo) return '未知'
  const timestamp = type === 'primary' ? quotaInfo.primary_resets_at : quotaInfo.weekly_resets_at
  if (!timestamp) return '未知'
  const date = new Date(timestamp * 1000)
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function quotaBarWidth(account, type) {
  const value = quota(account, type)
  return value === null ? 8 : Math.min(100, Math.max(8, value))
}

function quotaBarTone(value) {
  if (value === null) return 'bg-slate-500'
  if (value > 45) return 'bg-emerald-400'
  if (value > 20) return 'bg-amber-400'
  return 'bg-rose-400'
}

function safeQuota(account) {
  const value = quota(account, 'primary')
  return value === null ? 101 : value
}

function attentionRank(account) {
  const statusRank = {
    exhausted: 0,
    pending: 1,
    standby: 2,
    active: 3,
  }[account.status] ?? 4
  const primary = safeQuota(account)
  return statusRank * 1000 + primary
}

function resetFilters() {
  searchQuery.value = ''
  selectedStatus.value = 'all'
  sortKey.value = 'attention'
}

function showMessage(text, type = 'success') {
  message.value = text
  messageClass.value = type === 'success'
    ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100'
    : type === 'info'
      ? 'border-cyan-400/20 bg-cyan-500/10 text-cyan-100'
      : 'border-rose-400/20 bg-rose-500/10 text-rose-100'
  window.clearTimeout(showMessage._timer)
  showMessage._timer = window.setTimeout(() => {
    message.value = ''
  }, 8000)
}

async function exportCodexAuth(email) {
  actionEmail.value = email
  actionType.value = 'export'
  try {
    exportData.value = await api.getCodexAuth(email)
    copied.value = false
  } catch (e) {
    showMessage(e.message, 'error')
  } finally {
    actionEmail.value = ''
    actionType.value = ''
  }
}

async function copyExport() {
  try {
    await navigator.clipboard.writeText(exportJson.value)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = exportJson.value
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 3000)
}

function downloadExport() {
  const blob = new Blob([exportJson.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'auth.json'
  link.click()
  URL.revokeObjectURL(url)
}

async function syncAccounts() {
  syncing.value = true
  try {
    const result = await api.postSyncAccounts()
    if (Array.isArray(result.accounts)) {
      localStatus.value = {
        accounts: result.accounts,
        summary: result.summary || {},
        quota_cache: statusData.value?.quota_cache || {},
      }
      emit('accounts-synced', result)
    }
    result.message = result.message || '\u8d26\u53f7\u72b6\u6001\u540c\u6b65\u5b8c\u6210'
    showMessage(result.message || '账号状态同步完成')
  } catch (e) {
    showMessage(e.message, 'error')
  } finally {
    syncing.value = false
  }
}

async function loginAccount(email) {
  if (actionDisabled.value) return

  actionEmail.value = email
  actionType.value = 'login'
  try {
    const result = await api.loginAccount(email)
    showMessage(`已提交 ${email} 的登录任务 ${result.task_id}`, 'info')
    emit('refresh')
  } catch (e) {
    showMessage(e.message, 'error')
  } finally {
    actionEmail.value = ''
    actionType.value = ''
  }
}

async function kickAccount(email) {
  if (actionDisabled.value) return

  const confirmed = window.confirm(`确认将 ${email} 移出 Team？\n账号会切回待命状态，额度恢复后可以重新复用。`)
  if (!confirmed) return

  actionEmail.value = email
  actionType.value = 'kick'
  try {
    const result = await api.kickAccount(email)
    showMessage(result.message || `已将 ${email} 移出 Team`)
    emit('refresh')
  } catch (e) {
    showMessage(e.message, 'error')
  } finally {
    actionEmail.value = ''
    actionType.value = ''
  }
}

async function removeAccount(email) {
  if (actionDisabled.value) return

  const confirmed = window.confirm(`确认删除账号 ${email}？\n会同时清理本地记录、CPA、Team/Invite 和 CloudMail。`)
  if (!confirmed) return

  actionEmail.value = email
  actionType.value = 'delete'
  try {
    const result = await api.deleteAccount(email)
    showMessage(result.message || `已删除 ${email}`)
    emit('refresh')
  } catch (e) {
    showMessage(e.message, 'error')
  } finally {
    actionEmail.value = ''
    actionType.value = ''
  }
}
</script>
