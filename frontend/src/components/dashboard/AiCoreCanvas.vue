<template>
  <canvas ref="canvasHost" class="ai-core-canvas" aria-hidden="true"></canvas>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { token } from '../../lib/screenTheme'
import { CY_RATIO, NODE_RING, SQUASH, coreBase } from '../../lib/coreGeometry'

/**
 * AI 安全大脑的能量层：轨道环、雷达扫描、数据流粒子、节点脉冲。
 *
 * 用 Canvas 2D 而不是 Three.js/WebGL：这一层只有约 500px 的发光图元，
 * WebGL 的上下文与 ~600KB 依赖换不来可见收益，Canvas 还能避免文字栅格化模糊
 * （文案与业务节点仍留在 DOM 层）。
 *
 * 该组件是纯装饰层，不渲染任何业务数值；引擎数量等状态由父组件的 DOM 承担，
 * 避免视觉动画伪造业务状态。
 */
const props = withDefaults(defineProps<{
  /** 数据流强度 0–1，驱动粒子密度与速度，用于映射真实链路负载 */
  intensity?: number
  /** 告警态：能量色偏向风险色 */
  alert?: boolean
}>(), { intensity: 0.6, alert: false })

const canvasHost = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let frame = 0
let observer: ResizeObserver | null = null
let width = 0
let height = 0
let dpr = 1
let running = false
let reduceMotion = false
let startedAt = 0
let lastFrameAt = 0

/** 四条数据通道的角度（对应四张能力卡的方位） */
const LANES = [-142, -98, -38, 38, 98, 142]

interface Particle { lane: number; t: number; speed: number; size: number }
let particles: Particle[] = []

interface Palette { accent: string; cyan: string; violet: string; ink: string; danger: string }
let palette: Palette = { accent: '#2ac9ff', cyan: '#22e3d8', violet: '#8f7dff', ink: '#eafcff', danger: '#ff4363' }

function readPalette() {
  palette = {
    accent: token('--sc-accent'),
    cyan: token('--sc-cyan'),
    violet: token('--sc-violet'),
    ink: '#eafcff',
    danger: token('--sc-critical'),
  }
}

function seedParticles() {
  const count = Math.round(26 + props.intensity * 30)
  // speed 的单位是"每秒走完通道的比例"：0.3 ≈ 3.3 秒走完一条通道
  particles = Array.from({ length: count }, (_, index) => ({
    lane: index % LANES.length,
    t: Math.random(),
    speed: 0.26 + Math.random() * 0.30 + props.intensity * 0.18,
    size: 1.1 + Math.random() * 1.9,
  }))
}

function resize() {
  const host = canvasHost.value
  if (!host) return
  // client dimensions stay in design-stage coordinates when CockpitShell scales.
  const hostWidth = host.clientWidth
  const hostHeight = host.clientHeight
  if (!hostWidth || !hostHeight) return
  // 限制 DPR：大屏常见 1.25/1.5 缩放，2 以上再放大只增加填充开销
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = hostWidth
  height = hostHeight
  host.width = Math.round(width * dpr)
  host.height = Math.round(height * dpr)
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
}

/** 发光圆点：两层叠加代替 shadowBlur（后者在大量图元下开销高） */
function glowDot(c: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, strength = 1) {
  const gradient = c.createRadialGradient(x, y, 0, x, y, r * 5)
  gradient.addColorStop(0, color)
  gradient.addColorStop(0.22, withAlpha(color, 0.42 * strength))
  gradient.addColorStop(1, withAlpha(color, 0))
  c.fillStyle = gradient
  c.beginPath()
  c.arc(x, y, r * 5, 0, Math.PI * 2)
  c.fill()
  c.fillStyle = color
  c.beginPath()
  c.arc(x, y, r, 0, Math.PI * 2)
  c.fill()
}

function withAlpha(color: string, a: number) {
  if (color.startsWith('#')) {
    const hex = color.length === 4
      ? color.slice(1).split('').map(ch => ch + ch).join('')
      : color.slice(1, 7)
    const int = Number.parseInt(hex, 16)
    return `rgba(${(int >> 16) & 255},${(int >> 8) & 255},${int & 255},${a})`
  }
  const parts = color.match(/[\d.]+/g)
  if (!parts || parts.length < 3) return color
  return `rgba(${parts[0]},${parts[1]},${parts[2]},${a})`
}

function draw(now: number) {
  if (!ctx || !width || !height) return
  const c = ctx
  const time = (now - startedAt) / 1000
  // 用真实帧间隔推进粒子，掉帧时速度不变；上限 50ms 防止切回标签页时瞬移
  const delta = lastFrameAt ? Math.min((now - lastFrameAt) / 1000, 0.05) : 0
  lastFrameAt = now
  const cx = width / 2
  const cy = height * CY_RATIO
  const base = coreBase(width, height)
  const energy = palette.accent
  const focus = props.alert ? palette.danger : palette.cyan

  c.clearRect(0, 0, width, height)

  // ---- 1. 中心体积光：让中枢"发亮"而不是"贴了个圆" ----
  const halo = c.createRadialGradient(cx, cy, 0, cx, cy, base * 1.5)
  halo.addColorStop(0, withAlpha(energy, 0.20))
  halo.addColorStop(0.34, withAlpha(energy, 0.09))
  halo.addColorStop(0.62, withAlpha(palette.violet, 0.05))
  halo.addColorStop(1, 'rgba(0,0,0,0)')
  c.fillStyle = halo
  c.fillRect(0, 0, width, height)

  // ---- 2. 三层轨道环：不同速度与虚实，制造纵深 ----
  const rings = [
    { r: base * NODE_RING, w: 1.4, alpha: 0.50, dash: [] as number[], spin: 0 },
    { r: base * 0.76, w: 1, alpha: 0.34, dash: [3, 9], spin: time * 0.16 },
    { r: base * 0.95, w: 1, alpha: 0.20, dash: [1, 7], spin: -time * 0.1 },
  ]
  for (const ring of rings) {
    c.save()
    c.translate(cx, cy)
    c.rotate(ring.spin)
    c.beginPath()
    // 轨道压扁成椭圆 → 读作"倾斜的空间轨道"而非平面圆
    c.ellipse(0, 0, ring.r, ring.r * SQUASH, 0, 0, Math.PI * 2)
    c.setLineDash(ring.dash)
    c.strokeStyle = withAlpha(energy, ring.alpha)
    c.lineWidth = ring.w
    c.stroke()
    c.restore()
  }

  // ---- 3. 雷达扫描扇形：绕内环旋转 ----
  const sweepAngle = time * 0.85
  c.save()
  c.translate(cx, cy)
  c.rotate(sweepAngle)
  const sweep = c.createConicGradient
    ? c.createConicGradient(0, 0, 0)
    : null
  if (sweep) {
    sweep.addColorStop(0, withAlpha(focus, 0.035))
    sweep.addColorStop(0.10, withAlpha(focus, 0.008))
    sweep.addColorStop(1, 'rgba(0,0,0,0)')
    c.fillStyle = sweep
  } else {
    c.fillStyle = withAlpha(focus, 0.015)
  }
  c.beginPath()
  c.moveTo(0, 0)
  c.arc(0, 0, base * NODE_RING, 0, Math.PI * 0.5)
  c.closePath()
  c.fill()
  c.restore()

  // 扫描前缘亮线
  c.save()
  c.translate(cx, cy)
  c.rotate(sweepAngle)
  c.beginPath()
  c.moveTo(0, 0)
  c.lineTo(base * NODE_RING, 0)
  c.strokeStyle = withAlpha(palette.ink, 0.12)
  c.lineWidth = 1.2
  c.stroke()
  c.restore()

  // ---- 4. 呼吸脉冲：从核心向外扩散的能量波 ----
  const pulsePhase = (time % 4.2) / 4.2
  const pulseR = base * (0.30 + pulsePhase * 0.68)
  c.save()
  c.translate(cx, cy)
  c.beginPath()
  c.ellipse(0, 0, pulseR, pulseR * SQUASH, 0, 0, Math.PI * 2)
  c.strokeStyle = withAlpha(palette.ink, 0.30 * (1 - pulsePhase))
  c.lineWidth = 1.6
  c.stroke()
  c.restore()

  // ---- 5. 八个轨道节点：沿内环缓慢公转 + 独立闪烁 ----
  const nodeCount = 8
  for (let index = 0; index < nodeCount; index += 1) {
    const angle = (index / nodeCount) * Math.PI * 2 + time * 0.11
    const r = base * NODE_RING
    const x = cx + Math.cos(angle) * r
    const y = cy + Math.sin(angle) * r * SQUASH
    const blink = 0.5 + 0.5 * Math.sin(time * 1.7 + index * 0.8)
    const major = index % 2 === 1
    // 主节点（对角）稳定亮，次节点闪烁，避免整圈同频"跑马灯"
    glowDot(c, x, y, major ? 2.6 : 1.7, major ? palette.ink : energy, major ? 1 : 0.45 + blink * 0.55)
  }

  // ---- 6. 数据流粒子：沿四条通道从能力卡汇入核心 ----
  for (const particle of particles) {
    particle.t += particle.speed * delta
    if (particle.t > 1) particle.t -= 1
    const angle = (LANES[particle.lane] * Math.PI) / 180
    // 由外向内：远端起点在 1.28×base，终点落在核心边缘
    const from = base * 1.28
    const to = base * 0.34
    const eased = particle.t * particle.t * (3 - 2 * particle.t)
    const r = from + (to - from) * eased
    const x = cx + Math.cos(angle) * r
    const y = cy + Math.sin(angle) * r * SQUASH
    // 越靠近核心越亮：视觉上读作"被吸入"
    const strength = 0.3 + eased * 0.9
    glowDot(c, x, y, particle.size, particle.lane % 2 === 0 ? palette.cyan : energy, strength)
  }

  // ---- 7. 通道导引线：极淡的虚线，提示粒子路径 ----
  c.save()
  c.translate(cx, cy)
  c.setLineDash([])
  c.strokeStyle = withAlpha(energy, 0.34)
  c.lineWidth = 1
  for (const lane of LANES) {
    const angle = (lane * Math.PI) / 180
    c.beginPath()
    c.moveTo(Math.cos(angle) * base * 0.34, Math.sin(angle) * base * SQUASH * 0.34)
    c.lineTo(Math.cos(angle) * base * 1.28, Math.sin(angle) * base * SQUASH * 1.28)
    c.stroke()
  }
  c.restore()
}

function loop(now: number) {
  if (!running) return
  draw(now)
  frame = requestAnimationFrame(loop)
}

function start() {
  if (running || reduceMotion) {
    // 降低动效时只画一帧静态构图，保留层次但不消耗持续算力
    if (reduceMotion) { startedAt = performance.now(); draw(performance.now()) }
    return
  }
  running = true
  startedAt = performance.now() - 1200 // 预跑一段，避免入场时轨道空荡
  frame = requestAnimationFrame(loop)
}

function stop() {
  running = false
  if (frame) cancelAnimationFrame(frame)
  frame = 0
  // 重置帧时间戳：切回标签页后按新起点计算 delta，粒子不会因暂停时长而瞬移
  lastFrameAt = 0
}

function handleVisibility() {
  if (document.hidden) stop()
  else start()
}

onMounted(() => {
  const host = canvasHost.value
  if (!host) return
  ctx = host.getContext('2d')
  reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  readPalette()
  seedParticles()
  resize()
  observer = new ResizeObserver(() => { resize(); if (reduceMotion) draw(performance.now()) })
  observer.observe(host)
  document.addEventListener('visibilitychange', handleVisibility)
  start()
})

onBeforeUnmount(() => {
  stop()
  observer?.disconnect()
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<style scoped>
.ai-core-canvas{position:absolute;inset:0;width:100%;height:100%;z-index:1;pointer-events:none}
</style>
