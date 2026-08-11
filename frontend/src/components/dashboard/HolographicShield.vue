<template>
  <svg class="holographic-shield" viewBox="0 0 180 220" role="img" aria-label="安全审核中枢盾牌">
    <defs>
      <linearGradient id="shield-glass" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#d8f7ff" stop-opacity=".92" />
        <stop offset=".35" stop-color="#218ff4" stop-opacity=".82" />
        <stop offset="1" stop-color="#063c96" stop-opacity=".62" />
      </linearGradient>
      <linearGradient id="shield-edge" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#d9f8ff" />
        <stop offset=".42" stop-color="#4ec7ff" />
        <stop offset="1" stop-color="#0875ef" />
      </linearGradient>
      <radialGradient id="shield-core" cx="50%" cy="42%" r="60%">
        <stop offset="0" stop-color="#7bdcff" stop-opacity=".34" />
        <stop offset="1" stop-color="#168cff" stop-opacity="0" />
      </radialGradient>
      <filter id="shield-glow" x="-80%" y="-80%" width="260%" height="260%">
        <feGaussianBlur stdDeviation="4" result="blur" />
        <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>
    <ellipse class="shield-halo" cx="90" cy="112" rx="70" ry="86" fill="url(#shield-core)" />
    <path class="shield-aura" d="M90 10 155 36v66c0 45-28 77-65 98-37-21-65-53-65-98V36Z" fill="none" stroke="#168cff" stroke-opacity=".22" stroke-width="8" filter="url(#shield-glow)" />
    <path class="shield-back" d="M90 19 158 44v62c0 43-28 76-68 99" fill="none" stroke="#0a67d7" stroke-opacity=".42" stroke-width="2" transform="translate(7 7)" />
    <path class="shield-side" d="M28 38 90 14v18L45 49v50c0 27 13 49 40 68" fill="none" stroke="#6cd7ff" stroke-opacity=".34" stroke-width="2" />
    <path class="shield-face" d="M90 14 151 38v62c0 42-25 71-61 93-36-22-61-51-61-93V38Z" fill="url(#shield-glass)" stroke="url(#shield-edge)" stroke-width="2.6" />
    <path class="shield-inner" d="M90 31 133 48v50c0 30-17 52-43 69-26-17-43-39-43-69V48Z" fill="none" stroke="#a8ecff" stroke-opacity=".45" stroke-width="1.4" />
    <path class="shield-scan" d="M43 78h94" stroke="#d9f8ff" stroke-opacity=".65" stroke-width="1.4" />
    <g class="shield-core-mark" filter="url(#shield-glow)">
      <circle cx="90" cy="110" r="18" fill="#72d9ff" fill-opacity=".12" stroke="#c8f4ff" stroke-opacity=".72" stroke-width="1.5" />
      <path d="M94 88 77 111h13l-5 23 21-29H93Z" fill="#e8fbff" fill-opacity=".86" stroke="#b9f2ff" stroke-width="1.4" stroke-linejoin="round" />
      <circle cx="90" cy="110" r="3" fill="#ffffff" />
      <path d="M90 84v10M90 126v10M64 110h10M106 110h10" fill="none" stroke="#c8f4ff" stroke-opacity=".74" stroke-width="1.5" stroke-linecap="round" />
    </g>
    <path class="shield-notch" d="M90 14v18M28 82H14M152 82h14" fill="none" stroke="#72d9ff" stroke-width="2" stroke-linecap="round" />
  </svg>
</template>

<style scoped>
.holographic-shield{display:block;width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 16px rgba(22,140,255,.5))}
.shield-face{transform-origin:90px 110px;animation:shield-breathe 3.8s ease-in-out infinite}
.shield-halo{transform-origin:90px 112px;animation:shield-halo 3.8s ease-in-out infinite}
.shield-scan{animation:shield-scan 2.4s ease-in-out infinite}
.shield-back,.shield-side{animation:shield-depth 5.8s ease-in-out infinite}
.shield-core-mark{animation:shield-core-pulse 2.8s ease-in-out infinite}
@keyframes shield-breathe{0%,100%{opacity:.92;transform:scale(.99)}50%{opacity:1;transform:scale(1.012)}}
@keyframes shield-halo{0%,100%{opacity:.38;transform:scale(.94)}50%{opacity:.76;transform:scale(1.04)}}
@keyframes shield-scan{0%{opacity:0;transform:translateY(-24px)}35%,70%{opacity:.8}100%{opacity:0;transform:translateY(34px)}}
@keyframes shield-depth{0%,100%{opacity:.42;transform:translate(7px,7px)}50%{opacity:.8;transform:translate(11px,9px)}}
@keyframes shield-core-pulse{0%,100%{opacity:.64;transform:scale(.92)}50%{opacity:1;transform:scale(1.06)}}
@media(prefers-reduced-motion:reduce){.shield-face,.shield-halo,.shield-scan,.shield-back,.shield-side,.shield-core-mark{animation:none}}
</style>
