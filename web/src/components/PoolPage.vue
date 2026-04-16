<template>
  <TaskPanel
    mode="pool"
    :running-task="runningTask"
    :admin-status="adminStatus"
    @task-started="$emit('task-started')"
    @refresh="$emit('refresh')"
  />
</template>

<script setup>
import TaskPanel from './TaskPanel.vue'

defineProps({
  runningTask: Object,
  adminStatus: Object,
})

defineEmits(['task-started', 'refresh'])
</script>
