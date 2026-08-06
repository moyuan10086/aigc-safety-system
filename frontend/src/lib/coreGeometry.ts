/* ============================================================
   AI 中枢几何：Canvas 能量层与 DOM 核心球共用的唯一来源。

   两层此前各自算尺寸（Canvas 用 min(w*.5,h*.62)，CSS 用 17vw），
   导致轨道节点落在球体背后、轨道被面板上下缘裁掉。
   任何一层改动都必须走这里。
   ============================================================ */

/** 圆心纵向位置（占面板高度比例） */
export const CY_RATIO = 0.46
/** 轨道纵向压扁系数：椭圆读作"倾斜的空间轨道" */
export const SQUASH = 0.9
/** 最外层轴对齐图元半径系数（呼吸波峰值 0.30+0.68≈0.98） */
export const OUTER_RING = 0.98
/** 轨道节点所在环的半径系数 */
export const NODE_RING = 0.6
/** 球体半径 / base：必须显著小于 NODE_RING，让节点在球外可见 */
export const ORB_RATIO = 0.42

/**
 * 轨道基准半径 base。
 *
 * 约束来自最外层轴对齐图元（轨道环、呼吸波），纵向被压扁 SQUASH：
 *   base * OUTER_RING * SQUASH ≤ min(cy, height - cy)
 *   base * OUTER_RING          ≤ width / 2
 * 数据流粒子沿 ±40° 斜向走，纵向投影仅 base*0.74，不构成约束。
 */
export function coreBase(width: number, height: number): number {
  const vertical = Math.min(height * CY_RATIO, height * (1 - CY_RATIO))
  return (Math.min(width / 2, vertical / SQUASH) / OUTER_RING) * 0.72
}

/** 核心球直径（px），供 DOM 层写入 --core */
export function orbDiameter(width: number, height: number): number {
  return coreBase(width, height) * ORB_RATIO * 2
}
