<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-white">实时日志</h2>
        <p class="mt-2 text-sm leading-6 text-slate-400">
          这里会持续拉取后台输出，方便看同步、登录和任务流程到底卡在哪一步。
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <label class="app-chip cursor-pointer">
          <input type="checkbox" v-model="autoScroll" class="h-4 w-4 rounded border-white/10 bg-slate-950/60" />
          自动滚动
        </label>
        <button @click="fetchLogs" :disabled="loading" class="app-button-secondary">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <button @click="clearLogs" class="app-button-secondary">
          清空
        </button>
      </div>
    </div>

    <div
      ref="logContainer"
      class="app-card h-[calc(100vh-230px)] min-h-[420px] overflow-y-auto p-4 font-mono text-xs leading-7 md:h-[680px]"
    >
      <div v-if="logs.length === 0" class="py-16 text-center text-slate-500">
        暂无日志
      </div>

      <div
        v-for="(log, index) in logs"
        :key="`${log.time}-${index}`"
        class="grid grid-cols-[92px_72px_minmax(0,1fr)] gap-3 rounded-2xl px-3 py-2 transition hover:bg-white/5"
      >
        <span class="text-slate-500">{{ formatTime(log.time) }}</span>
        <span :class="levelClass(log.level)">{{ log.level }}</span>
        <span class="break-all text-slate-200">{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { api } from '../api.js'

const logs = ref([])
const loading = ref(false)
const autoScroll = ref(true)
const logContainer = ref(null)

let pollTimer = null
let lastTime = 0

function formatTime(timestamp) {
  const date = new Date(timestamp * 1000)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function levelClass(level) {
  return {
    ERROR: 'text-rose-300',
    WARNING: 'text-amber-300',
    INFO: 'text-cyan-200',
    DEBUG: 'text-slate-500',
  }[level] || 'text-slate-400'
}

async function fetchLogs() {
  loading.value = true
  try {
    const result = await api.getLogs(500, lastTime)
    if (result.logs.length > 0) {
      if (lastTime === 0) {
        logs.value = result.logs
      } else {
        logs.value.push(...result.logs)
        if (logs.value.length > 1000) {
          logs.value = logs.value.slice(-1000)
        }
      }
      lastTime = result.logs[result.logs.length - 1].time
      if (autoScroll.value) {
        nextTick(() => {
          if (logContainer.value) {
            logContainer.value.scrollTop = logContainer.value.scrollHeight
          }
        })
      }
    }
  } catch (e) {
    console.error('获取日志失败:', e)
  } finally {
    loading.value = false
  }
}

function clearLogs() {
  logs.value = []
  lastTime = 0
}

onMounted(() => {
  fetchLogs()
  pollTimer = setInterval(fetchLogs, 3000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})
</script>
