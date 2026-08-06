<template><BaseChart :option="option" :aria-label="ariaLabel" dark suppress-tooltip /></template>
<script setup lang="ts">import type { EChartsCoreOption } from 'echarts/core'; import BaseChart from './BaseChart.vue'; defineProps<{option:EChartsCoreOption;ariaLabel:string}>()</script>
