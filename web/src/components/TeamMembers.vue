<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="app-chip">
            Team 成员
          </span>
          <span
            v-if="cacheTime"
            :class="[
              'status-pill',
              isCacheFresh
                ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
                : 'border-amber-400/20 bg-amber-500/10 text-amber-200',
            ]"
          >
            {{ isCacheFresh ? '缓存可用' : '缓存偏旧' }}
          </span>
        </div>
        <h2 class="mt-3 text-2xl font-bold tracking-tight text-white">成员列表</h2>
        <p class="mt-2 text-sm leading-6 text-slate-400">
          这里现在默认优先显示本地缓存，不会一切进来就立刻打接口。要更新时你自己点刷新就行。
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <span v-if="cacheLabel" class="app-chip">
          {{ cacheLabel }}
        </span>
        <button @click="fetchMembers" :disabled="loading" class="app-button-secondary">
          {{ loading ? '刷新中...' : data ? '手动刷新' : '加载成员' }}
        </button>
      </div>
    </div>

    <div
      v-if="error"
      class="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100"
    >
      {{ error }}
    </div>

    <div
      v-if="data && cacheHint"
      class="rounded-2xl border px-4 py-3 text-sm"
      :class="isCacheFresh ? 'border-cyan-400/20 bg-cyan-500/10 text-cyan-100' : 'border-amber-400/20 bg-amber-500/10 text-amber-100'"
    >
      {{ cacheHint }}
    </div>

    <div v-if="data" class="space-y-4">
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article class="app-card-soft p-4">
          <div class="metric-label">成员总数</div>
          <div class="mt-3 text-3xl font-bold text-white">{{ data.total }}</div>
          <p class="mt-2 text-sm text-slate-400">当前 Team 中的成员与邀请总量。</p>
        </article>

        <article class="app-card-soft p-4">
          <div class="metric-label">待接受邀请</div>
          <div class="mt-3 text-3xl font-bold text-white">{{ data.invites || 0 }}</div>
          <p class="mt-2 text-sm text-slate-400">还没完成接受流程的邀请数量。</p>
        </article>
      </div>

      <div class="app-card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full min-w-[860px] text-sm">
            <thead>
              <tr class="border-b border-white/10 text-left text-slate-400">
                <th class="px-5 py-3 font-medium">#</th>
                <th class="px-5 py-3 font-medium">邮箱</th>
                <th class="px-5 py-3 font-medium">角色</th>
                <th class="px-5 py-3 font-medium">类型</th>
                <th class="px-5 py-3 font-medium">来源</th>
                <th class="px-5 py-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(member, index) in data.members"
                :key="member.email + member.type"
                class="border-b border-white/5 transition hover:bg-white/5"
              >
                <td class="px-5 py-4 text-slate-500">{{ index + 1 }}</td>
                <td class="px-5 py-4 font-mono text-xs text-white">{{ member.email }}</td>
                <td class="px-5 py-4">
                  <span :class="['status-pill', roleClass(member.role)]">
                    {{ member.role || 'member' }}
                  </span>
                </td>
                <td class="px-5 py-4">
                  <span
                    :class="[
                      'status-pill',
                      member.type === 'invite'
                        ? 'border-amber-400/20 bg-amber-500/10 text-amber-200'
                        : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
                    ]"
                  >
                    {{ member.type === 'invite' ? '待接受' : '已加入' }}
                  </span>
                </td>
                <td class="px-5 py-4">
                  <span :class="member.is_local ? 'text-cyan-200' : 'text-slate-500'">
                    {{ member.is_local ? '本地管理' : '外部' }}
                  </span>
                </td>
                <td class="px-5 py-4 text-right">
                  <button
                    v-if="member.role !== 'account-owner'"
                    @click="removeMember(member)"
                    :disabled="removingId === memberKey(member)"
                    class="app-button-danger"
                  >
                    {{ removingId === memberKey(member) ? '处理中...' : '移出' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-else-if="loading" class="app-card h-64 animate-pulse"></div>

    <div
      v-else
      class="rounded-[24px] border border-dashed border-white/10 bg-white/5 px-6 py-12 text-center text-slate-500"
    >
      <div class="text-lg font-semibold text-white">当前没有成员缓存</div>
      <p class="mt-3 text-sm leading-6 text-slate-400">
        我已经把自动拉取关掉了。需要查看最新 Team 成员时，手动点上面的“加载成员”。
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const CACHE_KEY = 'autoteam_team_members'
const CACHE_TTL_MS = 10 * 60 * 1000

const memoryCache = {
  data: null,
  time: 0,
}

const data = ref(null)
const cacheTime = ref(0)
const loading = ref(false)
const error = ref('')
const removingId = ref('')

const isCacheFresh = computed(() => {
  return !!cacheTime.value && Date.now() - cacheTime.value < CACHE_TTL_MS
})

const cacheLabel = computed(() => {
  if (!cacheTime.value) return ''
  return `缓存更新于 ${formatRelativeTime(cacheTime.value)}`
})

const cacheHint = computed(() => {
  if (!cacheTime.value) return ''
  if (isCacheFresh.value) {
    return '当前显示的是缓存快照，切页返回不会再傻乎乎重新拉成员接口。'
  }
  return '当前显示的是较旧缓存。如果你怀疑成员列表不准，再手动刷新。'
})

function readCache() {
  if (memoryCache.data && memoryCache.time) {
    return {
      data: memoryCache.data,
      time: memoryCache.time,
    }
  }

  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.data || !parsed?.time) return null
    memoryCache.data = parsed.data
    memoryCache.time = parsed.time
    return parsed
  } catch {
    return null
  }
}

function writeCache(payload) {
  const snapshot = {
    data: payload,
    time: Date.now(),
  }
  memoryCache.data = snapshot.data
  memoryCache.time = snapshot.time
  cacheTime.value = snapshot.time

  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(snapshot))
  } catch {}
}

function clearCache() {
  memoryCache.data = null
  memoryCache.time = 0
  cacheTime.value = 0
  try {
    localStorage.removeItem(CACHE_KEY)
  } catch {}
}

function restoreFromCache() {
  const cached = readCache()
  if (!cached) return false
  data.value = cached.data
  cacheTime.value = cached.time
  return true
}

function memberKey(member) {
  return `${member.type}:${member.user_id}:${member.email}`
}

function roleClass(role) {
  if (role === 'account-owner') return 'border-fuchsia-400/20 bg-fuchsia-500/10 text-fuchsia-200'
  if (role === 'account-admin') return 'border-cyan-400/20 bg-cyan-500/10 text-cyan-200'
  return 'border-slate-500/20 bg-slate-500/10 text-slate-300'
}

function formatRelativeTime(timestamp) {
  const diffMs = Math.max(0, Date.now() - timestamp)
  const diffSeconds = Math.floor(diffMs / 1000)
  if (diffSeconds < 10) return '刚刚'
  if (diffSeconds < 60) return `${diffSeconds} 秒前`
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)} 分钟前`
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(timestamp)
}

async function fetchMembers() {
  loading.value = true
  error.value = ''
  try {
    const result = await api.getTeamMembers()
    data.value = result
    writeCache(result)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function removeMember(member) {
  const actionText = member.type === 'invite' ? '取消邀请' : '移出 Team'
  const confirmed = window.confirm(`确认${actionText} ${member.email}？`)
  if (!confirmed) return

  removingId.value = memberKey(member)
  error.value = ''
  try {
    await api.removeTeamMember({
      email: member.email,
      user_id: member.user_id,
      type: member.type,
    })
    clearCache()
    await fetchMembers()
  } catch (e) {
    error.value = e.message
  } finally {
    removingId.value = ''
  }
}

onMounted(() => {
  restoreFromCache()
})
</script>
