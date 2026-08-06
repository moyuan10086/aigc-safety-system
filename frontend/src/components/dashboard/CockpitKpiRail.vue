<template><section class="kpi-rail" aria-label="实时态势指标"><slot /></section></template>
<style scoped>.kpi-rail{display:flex;gap:var(--screen-gap);height:var(--screen-kpi-height)}.kpi-rail :deep(>*){flex:1;min-width:0}@media(max-width:1199px){.kpi-rail{gap:9px;height:70px}}</style>
