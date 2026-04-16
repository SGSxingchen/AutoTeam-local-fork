<template>
  <aside class="hidden lg:flex lg:w-[280px] lg:shrink-0">
    <div class="app-card flex min-h-[calc(100vh-3rem)] w-full flex-col p-5">
      <section class="app-panel overflow-hidden p-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="metric-label">Workspace</div>
            <h1 class="mt-3 text-2xl font-bold tracking-tight text-white">
              AutoTeam
            </h1>
            <p class="mt-2 text-sm leading-6 text-slate-400">
              {{ adminStatus?.workspace_name || '账号池与 Team 管理控制台' }}
            </p>
          </div>
          <span
            :class="[
              'status-pill shrink-0',
              busyTask ? 'border-amber-400/20 bg-amber-500/10 text-amber-200' : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
            ]"
          >
            <span class="h-2 w-2 rounded-full bg-current"></span>
            {{ busyTask ? '忙碌' : '空闲' }}
          </span>
        </div>
      </section>

      <section class="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
        <article
          v-for="card in summaryCards"
          :key="card.label"
          class="app-card-soft p-4"
        >
          <div class="metric-label">{{ card.label }}</div>
          <div class="mt-2 text-2xl font-bold text-white">{{ card.value }}</div>
          <p class="mt-2 text-xs leading-5 text-slate-400">
            {{ card.copy }}
          </p>
        </article>
      </section>

      <nav class="mt-5 flex-1 space-y-1">
        <button
          v-for="item in items"
          :key="item.key"
          @click="$emit('navigate', item.key)"
          :class="[
            'group flex w-full items-center gap-3 rounded-[22px] px-4 py-3 text-left transition',
            active === item.key
              ? 'border border-cyan-400/20 bg-cyan-400/10 text-white shadow-[0_20px_40px_-28px_rgba(34,211,238,0.9)]'
              : 'border border-transparent text-slate-400 hover:border-white/10 hover:bg-white/5 hover:text-white',
          ]"
        >
          <span
            :class="[
              'flex h-11 w-11 items-center justify-center rounded-2xl border transition',
              active === item.key
                ? 'border-cyan-300/30 bg-cyan-400/15 text-cyan-100'
                : 'border-white/10 bg-white/5 text-slate-300 group-hover:border-white/20 group-hover:text-white',
            ]"
          >
            <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8">
              <path :d="item.iconPath" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-medium">{{ item.label }}</span>
            <span class="mt-1 block text-xs leading-5 text-slate-500 group-hover:text-slate-400">
              {{ item.copy }}
            </span>
          </span>
        </button>
      </nav>

      <div class="mt-5 space-y-2 border-t border-white/10 pt-4">
        <button
          @click="$emit('refresh')"
          :disabled="loading"
          class="app-button-secondary w-full justify-between"
        >
          <span>{{ loading ? '刷新中...' : '刷新数据' }}</span>
          <span class="text-xs text-slate-400">R</span>
        </button>
        <button
          v-if="authRequired"
          @click="$emit('logout')"
          class="app-button-danger w-full justify-between"
        >
          <span>退出登录</span>
          <span class="text-xs text-rose-200/70">API Key</span>
        </button>
      </div>
    </div>
  </aside>

  <nav class="fixed inset-x-4 bottom-4 z-50 lg:hidden">
    <div class="app-card overflow-hidden px-2 py-2">
      <div class="flex gap-2 overflow-x-auto pb-1">
        <button
          v-for="item in items"
          :key="item.key"
          @click="$emit('navigate', item.key)"
          :class="[
            'min-w-[82px] flex-1 rounded-2xl px-3 py-2 text-center transition',
            active === item.key
              ? 'bg-cyan-400/15 text-white'
              : 'text-slate-400 hover:bg-white/5 hover:text-white',
          ]"
        >
          <span class="mx-auto flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/5">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8">
              <path :d="item.iconPath" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
          <span class="mt-2 block text-[11px] font-medium">
            {{ item.mobileLabel || item.label }}
          </span>
        </button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  active: String,
  loading: Boolean,
  authRequired: Boolean,
  status: {
    type: Object,
    default: null,
  },
  adminStatus: {
    type: Object,
    default: null,
  },
  busyTask: {
    type: Object,
    default: null,
  },
  tasks: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['navigate', 'refresh', 'logout'])

const items = [
  {
    key: 'dashboard',
    label: '仪表盘',
    mobileLabel: '概览',
    copy: '账号池健康与最近动作',
    iconPath: 'M4 5.5h7v5H4zM13 5.5h7v13h-7zM4 12.5h7v6H4z',
  },
  {
    key: 'team',
    label: 'Team 成员',
    mobileLabel: '成员',
    copy: '查看成员、邀请和移出操作',
    iconPath: 'M16 19a4 4 0 0 0-8 0M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7 7a3 3 0 0 0-4-2.83M17 4.5a2.5 2.5 0 1 1 0 5',
  },
  {
    key: 'pool',
    label: '账号池操作',
    mobileLabel: '账号池',
    copy: '轮转、补满、检查和清理动作',
    iconPath: 'M4 7.5 12 4l8 3.5-8 3.5L4 7.5Zm0 4L12 15l8-3.5M4 15.5 12 19l8-3.5',
  },
  {
    key: 'sync',
    label: '同步中心',
    mobileLabel: '同步',
    copy: 'CPA 对账、拉取和账号同步',
    iconPath: 'M4 12a8 8 0 0 1 13.66-5.66M20 12a8 8 0 0 1-13.66 5.66M17.5 3.5v3.5H14M6.5 20.5V17H10',
  },
  {
    key: 'oauth',
    label: 'OAuth 登录',
    mobileLabel: 'OAuth',
    copy: '手动 OAuth 回调补录账号',
    iconPath: 'M15 11a4 4 0 1 0-3.87-5M9 13a4 4 0 1 0 3.87 5M8 12h8',
  },
  {
    key: 'tasks',
    label: '任务历史',
    mobileLabel: '任务',
    copy: '回看任务状态、耗时和结果',
    iconPath: 'M12 7v5l3 3M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  },
  {
    key: 'logs',
    label: '实时日志',
    mobileLabel: '日志',
    copy: '追踪后台输出和错误信息',
    iconPath: 'M5 19V9M12 19V5M19 19v-8',
  },
  {
    key: 'settings',
    label: '系统设置',
    mobileLabel: '设置',
    copy: '管理员登录、巡检阈值与主号同步',
    iconPath: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM19.4 15a1 1 0 0 0 .2 1.1l.1.11a2 2 0 0 1-2.82 2.82l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 0 1-4 0v-.15a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 0 1-2.82-2.82l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 0 1 0-4h.15a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1A2 2 0 0 1 7.57 4l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V3a2 2 0 0 1 4 0v.15a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1A2 2 0 0 1 19.99 6l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a2 2 0 0 1 0 4h-.15a1 1 0 0 0-.9.6Z',
  },
]

const summaryCards = computed(() => {
  const summary = props.status?.summary || {}
  const running = props.tasks.filter(task => task.status === 'running' || task.status === 'pending').length
  return [
    {
      label: '活跃账号',
      value: summary.active ?? 0,
      copy: '当前在池中可直接使用的账号数量。',
    },
    {
      label: '待命账号',
      value: summary.standby ?? 0,
      copy: '额度恢复后可以重新上场的储备。',
    },
    {
      label: '后台任务',
      value: running,
      copy: running > 0 ? '有任务正在执行，发起新动作前先看状态。' : '当前没有排队任务，系统处于空闲状态。',
    },
  ]
})
</script>
