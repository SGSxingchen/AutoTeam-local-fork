<template>
  <nav class="w-48 shrink-0 bg-gray-900 border-r border-gray-800 min-h-screen p-4 space-y-1">
    <div class="mb-6">
      <h1 class="text-lg font-bold text-white">AutoTeam</h1>
      <p class="text-xs text-gray-500 mt-0.5">账号轮转管理</p>
    </div>
    <button v-for="item in items" :key="item.key"
      @click="$emit('navigate', item.key)"
      class="w-full text-left px-3 py-2 rounded-lg text-sm transition flex items-center gap-2"
      :class="active === item.key
        ? 'bg-blue-600/20 text-blue-400'
        : 'text-gray-400 hover:bg-gray-800 hover:text-white'">
      <span class="text-base">{{ item.icon }}</span>
      {{ item.label }}
    </button>
  </nav>
</template>

<script setup>
defineProps({
  active: String,
})
defineEmits(['navigate'])

const items = [
  { key: 'dashboard', icon: '📊', label: '仪表盘' },
  { key: 'team', icon: '👥', label: 'Team 成员' },
  { key: 'tasks', icon: '⚡', label: '操作 & 任务' },
  { key: 'logs', icon: '📋', label: '日志' },
  { key: 'settings', icon: '⚙️', label: '设置' },
]
</script>
