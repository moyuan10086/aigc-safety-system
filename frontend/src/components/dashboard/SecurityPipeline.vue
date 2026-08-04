<template>
  <div class="pipeline-stage">
    <div class="orbit orbit-a"></div><div class="orbit orbit-b"></div>
    <div class="pipeline-core">
      <ShieldCheck :size="34" />
      <strong>安全审核中枢</strong>
      <span>POLICY ORCHESTRATOR</span>
      <b>{{ configured }}/{{ total }} 引擎就绪</b>
    </div>
    <div v-for="item in capabilities" :key="item.code" class="capability" :class="item.position">
      <component :is="item.icon" :size="19" />
      <div><strong>{{ item.label }}</strong><span>{{ item.code }}</span></div>
      <i></i>
    </div>
    <div class="decision-flow">
      <span>输入采集</span><i></i><span>多模态判定</span><i></i><span>策略融合</span><i></i><span>放行 / 复核 / 阻断</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { BadgeCheck, ScanFace, ScanSearch, ShieldCheck, UserCheck } from 'lucide-vue-next'

defineProps<{ configured: number; total: number }>()
const capabilities = [
  { label: '真实性检测', code: 'DEEPFAKE / MLLM', icon: ScanFace, position: 'top-left' },
  { label: '内容安全审核', code: 'VISION / RAG', icon: ScanSearch, position: 'top-right' },
  { label: '来源与取证', code: 'C2PA / HASH', icon: BadgeCheck, position: 'bottom-left' },
  { label: '人工复核闭环', code: 'HUMAN REVIEW', icon: UserCheck, position: 'bottom-right' },
]
</script>

<style scoped>
.pipeline-stage{position:relative;height:100%;min-height:300px;overflow:hidden;background:radial-gradient(circle at 50% 45%,rgba(49,198,220,.10),transparent 34%)}.pipeline-stage::before,.pipeline-stage::after{content:'';position:absolute;left:50%;top:45%;background:rgba(49,198,220,.28);transform:translate(-50%,-50%)}.pipeline-stage::before{width:64%;height:1px}.pipeline-stage::after{width:1px;height:58%}.orbit{position:absolute;left:50%;top:45%;border:1px solid rgba(49,198,220,.18);border-radius:50%;transform:translate(-50%,-50%)}.orbit-a{width:42%;aspect-ratio:1}.orbit-b{width:64%;aspect-ratio:1;animation:pulse 3.4s ease-in-out infinite}.pipeline-core{position:absolute;left:50%;top:45%;width:142px;aspect-ratio:1;display:flex;align-items:center;justify-content:center;flex-direction:column;color:#7de8f5;background:#0b2b3f;border:1px solid #31c6dc;border-radius:50%;box-shadow:0 0 35px rgba(49,198,220,.23);transform:translate(-50%,-50%);z-index:2}.pipeline-core::before{content:'';position:absolute;inset:8px;border:1px dashed rgba(125,232,245,.32);border-radius:50%;animation:rotate 16s linear infinite}.pipeline-core strong{margin-top:7px;color:#e7f9ff;font-size:12px}.pipeline-core span{margin-top:3px;color:#4f7d94;font:7px ui-monospace,monospace}.pipeline-core b{margin-top:8px;padding:3px 7px;color:#4ddeaa;background:rgba(77,222,170,.08);font:7px ui-monospace,monospace}.capability{position:absolute;width:150px;height:56px;display:flex;align-items:center;gap:9px;padding:0 11px;color:#31c6dc;background:#0a2639;border:1px solid #24536d;z-index:2}.capability::after{content:'';position:absolute;width:32px;height:1px;background:#31c6dc}.capability div{min-width:0;display:flex;flex-direction:column}.capability strong{color:#d9edf7;font-size:9px}.capability span{margin-top:4px;color:#52778b;font:7px ui-monospace,monospace}.capability i{position:absolute;width:6px;height:6px;border-radius:50%;background:#4ddeaa;box-shadow:0 0 8px #4ddeaa}.top-left{left:8%;top:16%}.top-left::after{right:-33px}.top-left i{right:-38px}.top-right{right:8%;top:16%}.top-right::after{left:-33px}.top-right i{left:-38px}.bottom-left{left:8%;bottom:23%}.bottom-left::after{right:-33px}.bottom-left i{right:-38px}.bottom-right{right:8%;bottom:23%}.bottom-right::after{left:-33px}.bottom-right i{left:-38px}.decision-flow{position:absolute;left:7%;right:7%;bottom:5%;height:30px;display:flex;align-items:center;justify-content:center;gap:10px;color:#7298ac;font-size:8px}.decision-flow span{padding:5px 8px;background:#092335;border:1px solid #1c465e;white-space:nowrap}.decision-flow i{width:20px;height:1px;background:#31c6dc;position:relative}.decision-flow i::after{content:'';position:absolute;right:-1px;top:-2px;border-left:4px solid #31c6dc;border-top:2px solid transparent;border-bottom:2px solid transparent}@keyframes pulse{50%{opacity:.35;transform:translate(-50%,-50%) scale(1.04)}}@keyframes rotate{to{transform:rotate(360deg)}}
</style>
