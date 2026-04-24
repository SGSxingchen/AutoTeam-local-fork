<template>
  <div class="app-card p-5 md:p-6">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-white">{{ panelTitle }}</h2>
        <p class="mt-2 text-sm leading-6 text-slate-400">
          {{ panelCopy }}
        </p>
      </div>

      <span
        :class="[
          'status-pill shrink-0',
          props.runningTask
            ? 'border-amber-400/20 bg-amber-500/10 text-amber-200'
            : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
        ]"
      >
        <span class="h-2 w-2 rounded-full bg-current"></span>
        {{ taskStatusText }}
      </span>
    </div>

    <div
      v-if="showAdminHint"
      class="mt-5 rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-4 text-sm text-amber-100"
    >
      {{ adminHint }}
    </div>

    <div class="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      <button
        v-for="action in visibleActions"
        :key="action.key"
        @click="execute(action)"
        :disabled="isDisabled(action)"
        :class="[
          'rounded-[24px] border p-4 text-left transition',
          isDisabled(action)
            ? 'cursor-not-allowed border-white/10 bg-slate-900/50 text-slate-500'
            : 'border-white/10 bg-white/5 text-white hover:border-cyan-400/20 hover:bg-cyan-400/10',
        ]"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="text-base font-semibold">{{ action.label }}</div>
          <span
            :class="[
              'rounded-full px-2.5 py-1 text-[11px] font-medium',
              action.sync
                ? 'bg-emerald-500/15 text-emerald-200'
                : action.needParam
                  ? 'bg-cyan-500/15 text-cyan-200'
                  : 'bg-violet-500/15 text-violet-200',
            ]"
          >
            {{ action.sync ? '即时执行' : action.needParam ? '需要参数' : '后台任务' }}
          </span>
        </div>
        <p class="mt-3 text-sm leading-6 text-slate-400">
          {{ action.copy }}
        </p>
      </button>
    </div>

    <div
      v-if="showParams && pendingAction"
      class="mt-5 rounded-[24px] border border-cyan-400/20 bg-cyan-500/10 p-4"
    >
      <div class="text-sm font-semibold text-cyan-100">
        {{ pendingAction.label }} 需要输入参数
      </div>
      <p class="mt-2 text-sm leading-6 text-cyan-100/80">
        {{ paramHelp }}
      </p>
      <div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          v-model.number="paramValue"
          type="number"
          min="1"
          max="20"
          class="app-input w-full sm:max-w-[140px]"
        />
        <div class="flex flex-wrap gap-3">
          <button
            @click="confirmAction"
            :disabled="pendingAction && isDisabled(pendingAction)"
            class="app-button-primary"
          >
            确认执行
          </button>
          <button @click="cancelParamInput" class="app-button-secondary">
            取消
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="message"
      class="mt-5 rounded-2xl border px-4 py-3 text-sm"
      :class="messageClass"
    >
      {{ message }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  runningTask: {
    type: Object,
    default: null,
  },
  adminStatus: {
    type: Object,
    default: null,
  },
  mode: {
    type: String,
    default: 'all',
  },
})

const taskStatusText = computed(() => {
  if (!props.runningTask) return '当前空闲'
  if (props.runningTask.status === 'queued') return '后台任务排队中'
  return '后台任务进行中'
})

const emit = defineEmits(['task-started', 'refresh', 'accounts-synced'])

const actions = [
  {
    key: 'rotate',
    group: 'pool',
    label: '智能轮转',
    copy: '按目标成员数自动调度账号，把额度紧张的成员从当前流程里换下来。',
    method: 'startRotate',
    needParam: true,
    paramName: 'target',
  },
  {
    key: 'check',
    group: 'pool',
    label: '检查额度',
    copy: '立即刷新账号额度缓存，适合在大动作前先看一遍真实状态。',
    method: 'startCheck',
    needParam: false,
  },
  {
    key: 'fill',
    group: 'pool',
    label: '补满成员',
    copy: '把 Team 成员补到目标数量，适合轮转之后快速回到稳定规模。',
    method: 'startFill',
    needParam: true,
    paramName: 'target',
  },
  {
    key: 'add',
    group: 'pool',
    label: '添加账号',
    copy: '发起新增账号流程，把新账号逐步拉进本地池子和 Team 里。',
    method: 'startAdd',
    needParam: false,
  },
  {
    key: 'cleanup',
    group: 'pool',
    label: '清理成员',
    copy: '清掉多余或不该留在 Team 里的成员，适合混乱后做一次收口。',
    method: 'startCleanup',
    needParam: false,
  },
  {
    key: 'sync',
    group: 'sync',
    label: '同步 CPA',
    copy: '把本地认证状态推到 CPA 侧，让外部依赖拿到最新文件。',
    method: 'postSync',
    needParam: false,
    sync: true,
    allowWithoutAdmin: true,
  },
  {
    key: 'pull-cpa',
    group: 'sync',
    label: '拉取 CPA',
    copy: '从 CPA 反向拉认证文件到本地，适合对账和补齐缺失状态。',
    method: 'postSyncFromCpa',
    needParam: false,
    sync: true,
    allowWithoutAdmin: true,
  },
  {
    key: 'sync-accounts',
    group: 'sync',
    label: '同步账号',
    copy: '对齐本地账号池记录，刷新活跃、待命和额度耗尽状态。',
    method: 'postSyncAccounts',
    needParam: false,
    sync: true,
    allowWithoutAdmin: true,
  },
]

const showParams = ref(false)
const paramValue = ref(5)
const pendingAction = ref(null)
const message = ref('')
const messageClass = ref('')

const adminReady = computed(() => !!props.adminStatus?.configured)
const visibleActions = computed(() => {
  if (props.mode === 'all') return actions
  return actions.filter(action => action.group === props.mode)
})
const panelTitle = computed(() => {
  if (props.mode === 'pool') return '账号池动作区'
  if (props.mode === 'sync') return '同步动作区'
  return '操作中心'
})
const panelCopy = computed(() => {
  if (props.mode === 'pool') {
    return '轮转、补满、检查和清理都会直接影响账号池状态。建议先确认管理员登录已完成。'
  }
  if (props.mode === 'sync') {
    return '这里处理本地、CPA 和账号记录之间的同步关系，偏对账和状态修复。'
  }
  return '所有动作都会在这里集中发起。系统忙碌时会自动禁用，避免任务撞车。'
})
const adminHint = computed(() => {
  if (props.mode === 'sync') {
    return '同步类动作可以独立执行：同步账号、同步 CPA、拉取 CPA 不依赖管理员登录。'
  }
  return '管理员未登录时，轮转、补满、添加和清理这类会影响 Team 结构的动作会被锁住。'
})
const showAdminHint = computed(() => !adminReady.value && (props.mode === 'pool' || props.mode === 'sync'))
const paramHelp = computed(() => {
  if (!pendingAction.value) return ''
  if (pendingAction.value.paramName === 'target') {
    return '输入希望补到或轮转到的目标成员数。系统会按这个值发起后台任务。'
  }
  return '输入这个动作需要的参数值，再确认执行。'
})

function isDisabled(action) {
  if (props.runningTask && action.sync) return true
  if (!adminReady.value && !action.allowWithoutAdmin) return true
  return false
}

async function execute(action) {
  if (isDisabled(action)) return
  message.value = ''
  if (action.needParam) {
    pendingAction.value = action
    paramValue.value = 5
    showParams.value = true
    return
  }
  await doExecute(action)
}

async function confirmAction() {
  showParams.value = false
  if (pendingAction.value) {
    await doExecute(pendingAction.value, paramValue.value)
    pendingAction.value = null
  }
}

function cancelParamInput() {
  pendingAction.value = null
  showParams.value = false
}

async function doExecute(action, param) {
  try {
    if (action.sync) {
      const result = await api[action.method]()
      message.value = result.message || '操作完成'
      messageClass.value = 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100'
      if (action.key === 'sync-accounts' && Array.isArray(result.accounts)) {
        emit('accounts-synced', result)
      } else {
        emit('refresh')
      }
    } else {
      const result = await api[action.method](param)
      message.value = `任务已提交：${result.task_id}`
      messageClass.value = 'border-cyan-400/20 bg-cyan-500/10 text-cyan-100'
      emit('task-started')
    }
  } catch (e) {
    message.value = e.message
    messageClass.value = 'border-rose-400/20 bg-rose-500/10 text-rose-100'
  }

  window.clearTimeout(doExecute._timer)
  doExecute._timer = window.setTimeout(() => {
    message.value = ''
  }, 8000)
}
</script>
