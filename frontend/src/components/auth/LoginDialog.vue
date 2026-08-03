<template>
  <Teleport to="body">
    <div v-if="open" class="login-mask" @click.self="close" @keydown.esc="close">
      <section class="login-dialog" role="dialog" aria-modal="true" aria-labelledby="login-title">
        <header class="login-header">
          <div class="login-emblem"><ShieldCheck :size="21" /></div>
          <div>
            <p>OPERATOR ACCESS</p>
            <h2 id="login-title">审核员登录</h2>
          </div>
          <button class="dialog-icon-button" type="button" title="关闭" @click="close">
            <X :size="18" />
          </button>
        </header>

        <form class="login-form" @submit.prevent="submit">
          <label for="auth-username">用户名</label>
          <div class="login-input-wrap">
            <UserRound :size="17" />
            <input
              id="auth-username"
              ref="usernameInput"
              v-model.trim="username"
              name="username"
              autocomplete="username"
              maxlength="128"
              required
            />
          </div>

          <label for="auth-password">密码</label>
          <div class="login-input-wrap">
            <LockKeyhole :size="17" />
            <input
              id="auth-password"
              v-model="password"
              name="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              maxlength="256"
              required
            />
            <button class="password-toggle" type="button" :title="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <EyeOff v-if="showPassword" :size="17" />
              <Eye v-else :size="17" />
            </button>
          </div>

          <p v-if="error" class="login-error" role="alert"><CircleAlert :size="15" />{{ error }}</p>

          <button class="login-submit" type="submit" :disabled="submitting || !username || !password">
            <LoaderCircle v-if="submitting" class="spin" :size="17" />
            <LogIn v-else :size="17" />
            {{ submitting ? '正在验证' : '登录工作台' }}
          </button>
        </form>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import {
  CircleAlert,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  LogIn,
  ShieldCheck,
  UserRound,
  X,
} from 'lucide-vue-next'
import { login } from '../../composables/useAuth'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; authenticated: [] }>()
const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)
const showPassword = ref(false)
const usernameInput = ref<HTMLInputElement | null>(null)

watch(() => props.open, async (isOpen) => {
  if (!isOpen) return
  error.value = ''
  password.value = ''
  await nextTick()
  usernameInput.value?.focus()
})

function close() {
  if (!submitting.value) emit('close')
}

async function submit() {
  if (submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await login(username.value, password.value)
    password.value = ''
    emit('authenticated')
    emit('close')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '登录失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-mask { position:fixed; inset:0; z-index:300; display:grid; place-items:center; padding:20px; background:rgba(10,29,44,.55); backdrop-filter:blur(6px); }
.login-dialog { width:min(420px,100%); overflow:hidden; background:var(--surface); border:1px solid var(--line-bright); border-radius:8px; box-shadow:0 28px 90px rgba(10,29,44,.32); }
.login-header { display:flex; align-items:center; gap:12px; padding:20px 22px; color:var(--text); background:linear-gradient(90deg,#edf6f9 0,#ffffff 72%); border-bottom:1px solid var(--line); }
.login-emblem { width:40px; height:40px; flex:0 0 40px; display:grid; place-items:center; color:#fff; background:var(--primary); border-radius:6px; }
.login-header p { margin:0 0 3px; color:var(--primary); font:700 9px/1 ui-monospace,monospace; letter-spacing:.12em; }
.login-header h2 { margin:0; font-size:16px; line-height:1.2; letter-spacing:0; }
.dialog-icon-button { width:34px; height:34px; margin-left:auto; display:grid; place-items:center; color:var(--muted); background:transparent; border:1px solid transparent; border-radius:6px; cursor:pointer; }
.dialog-icon-button:hover { color:var(--primary); background:var(--surface-3); border-color:var(--line); }
.login-form { display:flex; flex-direction:column; padding:22px; }
.login-form label { margin:0 0 7px; color:var(--muted); font-size:12px; font-weight:650; }
.login-form label:not(:first-child) { margin-top:16px; }
.login-input-wrap { height:42px; display:flex; align-items:center; gap:9px; padding:0 12px; color:var(--faint); background:var(--surface-2); border:1px solid var(--line); border-radius:6px; transition:border-color .16s,box-shadow .16s; }
.login-input-wrap:focus-within { color:var(--primary); border-color:var(--primary); box-shadow:0 0 0 3px rgba(8,126,174,.1); }
.login-input-wrap input { min-width:0; flex:1; height:100%; color:var(--text); background:transparent; border:0; outline:0; font-size:13px; }
.password-toggle { width:30px; height:30px; display:grid; place-items:center; color:var(--faint); background:transparent; border:0; border-radius:5px; cursor:pointer; }
.password-toggle:hover { color:var(--primary); background:var(--surface-3); }
.login-error { display:flex; align-items:center; gap:7px; margin:14px 0 0; padding:9px 10px; color:var(--danger); background:rgba(207,63,79,.07); border:1px solid rgba(207,63,79,.18); border-radius:6px; font-size:12px; }
.login-submit { height:42px; margin-top:20px; display:flex; align-items:center; justify-content:center; gap:8px; color:#fff; background:var(--primary); border:1px solid var(--primary); border-radius:6px; font-weight:650; font-size:13px; cursor:pointer; box-shadow:0 8px 20px rgba(8,126,174,.18); }
.login-submit:hover:not(:disabled) { background:var(--primary-strong); border-color:var(--primary-strong); }
.login-submit:disabled { opacity:.58; cursor:not-allowed; box-shadow:none; }
.spin { animation:spin .8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
</style>
