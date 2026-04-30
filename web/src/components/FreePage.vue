<template>
  <section class="space-y-6">
    <div v-if="!loaded" class="app-card p-6 text-slate-300">
      加载中...
    </div>

    <div v-else-if="!enabled" class="app-card p-6">
      <div class="max-w-3xl space-y-3">
        <h2 class="text-lg font-semibold text-white">Free 账号注册未启用</h2>
        <p class="text-sm leading-6 text-slate-300">
          请在 <code class="rounded bg-white/10 px-1.5 py-0.5">.env</code> 中配置
          <code class="rounded bg-white/10 px-1.5 py-0.5">CLOUDMAIL_FREE_DOMAIN=@your-domain.com</code> 后重启服务。
        </p>
        <p class="text-sm leading-6 text-amber-200">
          该域名必须与 <code class="rounded bg-white/10 px-1.5 py-0.5">CLOUDMAIL_DOMAIN</code>
          不同，否则新注册账号会被自动拉进 Team。
        </p>
      </div>
    </div>

    <template v-else>
      <div class="app-card p-5">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div class="space-y-2">
            <h2 class="text-xl font-semibold text-white">Free 账号</h2>
            <p class="max-w-3xl text-sm leading-6 text-slate-400">
              独立域名注册，不参与 Team 轮转；Codex 认证会与 Team active 账号一起同步到 CPA。
            </p>
          </div>

          <div class="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label class="text-sm text-slate-300">
              数量
              <input
                v-model.number="count"
                type="number"
                min="1"
                max="50"
                class="app-input ml-0 mt-1 w-24 sm:ml-2 sm:mt-0"
              />
            </label>
            <button @click="onCreate" :disabled="busy" class="app-button-primary">
              {{ busy ? '任务进行中...' : '批量创建' }}
            </button>
            <button @click="reload" :disabled="busy" class="app-button-secondary">
              刷新列表
            </button>
          </div>
        </div>

        <p v-if="message" class="mt-4 text-sm" :class="messageTone">
          {{ message }}
        </p>
      </div>

      <div class="app-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full min-w-[860px] table-fixed text-sm">
            <thead class="bg-white/5 text-slate-400">
              <tr>
                <th class="p-3 text-left">邮箱</th>
                <th class="w-44 p-3 text-left">创建时间</th>
                <th class="w-44 p-3 text-left">最后刷新</th>
                <th class="w-24 p-3 text-left">auth</th>
                <th class="w-48 p-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="accounts.length === 0">
                <td colspan="5" class="p-8 text-center text-slate-400">还没有 Free 账号</td>
              </tr>
              <tr v-for="acc in accounts" :key="acc.email" class="border-t border-white/5">
                <td class="truncate p-3 text-slate-100" :title="acc.email">{{ acc.email }}</td>
                <td class="p-3 text-slate-400">{{ formatTimestamp(acc.created_at) }}</td>
                <td class="p-3 text-slate-400">{{ formatTimestamp(acc.last_refreshed_at) }}</td>
                <td class="p-3">
                  <span
                    :class="[
                      'status-pill',
                      acc.auth_file_exists
                        ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
                        : 'border-rose-400/20 bg-rose-500/10 text-rose-200',
                    ]"
                    :title="acc.last_error || ''"
                  >
                    {{ acc.auth_file_exists ? '存在' : '缺失' }}
                  </span>
                </td>
                <td class="space-x-2 p-3 text-right">
                  <button @click="onRefresh(acc.email)" :disabled="busy" class="app-button-secondary px-3 py-1.5 text-xs">
                    刷新
                  </button>
                  <button @click="onDelete(acc.email)" :disabled="busy" class="app-button-danger px-3 py-1.5 text-xs">
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api.js'

const loaded = ref(false)
const enabled = ref(false)
const accounts = ref([])
const count = ref(1)
const message = ref('')
const tone = ref('info')
const currentTaskId = ref(null)
let pollTimer = null

const busy = computed(() => currentTaskId.value !== null)
const messageTone = computed(() => ({
  info: 'text-slate-400',
  success: 'text-emerald-300',
  warn: 'text-amber-300',
  error: 'text-rose-300',
}[tone.value] || 'text-slate-400')
)

function setMessage(text, nextTone = 'info') {
  message.value = text
  tone.value = nextTone
}

function formatTimestamp(timestamp) {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN', { hour12: false })
}

async function reload() {
  try {
    const data = await api.listFreeAccounts()
    enabled.value = Boolean(data.enabled)
    accounts.value = data.accounts || []
  } catch (error) {
    setMessage(`加载失败: ${error.message}`, 'error')
  } finally {
    loaded.value = true
  }
}

function stopPollingTask() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPollingTask(taskId, label) {
  currentTaskId.value = taskId
  setMessage(`${label}进行中...`, 'info')
  stopPollingTask()
  pollTimer = setInterval(async () => {
    try {
      const task = await api.getTask(taskId)
      if (task.status !== 'completed' && task.status !== 'failed') return

      stopPollingTask()
      currentTaskId.value = null
      if (task.status === 'completed') {
        const result = task.result || {}
        if (Array.isArray(result.succeeded) && Array.isArray(result.failed)) {
          setMessage(
            `${label}完成: 成功 ${result.succeeded.length}, 失败 ${result.failed.length}`,
            result.failed.length ? 'warn' : 'success',
          )
        } else {
          setMessage(`${label}完成`, 'success')
        }
      } else {
        setMessage(`${label}失败: ${task.error || '未知错误'}`, 'error')
      }
      await reload()
    } catch (error) {
      stopPollingTask()
      currentTaskId.value = null
      setMessage(`查询任务失败: ${error.message}`, 'error')
    }
  }, 2000)
}

async function onCreate() {
  const value = Number(count.value) || 0
  if (value < 1 || value > 50) {
    setMessage('数量需在 1..50', 'warn')
    return
  }
  try {
    const task = await api.createFreeAccounts(value)
    startPollingTask(task.task_id, `创建 ${value} 个 Free 账号`)
  } catch (error) {
    setMessage(`提交创建失败: ${error.message}`, 'error')
  }
}

async function onRefresh(email) {
  try {
    const task = await api.refreshFreeAccount(email)
    startPollingTask(task.task_id, `刷新 ${email}`)
  } catch (error) {
    setMessage(`提交刷新失败: ${error.message}`, 'error')
  }
}

async function onDelete(email) {
  if (!window.confirm(`确定删除 ${email}？\n会同时删除 CPA、本地 auth 和 CloudMail 临时邮箱。`)) return
  try {
    const task = await api.deleteFreeAccount(email)
    startPollingTask(task.task_id, `删除 ${email}`)
  } catch (error) {
    setMessage(`提交删除失败: ${error.message}`, 'error')
  }
}

onMounted(reload)
onUnmounted(stopPollingTask)
</script>
