<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const stats = ref({ total: 0, available: 0, in_use: 0, used: 0, error: 0 })
const rows = ref([])
const total = ref(0)
const filter = ref('all')
const search = ref('')
const page = ref(1)
const pageSize = 50
const importText = ref('')
const importing = ref(false)
const importResult = ref(null)
const loading = ref(false)
const showImport = ref(false)

async function refresh() {
  loading.value = true
  try {
    const params = { page: page.value, size: pageSize }
    if (filter.value !== 'all') params.status = filter.value
    if (search.value.trim()) params.q = search.value.trim()
    const data = await api.listOutlookPool(params)
    rows.value = data.rows || []
    total.value = data.total || 0
    stats.value = data.stats || stats.value
  } finally {
    loading.value = false
  }
}

async function doImport() {
  if (!importText.value.trim()) return
  importing.value = true
  try {
    importResult.value = await api.importOutlookPool(importText.value)
    importText.value = ''
    await refresh()
  } catch (exc) {
    importResult.value = { error: exc.message }
  } finally {
    importing.value = false
  }
}

async function testOne(email) {
  const result = await api.testOutlookAccount(email)
  alert(result.ok ? `${email} 连接成功` : `${email} 失败: ${result.error}`)
}

async function resetOne(email) {
  if (!confirm(`重置 ${email} 为可用?`)) return
  await api.resetOutlookAccount(email)
  await refresh()
}

async function deleteOne(email) {
  if (!confirm(`删除 ${email}?该操作不可逆`)) return
  await api.deleteOutlookAccount(email)
  await refresh()
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const statusBadge = (s) => ({
  available: { text: '可用', cls: 'bg-emerald-500/20 text-emerald-300' },
  in_use: { text: '使用中', cls: 'bg-sky-500/20 text-sky-300' },
  used: { text: '已用', cls: 'bg-slate-500/20 text-slate-300' },
  error: { text: '异常', cls: 'bg-rose-500/20 text-rose-300' },
}[s] || { text: s, cls: 'bg-slate-500/20 text-slate-300' })

onMounted(refresh)
</script>

<template>
  <div class="p-6 space-y-6">
    <h1 class="text-2xl font-bold text-white">邮箱池 / Outlook</h1>

    <div class="grid grid-cols-5 gap-3">
      <div class="app-card p-4">
        <div class="text-xs text-slate-400">总数</div>
        <div class="text-2xl font-bold text-white">{{ stats.total }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-emerald-300">可用</div>
        <div class="text-2xl font-bold text-emerald-300">{{ stats.available }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-sky-300">使用中</div>
        <div class="text-2xl font-bold text-sky-300">{{ stats.in_use }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-slate-400">已用</div>
        <div class="text-2xl font-bold text-slate-300">{{ stats.used }}</div>
      </div>
      <div class="app-card p-4">
        <div class="text-xs text-rose-300">异常</div>
        <div class="text-2xl font-bold text-rose-300">{{ stats.error }}</div>
      </div>
    </div>

    <div class="app-card p-4">
      <button class="text-sm text-cyan-300 mb-2" @click="showImport = !showImport">
        {{ showImport ? '收起' : '展开' }} 批量导入
      </button>
      <div v-if="showImport" class="space-y-2">
        <textarea
          v-model="importText"
          rows="10"
          class="w-full rounded-lg bg-slate-900/50 p-3 text-sm font-mono text-slate-200"
          placeholder="email----password----client_id----refresh_token&#10;每行一个,4 段或 5 段格式"
        />
        <div class="flex gap-2">
          <button
            class="rounded-lg bg-cyan-500/20 px-4 py-2 text-cyan-200"
            :disabled="importing"
            @click="doImport"
          >
            {{ importing ? '导入中...' : '导入' }}
          </button>
          <button class="rounded-lg bg-slate-500/20 px-4 py-2" @click="importText = ''">
            清空
          </button>
        </div>
        <div v-if="importResult" class="text-sm text-slate-300">
          <template v-if="importResult.error">
            <span class="text-rose-300">导入失败: {{ importResult.error }}</span>
          </template>
          <template v-else>
            成功 {{ importResult.imported }} / 跳过 {{ importResult.skipped }}
            / 解析失败 {{ importResult.errors?.length || 0 }}
            <ul v-if="importResult.errors?.length" class="mt-2 list-disc pl-6 text-rose-300">
              <li v-for="e in importResult.errors" :key="e.line">第 {{ e.line }} 行: {{ e.reason }}</li>
            </ul>
          </template>
        </div>
      </div>
    </div>

    <div class="app-card p-4 space-y-3">
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="f in [['all', '全部'], ['available', '可用'], ['in_use', '使用中'], ['used', '已用'], ['error', '异常']]"
          :key="f[0]"
          class="rounded-lg px-3 py-1 text-sm"
          :class="filter === f[0] ? 'bg-cyan-500/30 text-cyan-200' : 'bg-slate-700/30 text-slate-300'"
          @click="filter = f[0]; page = 1; refresh()"
        >
          {{ f[1] }}
        </button>
        <input
          v-model="search"
          type="text"
          placeholder="按邮箱搜索"
          class="ml-auto rounded-lg bg-slate-900/50 px-3 py-1 text-sm text-slate-200"
          @keyup.enter="page = 1; refresh()"
        />
      </div>

      <table class="w-full text-sm">
        <thead class="text-left text-slate-400">
          <tr>
            <th class="py-2">邮箱</th>
            <th>状态</th>
            <th>添加</th>
            <th>已注册账号</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.email" class="border-t border-slate-700/30 text-slate-200">
            <td class="py-2 font-mono">{{ r.email }}</td>
            <td>
              <span class="rounded px-2 py-0.5 text-xs" :class="statusBadge(r.status).cls">
                {{ statusBadge(r.status).text }}
              </span>
              <span v-if="r.last_error" class="ml-1 text-xs text-rose-400" :title="r.last_error">⚠</span>
            </td>
            <td class="text-xs text-slate-400">
              {{ r.added_at ? new Date(r.added_at * 1000).toLocaleString() : '-' }}
            </td>
            <td class="text-xs text-slate-300">{{ r.registered_chatgpt_email || '-' }}</td>
            <td class="space-x-2">
              <button v-if="r.status !== 'used'" class="text-xs text-cyan-300" @click="testOne(r.email)">测试</button>
              <button
                v-if="r.status === 'error' || r.status === 'in_use'"
                class="text-xs text-amber-300"
                @click="resetOne(r.email)"
              >
                重置
              </button>
              <button class="text-xs text-rose-300" @click="deleteOne(r.email)">删除</button>
            </td>
          </tr>
          <tr v-if="!rows.length && !loading">
            <td colspan="5" class="py-6 text-center text-slate-500">池为空,请先批量导入。</td>
          </tr>
        </tbody>
      </table>

      <div class="flex items-center justify-between text-sm text-slate-400">
        <div>共 {{ total }} 条</div>
        <div class="space-x-2">
          <button :disabled="page <= 1" @click="page--; refresh()">‹</button>
          <span>{{ page }} / {{ totalPages }}</span>
          <button :disabled="page >= totalPages" @click="page++; refresh()">›</button>
        </div>
      </div>
    </div>
  </div>
</template>
