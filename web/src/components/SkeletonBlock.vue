<script setup lang="ts">
defineProps<{ class?: string }>();
</script>

<template>
  <div class="skeleton rounded-surface" :class="$props.class" aria-hidden="true" />
</template>
