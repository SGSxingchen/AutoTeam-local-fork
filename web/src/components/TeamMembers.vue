<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h2 class="text-2xl font-bold tracking-tight text-white">Team 成员</h2>
        <p class="mt-2 text-sm leading-6 text-slate-400">
          查看当前成员、待接受邀请和来源信息，也可以直接把非 owner 成员移出 Team。
        </p>
      </div>
      <button @click="fetchMembers" :disabled="loading" class="app-button-secondary">
        {{ loading ? '加载中...' : '刷新成员' }}
      </button>
    </div>

    <div
      v-if="error"
      class="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100"
    >
      {{ error }}
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
          <p class="mt-2 text-sm text-slate-400">还没有完成接受流程的邀请数量。</p>
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
                  <span :class="['status-pill', member.type === 'invite' ? 'border-amber-400/20 bg-amber-500/10 text-amber-200' : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200']">
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
      点击「刷新成员」加载 Team 成员列表
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'

const data = ref(null)
const loading = ref(false)
const error = ref('')
const removingId = ref('')

const CACHE_KEY = 'autoteam_team_members'

function loadCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (raw) {
      const cached = JSON.parse(raw)
      if (cached.time && Date.now() - cached.time < 600000) {
        return cached.data
      }
    }
  } catch {}
  return null
}

function saveCache(value) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ data: value, time: Date.now() }))
  } catch {}
}

function memberKey(member) {
  return `${member.type}:${member.user_id}:${member.email}`
}

function roleClass(role) {
  if (role === 'account-owner') return 'border-fuchsia-400/20 bg-fuchsia-500/10 text-fuchsia-200'
  if (role === 'account-admin') return 'border-cyan-400/20 bg-cyan-500/10 text-cyan-200'
  return 'border-slate-500/20 bg-slate-500/10 text-slate-300'
}

async function fetchMembers() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.getTeamMembers()
    saveCache(data.value)
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
    try {
      localStorage.removeItem(CACHE_KEY)
    } catch {}
    await fetchMembers()
  } catch (e) {
    error.value = e.message
  } finally {
    removingId.value = ''
  }
}

onMounted(() => {
  const cached = loadCache()
  if (cached) {
    data.value = cached
  } else {
    fetchMembers()
  }
})
</script>
