<template>
  <div class="account-panel" :class="{ compact: !expanded }">
    <template v-if="loading">
      <div class="account-loading" :title="expanded ? '' : '正在读取账户状态'">
        <LoaderCircle class="spin" :size="18" />
        <span v-if="expanded">正在读取账户</span>
      </div>
    </template>

    <template v-else-if="user">
      <div class="account-avatar"><UserRound :size="17" /></div>
      <div v-if="expanded" class="account-copy">
        <strong>{{ user.display_name }}</strong>
        <span>{{ roleLabel }}</span>
      </div>
      <button class="account-icon-button" type="button" title="退出登录" :disabled="signingOut" @click="signOut">
        <LoaderCircle v-if="signingOut" class="spin" :size="17" />
        <LogOut v-else :size="17" />
      </button>
    </template>

    <button v-else class="login-entry" type="button" :title="expanded ? '' : '审核员登录'" @click="dialogOpen = true">
      <LogIn :size="18" />
      <span v-if="expanded">审核员登录</span>
    </button>
  </div>

  <LoginDialog :open="dialogOpen" @close="dialogOpen = false" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { LoaderCircle, LogIn, LogOut, UserRound } from 'lucide-vue-next'
import { logout, useAuth } from '../../composables/useAuth'
import LoginDialog from './LoginDialog.vue'

defineProps<{ expanded: boolean }>()
const { user, loading } = useAuth()
const dialogOpen = ref(false)
const signingOut = ref(false)
const roleLabel = computed(() => user.value?.role === 'admin' ? '系统管理员' : '安全审核员')
const openLogin = () => { dialogOpen.value = true }

onMounted(() => window.addEventListener('aigc:open-login', openLogin))
onBeforeUnmount(() => window.removeEventListener('aigc:open-login', openLogin))

async function signOut() {
  if (signingOut.value) return
  signingOut.value = true
  try {
    await logout()
  } finally {
    signingOut.value = false
  }
}
</script>

<style scoped>
.account-panel { min-height:58px; display:flex; align-items:center; gap:9px; padding:9px 7px; border-top:1px solid var(--sidebar-line); }
.account-panel.compact { justify-content:center; padding-inline:0; }
.account-loading { width:100%; min-height:38px; display:flex; align-items:center; justify-content:center; gap:8px; color:#9db3c2; font-size:11px; }
.account-avatar { width:34px; height:34px; flex:0 0 34px; display:grid; place-items:center; color:#dff6fb; background:#1d465d; border:1px solid #356078; border-radius:6px; }
.account-copy { min-width:0; flex:1; display:flex; flex-direction:column; gap:3px; }
.account-copy strong { overflow:hidden; color:#f5f9fc; font-size:12px; line-height:1.2; text-overflow:ellipsis; white-space:nowrap; }
.account-copy span { color:#8fa9ba; font-size:10px; }
.account-icon-button { width:31px; height:31px; flex:0 0 31px; display:grid; place-items:center; color:#9db3c2; background:transparent; border:1px solid transparent; border-radius:6px; cursor:pointer; }
.account-icon-button:hover { color:#fff; background:var(--sidebar-2); border-color:var(--sidebar-line); }
.login-entry { width:100%; min-height:38px; display:flex; align-items:center; justify-content:center; gap:9px; color:#d8e6ee; background:#173a50; border:1px solid #31546b; border-radius:6px; cursor:pointer; font-size:12px; font-weight:650; }
.login-entry:hover { color:#fff; background:#1d465d; border-color:#49758d; }
.compact .login-entry { width:38px; flex:0 0 38px; padding:0; }
.compact .account-avatar { display:none; }
.spin { animation:spin .8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
</style>
