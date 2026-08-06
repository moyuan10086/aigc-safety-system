<template><SecurityPipeline :configured="configuredModels" :total="totalModels" :alert="!auditHealthy || !running" /></template>
<script setup lang="ts">import SecurityPipeline from './SecurityPipeline.vue'; defineProps<{ configuredModels:number; totalModels:number; auditHealthy:boolean; running:boolean }>()</script>
