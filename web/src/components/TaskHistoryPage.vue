<template>
  <TaskHistory :tasks="tasks" />
</template>

<script setup>
import TaskHistory from './TaskHistory.vue'

defineProps({
  tasks: Array,
})
</script>
