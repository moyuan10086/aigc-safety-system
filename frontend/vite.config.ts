import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import UnoCSS from 'unocss/vite'
import { presetUno, presetAttributify } from 'unocss'

export default defineConfig({
  plugins: [
    UnoCSS({ presets: [presetUno(), presetAttributify()] }),
    vue(),
  ],
  server: { proxy: { '/api': 'http://localhost:8010' } },
})
