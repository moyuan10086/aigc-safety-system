<template>
  <canvas ref="canvasHost" class="ai-core-scene" aria-hidden="true"></canvas>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'

const props = withDefaults(defineProps<{ alert?: boolean }>(), { alert: false })

const canvasHost = ref<HTMLCanvasElement | null>(null)
let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let coreGroup: THREE.Group | null = null
let animationFrame = 0
let observer: ResizeObserver | null = null
let reduceMotion = false
let running = false
let particleCloud: THREE.Points | null = null
const animatedRings: THREE.Mesh[] = []
const energySegments: THREE.Mesh[] = []
const orbitRunners: THREE.Group[] = []
const rotatingOrbits: THREE.Group[] = []
const rotatingRings: THREE.Group[] = []

function metal(color: number, emissive = 0x000000, emissiveIntensity = 0, opacity = 1) {
  return new THREE.MeshStandardMaterial({
    color,
    emissive,
    emissiveIntensity,
    metalness: 0.78,
    roughness: 0.24,
    transparent: opacity < 1,
    opacity,
    depthWrite: opacity === 1,
  })
}

function createCylinder(radius: number, height: number, y: number, material: THREE.Material) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius * 1.03, height, 96, 1, false), material)
  mesh.position.y = y
  return mesh
}

function createRing(radius: number, tube: number, y: number, color: number, opacity = 1) {
  const material = new THREE.MeshBasicMaterial({
    color,
    transparent: opacity < 1,
    opacity,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 16, 128), material)
  ring.rotation.x = Math.PI / 2
  ring.position.y = y
  animatedRings.push(ring)
  return ring
}

function buildCore() {
  if (!scene) return
  const group = new THREE.Group()
  coreGroup = group
  // WebGL 透视中的圆台视觉中心需要与 DOM 业务中枢轴线重合。
  // Keep the WebGL object on the same logical center as the DOM shield.
  // Perspective is created by the camera and tilted orbit layers, not by an
  // arbitrary x/y translation that makes the core look misaligned.
  group.position.set(0, 0, 0)
  scene.add(group)

  const base = createCylinder(2.72, 0.42, -0.48, metal(0x03152f, 0x064aa8, 0.42, 0.26))
  group.add(base)

  const lowerBevel = createCylinder(2.48, 0.14, -0.12, metal(0x041d46, 0x075ed0, 0.42, 0.22))
  group.add(lowerBevel)

  const belt = createCylinder(2.30, 0.24, 0.13, metal(0x03183b, 0x0868d8, 0.38, 0.18))
  group.add(belt)

  const topDeck = createCylinder(2.02, 0.10, 0.39, metal(0x092b5c, 0x0a78e8, 0.42, 0.16))
  group.add(topDeck)

  const glass = new THREE.Mesh(
    new THREE.SphereGeometry(1.78, 96, 48, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshPhysicalMaterial({
      color: 0x1769c7,
      emissive: 0x064aa8,
      emissiveIntensity: 0.32,
      transparent: true,
      opacity: 0.11,
      roughness: 0.16,
      metalness: 0.1,
      transmission: 0.62,
      clearcoat: 1,
      clearcoatRoughness: 0.12,
      depthWrite: false,
    }),
  )
  glass.scale.y = 0.42
  glass.position.y = 0.60
  group.add(glass)

  const hologramShell = new THREE.Mesh(
    new THREE.SphereGeometry(2.12, 48, 24),
    new THREE.MeshBasicMaterial({
      color: 0x168cff,
      transparent: true,
      opacity: 0.018,
      wireframe: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  hologramShell.scale.y = 0.58
  hologramShell.position.y = 0.56
  group.add(hologramShell)

  group.add(createRing(2.68, 0.016, -0.72, 0x075ac8, 0.54))
  group.add(createRing(2.38, 0.022, 0.02, 0x168cff, 0.72))
  group.add(createRing(2.05, 0.016, 0.63, 0x37aaff, 0.62))
  group.add(createRing(1.58, 0.010, 0.78, 0x72d9ff, 0.46))
  group.add(createRing(2.54, 0.032, -0.28, 0x0b65d4, 0.46))
  group.add(createRing(2.22, 0.024, 0.30, 0x1b9aff, 0.54))

  // Tilted orbital hoops provide the perspective cue visible in sci-fi HUDs.
  for (const [index, tilt] of [-0.46, 0.46].entries()) {
    const orbitLayer = new THREE.Group()
    orbitLayer.rotation.x = tilt
    orbitLayer.rotation.z = tilt * 0.72
    orbitLayer.position.y = 0.28
    const orbit = createRing(2.58, 0.012, 0, 0x128dff, 0.38)
    orbitLayer.add(orbit)
    const runner = new THREE.Group()
    runner.userData.speed = index ? -0.72 : 0.58
    const bead = new THREE.Mesh(
      new THREE.SphereGeometry(0.075, 18, 18),
      new THREE.MeshBasicMaterial({ color: 0xbcefff, blending: THREE.AdditiveBlending, transparent: true, opacity: 0.95, depthWrite: false }),
    )
    bead.position.x = 2.58
    runner.add(bead)
    const trail = new THREE.PointLight(0x169dff, 3.2, 1.8, 2)
    trail.position.x = 2.58
    runner.add(trail)
    orbitLayer.add(runner)
    orbitRunners.push(runner)
    rotatingOrbits.push(orbitLayer)
    group.add(orbitLayer)
  }

  const segmentGeometry = new THREE.BoxGeometry(0.38, 0.22, 0.12)
  const segmentRing = new THREE.Group()
  segmentRing.position.y = 0.27
  rotatingRings.push(segmentRing)
  group.add(segmentRing)
  for (let index = 0; index < 24; index += 1) {
    const angle = (index / 24) * Math.PI * 2
    const accent = index % 4 === 0
    const segment = new THREE.Mesh(
      segmentGeometry,
      new THREE.MeshStandardMaterial({
        color: accent ? 0x2da9ff : (index % 2 ? 0x0a477f : 0x0b70bf),
        emissive: accent ? 0x65d8ff : 0x087ed9,
        emissiveIntensity: accent ? 1.05 : (index % 2 ? 0.24 : 0.62),
        metalness: 0.42,
        roughness: 0.28,
        transparent: true,
        opacity: 0.62,
        depthWrite: false,
      }),
    )
    segment.position.set(Math.cos(angle) * 2.33, 0, Math.sin(angle) * 2.33)
    segment.rotation.y = -angle
    segmentRing.add(segment)
    energySegments.push(segment)
  }

  const coreLight = new THREE.Mesh(
    new THREE.CylinderGeometry(0.18, 0.34, 0.52, 48, 1, true),
    new THREE.MeshBasicMaterial({
      color: 0x3bc6ff,
      transparent: true,
      opacity: 0.10,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  )
  coreLight.position.y = 0.94
  group.add(coreLight)

  const upperHalo = new THREE.Mesh(
    new THREE.CircleGeometry(1.56, 96),
    new THREE.MeshBasicMaterial({
      color: 0x0d75c8,
      transparent: true,
      opacity: 0.07,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  )
  upperHalo.rotation.x = -Math.PI / 2
  upperHalo.position.y = 0.83
  group.add(upperHalo)

  const particlePositions = new Float32Array(260 * 3)
  for (let index = 0; index < 260; index += 1) {
    const angle = Math.random() * Math.PI * 2
    const radius = 1.4 + Math.random() * 2.2
    particlePositions[index * 3] = Math.cos(angle) * radius
    particlePositions[index * 3 + 1] = -0.35 + Math.random() * 2.35
    particlePositions[index * 3 + 2] = Math.sin(angle) * radius
  }
  const particleGeometry = new THREE.BufferGeometry()
  particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3))
  particleCloud = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({
      color: 0x44c8ff,
      size: 0.045,
      transparent: true,
      opacity: 0.62,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    }),
  )
  group.add(particleCloud)
}

function resize() {
  const canvas = canvasHost.value
  if (!canvas || !renderer || !camera) return
  const width = canvas.clientWidth
  const height = canvas.clientHeight
  if (!width || !height) return
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75))
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  render()
}

function render(time = 0) {
  if (!renderer || !scene || !camera || !coreGroup) return
  const seconds = time / 1000
  if (!reduceMotion) {
    coreGroup.rotation.y = Math.sin(seconds * 0.18) * 0.035
    animatedRings.forEach((ring, index) => {
      ring.rotation.z = seconds * (index % 2 ? -0.18 : 0.13)
    })
    energySegments.forEach((segment, index) => {
      const material = segment.material as THREE.MeshStandardMaterial
      const accent = index % 4 === 0
      material.emissiveIntensity = accent
        ? 0.72 + (Math.sin(seconds * 2.2 - index * 0.34) + 1) * 0.42
        : 0.22 + (Math.sin(seconds * 2.2 - index * 0.34) + 1) * 0.24
    })
    if (particleCloud) {
      particleCloud.rotation.y = seconds * 0.08
      particleCloud.position.y = Math.sin(seconds * 0.7) * 0.04
    }
    orbitRunners.forEach((runner, index) => {
      runner.rotation.y = seconds * runner.userData.speed + index * Math.PI
    })
    rotatingOrbits.forEach((orbit, index) => {
      orbit.rotation.y = seconds * (index ? -0.16 : 0.12)
      orbit.rotation.z += (index ? -1 : 1) * 0.0008
    })
    rotatingRings.forEach((ring, index) => {
      ring.rotation.y = seconds * (index ? -0.10 : 0.14)
    })
  }
  renderer.render(scene, camera)
}

function loop(time: number) {
  if (!running) return
  render(time)
  animationFrame = requestAnimationFrame(loop)
}

function start() {
  if (running) return
  if (reduceMotion) {
    render()
    return
  }
  running = true
  animationFrame = requestAnimationFrame(loop)
}

function stop() {
  running = false
  if (animationFrame) cancelAnimationFrame(animationFrame)
  animationFrame = 0
}

function disposeObject(object: THREE.Object3D) {
  if (object instanceof THREE.Mesh || object instanceof THREE.Points) {
    object.geometry.dispose()
    const materials = Array.isArray(object.material) ? object.material : [object.material]
    materials.forEach(material => material.dispose())
  }
}

function rememberMaterialState() {
  scene?.traverse(object => {
    if (!(object instanceof THREE.Mesh) || !(object.material instanceof THREE.MeshStandardMaterial)) return
    object.material.userData.coreEmissive = object.material.emissive.getHex()
    object.material.userData.coreEmissiveIntensity = object.material.emissiveIntensity
  })
}

function updateAlertState() {
  if (!scene) return
  scene.traverse(object => {
    if (!(object instanceof THREE.Mesh) || !(object.material instanceof THREE.MeshStandardMaterial)) return
    if (props.alert) {
      object.material.emissive.setHex(0x7b1730)
      object.material.emissiveIntensity = Math.max(object.material.emissiveIntensity, 0.32)
    } else if (object.material.userData.coreEmissive !== undefined) {
      object.material.emissive.setHex(object.material.userData.coreEmissive)
      object.material.emissiveIntensity = object.material.userData.coreEmissiveIntensity
    }
  })
  render()
}

function handleVisibility() {
  if (document.hidden) stop()
  else start()
}

onMounted(() => {
  const canvas = canvasHost.value
  if (!canvas) return
  reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'high-performance' })
  renderer.setClearColor(0x000000, 0)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.18

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100)
  camera.position.set(0, 5.4, 9.2)
  camera.lookAt(0, 0.48, 0)

  scene.add(new THREE.HemisphereLight(0x8bdcff, 0x010712, 1.25))
  const keyLight = new THREE.PointLight(0x2e9eff, 22, 18, 2)
  keyLight.position.set(-2.8, 4.6, 4.2)
  scene.add(keyLight)
  const rimLight = new THREE.PointLight(0x0b5cff, 16, 16, 2)
  rimLight.position.set(3.4, 1.8, -2.8)
  scene.add(rimLight)
  const frontLight = new THREE.PointLight(0x167ad0, 12, 14, 2)
  frontLight.position.set(0, 1.1, 5.4)
  scene.add(frontLight)

  buildCore()
  rememberMaterialState()
  updateAlertState()
  observer = new ResizeObserver(resize)
  observer.observe(canvas)
  resize()
  start()
  document.addEventListener('visibilitychange', handleVisibility)
})

watch(() => props.alert, updateAlertState)

onBeforeUnmount(() => {
  stop()
  observer?.disconnect()
  scene?.traverse(disposeObject)
  renderer?.dispose()
  document.removeEventListener('visibilitychange', handleVisibility)
  animatedRings.length = 0
  energySegments.length = 0
  orbitRunners.length = 0
  rotatingOrbits.length = 0
  rotatingRings.length = 0
})
</script>

<style scoped>
.ai-core-scene{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
</style>
