<template><div class="cockpit-shell"><div class="cockpit-ambient" aria-hidden="true"></div><slot /></div></template>
<style scoped>
.cockpit-shell{position:fixed;inset:0;z-index:500;display:flex;min-width:1024px;min-height:640px;flex-direction:column;gap:var(--screen-gap);padding:var(--space-3) var(--screen-gutter) var(--space-2);overflow:hidden;color:var(--screen-text-secondary);background:var(--screen-bg);font-family:var(--font-body)}
.cockpit-ambient{position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 46% 44% at 50% 42%,rgba(20,112,192,.18),transparent 68%),radial-gradient(ellipse 34% 32% at 12% 76%,rgba(104,78,224,.10),transparent 66%),radial-gradient(ellipse 30% 30% at 88% 22%,rgba(0,214,208,.07),transparent 66%),linear-gradient(rgba(74,158,208,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(74,158,208,.035) 1px,transparent 1px);background-size:auto,auto,auto,58px 58px,58px 58px}
.cockpit-shell :deep(>*){position:relative;z-index:1;box-sizing:border-box}:global(body:has(.cockpit-shell)){overflow:hidden}
@media(max-width:1199px){.cockpit-shell{padding:var(--space-2) 10px 6px;gap:9px}}
</style>
