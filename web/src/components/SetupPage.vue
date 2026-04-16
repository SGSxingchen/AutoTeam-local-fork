<template>
  <div class="mx-auto flex min-h-[calc(100vh-2rem)] max-w-6xl items-center justify-center">
    <div class="grid w-full gap-6 xl:grid-cols-[0.88fr_1.12fr]">
      <section class="app-card hidden overflow-hidden p-8 xl:block">
        <div class="flex h-full flex-col justify-between gap-10">
          <div class="space-y-5">
            <span class="app-chip border-cyan-400/20 bg-cyan-500/10 text-cyan-100">
              First-time setup
            </span>
            <div>
              <h1 class="text-4xl font-bold leading-tight text-white">
                先把基础配置填对，后面整个面板才会顺。
              </h1>
              <p class="mt-4 max-w-xl text-base leading-7 text-slate-300">
                初始化阶段会写入后端必需的环境配置，包括 API Key、管理员账号和运行所需的基础参数。填完就能直接进入控制台。
              </p>
            </div>
          </div>

          <div class="grid gap-4">
            <article class="app-card-soft p-4">
              <div class="metric-label">自动生成</div>
              <div class="mt-3 text-lg font-semibold text-white">API Key 可留空</div>
              <p class="mt-2 text-sm leading-6 text-slate-400">
                如果没有现成的 API Key，系统会自动帮你生成一个，减少首次配置阻力。
              </p>
            </article>
            <article class="app-card-soft p-4">
              <div class="metric-label">一次填完</div>
              <div class="mt-3 text-lg font-semibold text-white">避免后面反复返工</div>
              <p class="mt-2 text-sm leading-6 text-slate-400">
                这里填的内容会直接影响管理员登录、同步和账号池任务流程，建议初始化时一次性填完整。
              </p>
            </article>
          </div>
        </div>
      </section>

      <section class="app-card p-6 sm:p-8">
        <div class="space-y-3">
          <span class="app-chip">初始化配置</span>
          <div>
            <h2 class="text-3xl font-bold tracking-tight text-white">
              AutoTeam 初始配置
            </h2>
            <p class="mt-2 text-sm leading-6 text-slate-400">
              首次启动时请先完成这些配置项。保存成功后会自动进入主面板。
            </p>
          </div>
        </div>

        <div
          v-if="message"
          class="mt-5 rounded-2xl border px-4 py-3 text-sm"
          :class="messageClass"
        >
          {{ message }}
        </div>

        <div class="mt-6 grid gap-4 md:grid-cols-2">
          <div v-for="field in fields" :key="field.key" class="space-y-2">
            <label class="block text-sm font-medium text-slate-300">
              {{ field.prompt }}
              <span v-if="!field.optional" class="text-rose-300">*</span>
              <span
                v-if="field.key === 'API_KEY'"
                class="ml-2 text-xs font-normal text-slate-500"
              >
                留空自动生成
              </span>
            </label>
            <input
              v-model="form[field.key]"
              :type="field.key.includes('PASSWORD') || field.key.includes('KEY') ? 'password' : 'text'"
              :placeholder="field.default || ''"
              class="app-input"
            />
          </div>
        </div>

        <button @click="save" :disabled="saving" class="app-button-primary mt-6 w-full">
          {{ saving ? '验证并保存中...' : '保存并进入控制台' }}
        </button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { api, setApiKey } from '../api.js'

const emit = defineEmits(['configured'])

const fields = ref([])
const form = reactive({})
const saving = ref(false)
const message = ref('')
const messageClass = ref('')

onMounted(async () => {
  try {
    const result = await api.getSetupStatus()
    fields.value = result.fields
    for (const field of result.fields) {
      form[field.key] = field.default || ''
    }
  } catch (e) {
    message.value = `获取配置状态失败: ${e.message}`
    messageClass.value = 'border-rose-400/20 bg-rose-500/10 text-rose-100'
  }
})

async function save() {
  saving.value = true
  message.value = ''
  try {
    const result = await api.saveSetup({ ...form })
    if (result.api_key) {
      setApiKey(result.api_key)
    }
    message.value = result.message
    messageClass.value = 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100'
    window.setTimeout(() => emit('configured'), 1000)
  } catch (e) {
    message.value = e.message
    messageClass.value = 'border-rose-400/20 bg-rose-500/10 text-rose-100'
  } finally {
    saving.value = false
  }
}
</script>
