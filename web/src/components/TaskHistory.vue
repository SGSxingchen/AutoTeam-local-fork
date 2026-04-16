<template>
  <div class="app-card overflow-hidden">
    <div class="flex flex-col gap-2 border-b border-white/10 px-5 py-4 md:flex-row md:items-end md:justify-between">
      <div>
        <h2 class="text-xl font-bold text-white">任务历史</h2>
        <p class="mt-1 text-sm text-slate-400">
          回看后台任务的状态、参数、耗时和结果，方便排查问题。
        </p>
      </div>
      <span class="app-chip">
        共 <strong class="text-white">{{ tasks.length }}</strong> 条
      </span>
    </div>

    <div v-if="tasks.length === 0" class="px-5 py-12 text-center text-sm text-slate-500">
      暂无任务记录
    </div>

    <div v-else class="overflow-x-auto">
      <table class="w-full min-w-[920px] text-sm">
        <thead>
          <tr class="border-b border-white/10 text-left text-slate-400">
            <th class="px-5 py-3 font-medium">任务 ID</th>
            <th class="px-5 py-3 font-medium">命令</th>
            <th class="px-5 py-3 font-medium">参数</th>
            <th class="px-5 py-3 font-medium">状态</th>
            <th class="px-5 py-3 font-medium">创建时间</th>
            <th class="px-5 py-3 font-medium">耗时</th>
            <th class="px-5 py-3 font-medium">结果</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="task in tasks"
            :key="task.task_id"
            class="border-b border-white/5 transition hover:bg-white/5"
          >
            <td class="px-5 py-4 font-mono text-xs text-slate-400">{{ task.task_id }}</td>
            <td class="px-5 py-4">
              <span class="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-slate-200">
                {{ task.command }}
              </span>
            </td>
            <td class="px-5 py-4 text-xs text-slate-400">{{ formatParams(task.params) }}</td>
            <td class="px-5 py-4">
              <span :class="['status-pill', taskStatusClass(task.status)]">
                <span
                  v-if="task.status === 'running'"
                  class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                ></span>
                <span
                  v-else
                  class="h-2 w-2 rounded-full bg-current"
                ></span>
                {{ taskStatusLabel(task.status) }}
              </span>
            </td>
            <td class="px-5 py-4 text-xs text-slate-400">{{ formatTime(task.created_at) }}</td>
            <td class="px-5 py-4 text-xs text-slate-400">{{ duration(task) }}</td>
            <td class="max-w-sm px-5 py-4 text-xs" :class="task.error ? 'text-rose-200' : 'text-slate-400'">
              <div class="truncate">{{ task.error || formatResult(task.result) }}</div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  tasks: { type: Array, default: () => [] },
})

function taskStatusClass(status) {
  return {
    pending: 'border-slate-500/20 bg-slate-500/10 text-slate-300',
    running: 'border-amber-400/20 bg-amber-500/10 text-amber-200',
    completed: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
    failed: 'border-rose-400/20 bg-rose-500/10 text-rose-200',
  }[status] || 'border-slate-500/20 bg-slate-500/10 text-slate-300'
}

function taskStatusLabel(status) {
  return {
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
  }[status] || status
}

function formatTime(timestamp) {
  if (!timestamp) return '-'
  const date = new Date(timestamp * 1000)
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function duration(task) {
  const start = task.started_at || task.created_at
  const end = task.finished_at || (task.status === 'running' ? Date.now() / 1000 : null)
  if (!start || !end) return '-'
  const seconds = Math.round(end - start)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s`
}

function formatParams(params) {
  if (!params || Object.keys(params).length === 0) return '-'
  return Object.entries(params).map(([key, value]) => `${key}=${value}`).join(', ')
}

function formatResult(result) {
  if (result === null || result === undefined) return '-'
  if (typeof result === 'string') return result
  return JSON.stringify(result)
}
</script>
