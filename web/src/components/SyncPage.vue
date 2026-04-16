<template>
  <TaskPanel
    mode="sync"
    :running-task="runningTask"
    :admin-status="adminStatus"
    @task-started="$emit('task-started')"
    @refresh="$emit('refresh')"
    @accounts-synced="$emit('accounts-synced', $event)"
  />
</template>

<script setup>
import TaskPanel from './TaskPanel.vue'

defineProps({
  runningTask: Object,
  adminStatus: Object,
})

defineEmits(['task-started', 'refresh', 'accounts-synced'])
</script>
