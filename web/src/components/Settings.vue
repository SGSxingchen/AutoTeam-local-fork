<template>
  <div class="mt-6 space-y-6">
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div class="flex items-center justify-between gap-4 mb-4">
        <div>
          <h2 class="text-lg font-semibold text-white">管理员登录</h2>
          <p class="text-sm text-gray-400 mt-1">
            首次启动先在这里完成主号登录，系统会统一写入单个 state.json 文件，保存邮箱、session、workspace ID、workspace 名称；如果你走了密码登录，也会保留密码供主号 Codex 复用。
          </p>
        </div>
        <span
          class="min-w-[72px] px-3 py-1.5 rounded-full text-xs text-center whitespace-nowrap border"
          :class="adminConfigured
            ? 'bg-green-500/10 text-green-400 border-green-500/20'
            : adminBusy
              ? 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20'
              : 'bg-gray-800 text-gray-400 border-gray-700'"
        >
          {{ adminConfigured ? '已配置' : adminBusy ? '登录中' : '未配置' }}
        </span>
      </div>

      <div v-if="message" class="mb-4 px-4 py-3 rounded-lg text-sm border" :class="messageClass">
        {{ message }}
      </div>

      <div v-if="adminConfigured && !adminBusy" class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <div class="px-3 py-3 bg-gray-800/60 border border-gray-800 rounded-lg">
          <div class="text-gray-500 mb-1">管理员邮箱</div>
          <div class="font-mono text-white break-all">{{ props.adminStatus?.email || '-' }}</div>
        </div>
        <div class="px-3 py-3 bg-gray-800/60 border border-gray-800 rounded-lg">
          <div class="text-gray-500 mb-1">Workspace ID</div>
          <div class="font-mono text-white break-all">{{ props.adminStatus?.account_id || '-' }}</div>
        </div>
        <div class="px-3 py-3 bg-gray-800/60 border border-gray-800 rounded-lg md:col-span-2">
          <div class="text-gray-500 mb-1">Workspace 名称</div>
          <div class="text-white">{{ props.adminStatus?.workspace_name || '未识别' }}</div>
        </div>
        <div class="px-3 py-3 bg-gray-800/60 border border-gray-800 rounded-lg md:col-span-2">
          <div class="text-gray-500 mb-1">Session Token</div>
          <div v-if="props.adminStatus?.session_present" class="text-green-400 text-xs">已配置</div>
          <div v-else class="space-y-2">
            <div class="text-amber-400 text-xs">未配置（Team 管理功能需要 session token）</div>
            <div class="text-gray-400 text-xs space-y-2">
              <div>获取方式：</div>
              <ol class="list-decimal list-inside space-y-1">
                <li>
                  在浏览器中打开
                  <a href="https://chatgpt.com" target="_blank" rel="noreferrer" class="text-blue-400 hover:underline">
                    chatgpt.com
                  </a>
                  并登录管理员账号
                </li>
                <li>按 F12 打开开发者工具 → Application → Cookies → chatgpt.com</li>
                <li>找到 <code class="bg-gray-800 px-1 rounded">__Secure-next-auth.session-token</code></li>
                <li>
                  如果有 <code class="bg-gray-800 px-1 rounded">.0</code> 和
                  <code class="bg-gray-800 px-1 rounded">.1</code> 两个，将值按顺序拼接在一起
                </li>
                <li>粘贴到下方输入框</li>
              </ol>
            </div>
            <div class="space-y-2">
              <input
                v-model.trim="sessionToken"
                type="password"
                placeholder="粘贴 session token"
                class="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-white font-mono focus:outline-none focus:border-blue-500"
              />
              <div class="flex justify-end">
                <button
                  @click="importSessionToken"
                  :disabled="submitting || !sessionEmail || !sessionToken"
                  class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition disabled:opacity-50"
                >
                  {{ submitting ? '校验中...' : '保存' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="px-3 py-3 bg-gray-800/60 border border-gray-800 rounded-lg md:col-span-2">
          <div class="text-gray-500 mb-1">管理员密码</div>
          <div class="text-white">{{ props.adminStatus?.password_saved ? '已保存，可用于主号 Codex 登录' : '未保存' }}</div>
        </div>
      </div>

      <div v-if="!adminBusy" class="mt-4">
        <div v-if="!adminConfigured" class="space-y-4">
          <div class="flex flex-col sm:flex-row gap-3">
            <input
              v-model.trim="email"
              type="email"
              autocomplete="username"
              placeholder="输入主号邮箱"
              class="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
            />
            <button
              @click="startLogin"
              :disabled="submitting || !email"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition disabled:opacity-50"
            >
              {{ submitting ? '提交中...' : '开始登录' }}
            </button>
          </div>

          <div class="border border-gray-800 rounded-xl p-4 bg-gray-800/30">
            <div class="text-sm font-medium text-white">或手动导入 session_token</div>
            <p class="text-xs text-gray-400 mt-1 mb-3">
              适合你已经在浏览器里拿到 <span class="font-mono">__Secure-next-auth.session-token</span> 的场景。系统会校验 token，并自动识别 workspace ID / 名称。
            </p>
            <div class="text-gray-400 text-xs space-y-2 mb-3">
              <div>获取方式：</div>
              <ol class="list-decimal list-inside space-y-1">
                <li>
                  在浏览器中打开
                  <a href="https://chatgpt.com" target="_blank" rel="noreferrer" class="text-blue-400 hover:underline">
                    chatgpt.com
                  </a>
                  并登录管理员账号
                </li>
                <li>按 F12 打开开发者工具 → Application → Cookies → chatgpt.com</li>
                <li>找到 <code class="bg-gray-800 px-1 rounded">__Secure-next-auth.session-token</code></li>
                <li>
                  如果有 <code class="bg-gray-800 px-1 rounded">.0</code> 和
                  <code class="bg-gray-800 px-1 rounded">.1</code> 两个，将值按顺序拼接在一起
                </li>
                <li>粘贴到下方输入框</li>
              </ol>
            </div>
            <div class="space-y-3">
              <input
                v-model.trim="sessionEmail"
                type="email"
                autocomplete="username"
                placeholder="输入主号邮箱"
                class="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
              />
              <textarea
                v-model.trim="sessionToken"
                rows="4"
                spellcheck="false"
                placeholder="粘贴完整 session_token"
                class="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white font-mono focus:outline-none focus:border-cyan-500"
              ></textarea>
              <div class="flex justify-end">
                <button
                  @click="importSessionToken"
                  :disabled="submitting || !sessionEmail || !sessionToken"
                  class="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm rounded-lg transition disabled:opacity-50"
                >
                  {{ submitting ? '校验中...' : '导入 session_token' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="!codexBusy" class="flex flex-wrap gap-3">
          <button
            @click="loginMainCodex"
            :disabled="submitting || syncingMain || deletingMainCpa"
            class="px-4 py-2 bg-blue-700 hover:bg-blue-600 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ syncingMain && mainCodexSubmittingAction === 'login' ? '登录中...' : '登录主号 Codex' }}
          </button>
          <button
            @click="syncMainCodex"
            :disabled="submitting || syncingMain || deletingMainCpa"
            class="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ syncingMain && mainCodexSubmittingAction === 'sync' ? '同步中...' : '同步主号 Codex 到 CPA' }}
          </button>
          <button
            @click="deleteMainCodexFromCpa"
            :disabled="submitting || syncingMain || deletingMainCpa"
            class="px-4 py-2 bg-amber-700 hover:bg-amber-600 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ deletingMainCpa ? '删除中...' : '从 CPA 删除主号文件' }}
          </button>
          <button
            @click="logoutAdmin"
            :disabled="submitting || syncingMain || deletingMainCpa"
            class="px-4 py-2 bg-rose-700/80 hover:bg-rose-700 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ submitting ? '处理中...' : '清除登录态' }}
          </button>
        </div>
      </div>

      <div v-if="adminBusy" class="space-y-4">
        <div class="text-sm text-gray-300">
          当前邮箱: <span class="font-mono">{{ loginEmail || props.adminStatus?.email || '-' }}</span>
        </div>

        <div v-if="props.adminStatus?.login_step === 'password_required'" class="flex flex-col sm:flex-row gap-3">
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="输入主号密码"
            :disabled="submitting"
            class="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          />
          <button
            @click="submitPassword"
            :disabled="submitting || !password"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ submitting ? '提交中...' : '提交密码' }}
          </button>
        </div>

        <div v-else-if="props.adminStatus?.login_step === 'code_required'" class="flex flex-col sm:flex-row gap-3">
          <input
            v-model.trim="code"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="输入邮箱验证码"
            :disabled="submitting"
            class="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          />
          <button
            @click="submitCode"
            :disabled="submitting || !code"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition disabled:opacity-50 disabled:bg-gray-700 disabled:hover:bg-gray-700"
          >
            {{ submitting ? '提交中...' : '提交验证码' }}
          </button>
        </div>

        <div v-else-if="props.adminStatus?.login_step === 'workspace_required'" class="space-y-3">
          <div class="text-sm text-gray-300">
            请选择要进入的组织 / workspace
          </div>
          <select
            v-model="workspaceOptionId"
            :disabled="submitting"
            class="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option disabled value="">请选择组织</option>
            <option
              v-for="opt in props.adminStatus?.workspace_options || []"
              :key="opt.id"
              :value="opt.id"
            >
              {{ opt.label }}{{ opt.kind === 'fallback' ? ' (可能是个人/免费)' : '' }}
            </option>
          </select>
          <button
            @click="submitWorkspace"
            :disabled="submitting || !workspaceOptionId"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition disabled:opacity-50 disabled:bg-gray-700 disabled:hover:bg-gray-700"
          >
            {{ submitting ? '提交中...' : '确认组织选择' }}
          </button>
        </div>

        <div v-if="submitting && adminSubmittingHint" class="text-xs text-blue-300">
          {{ adminSubmittingHint }}
        </div>

        <div class="flex justify-end">
          <button
            @click="cancelLogin"
            :disabled="submitting"
            class="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm text-gray-200 rounded-lg border border-gray-700 transition disabled:opacity-50"
          >
            取消登录
          </button>
        </div>
      </div>

      <div v-if="codexBusy" class="mt-4 space-y-4 border-t border-gray-800 pt-4">
        <div class="text-sm text-gray-300">
          主号 Codex{{ codexActionLabel }}继续中
        </div>

        <div v-if="props.codexStatus?.step === 'password_required'" class="flex flex-col sm:flex-row gap-3">
          <input
            v-model="codexPassword"
            type="password"
            autocomplete="current-password"
            placeholder="输入主号密码"
            :disabled="syncingMain"
            class="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          />
          <button
            @click="submitMainCodexPassword"
            :disabled="syncingMain || !codexPassword"
            class="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ syncingMain ? '提交中...' : '提交密码' }}
          </button>
        </div>

        <div v-else-if="props.codexStatus?.step === 'code_required'" class="flex flex-col sm:flex-row gap-3">
          <input
            v-model.trim="codexCode"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="输入主号 Codex 验证码"
            :disabled="syncingMain"
            class="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
          />
          <button
            @click="submitMainCodexCode"
            :disabled="syncingMain || !codexCode"
            class="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ syncingMain ? '提交中...' : '提交验证码' }}
          </button>
        </div>

        <div
          v-else-if="props.codexStatus?.step === 'phone_required'"
          class="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100"
        >
          主号 Codex 当前需要手机验证。请配置 5sim 后重新发起，或取消当前登录流程。
        </div>

        <div v-if="syncingMain && codexSubmittingHint" class="text-xs text-cyan-300">
          {{ codexSubmittingHint }}
        </div>

        <div class="flex justify-end">
          <button
            @click="cancelMainCodexSync"
            :disabled="syncingMain"
            class="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm text-gray-200 rounded-lg border border-gray-700 transition disabled:opacity-50"
          >
            取消主号 Codex 登录
          </button>
        </div>
      </div>
    </div>

    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div class="flex flex-col gap-2 mb-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 class="text-lg font-semibold text-white">环境变量配置</h2>
          <p class="text-sm text-gray-400 mt-1">
            统一保存到 .env。巡检字段会立即同步到后台线程；其他标记字段保存后可通过这里重启服务，让新配置完整生效。
          </p>
        </div>
        <span v-if="envSaved" class="text-xs text-green-400 transition">已保存</span>
      </div>

      <div v-if="envMessage" class="mb-4 px-4 py-3 rounded-lg text-sm border" :class="envMessageClass">
        {{ envMessage }}
      </div>

      <div
        v-if="restartRequired"
        class="mb-4 flex flex-col gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100 md:flex-row md:items-center md:justify-between"
      >
        <span>有配置需要重启服务后完整生效。</span>
        <button
          @click="restartApplication"
          :disabled="restartSubmitting"
          class="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-sm rounded-lg transition disabled:opacity-50"
        >
          {{ restartSubmitting ? '重启中...' : '重启服务' }}
        </button>
      </div>

      <div v-if="envGroups.length === 0" class="text-sm text-gray-500">正在加载配置...</div>

      <div v-else class="space-y-4">
        <div
          v-for="group in envGroups"
          :key="group.name"
          class="border-t border-gray-800 pt-4 first:border-t-0 first:pt-0"
        >
          <div class="mb-3 flex items-center justify-between gap-3">
            <h3 class="text-sm font-medium text-gray-200">{{ group.name }}</h3>
            <span class="text-[11px] text-gray-500">{{ group.fields.length }} 项</span>
          </div>
          <div class="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <div v-for="field in group.fields" :key="field.key" class="min-w-0">
              <div class="mb-1 flex items-center justify-between gap-2">
                <label :for="`env-${field.key}`" class="block truncate text-sm text-gray-400">
                  {{ field.label }}
                </label>
                <div class="flex shrink-0 items-center gap-1">
                  <span
                    v-if="field.restart_required"
                    class="rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-200"
                  >
                    需重启
                  </span>
                  <span class="rounded border px-1.5 py-0.5 text-[10px]" :class="sourceBadgeClass(field.source)">
                    {{ sourceLabel(field.source) }}
                  </span>
                </div>
              </div>

              <div
                v-if="field.type === 'bool'"
                class="flex h-10 items-center gap-3 rounded-lg border border-gray-700 bg-gray-800 px-3"
              >
                <input
                  :id="`env-${field.key}`"
                  type="checkbox"
                  :checked="envForm[field.key] === '1'"
                  class="h-4 w-4 rounded border-gray-700 bg-gray-900 text-blue-600 focus:ring-blue-500"
                  @change="setBoolEnvField(field.key, $event.target.checked)"
                />
                <span class="text-sm text-gray-300">{{ envForm[field.key] === '1' ? '开启' : '关闭' }}</span>
              </div>

              <div v-else class="flex gap-2">
                <input
                  :id="`env-${field.key}`"
                  v-model.trim="envForm[field.key]"
                  :type="fieldInputType(field)"
                  :inputmode="field.type === 'number' ? 'numeric' : undefined"
                  :placeholder="envPlaceholder(field)"
                  :disabled="envSensitiveClears[field.key]"
                  spellcheck="false"
                  class="min-w-0 flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-60"
                />
                <button
                  v-if="field.sensitive && field.has_value"
                  type="button"
                  @click="toggleSensitiveClear(field.key)"
                  class="shrink-0 px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs rounded-lg border border-gray-700 transition"
                >
                  {{ envSensitiveClears[field.key] ? '取消' : '清空' }}
                </button>
              </div>

              <p v-if="envFieldHint(field)" class="mt-1 text-xs text-gray-500 break-words">
                {{ envFieldHint(field) }}
              </p>
              <p class="mt-1 truncate font-mono text-[11px] text-gray-600">
                {{ field.key }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p class="text-xs text-gray-500 break-all">
          {{ envPath || '.env' }}
        </p>
        <div class="flex justify-end gap-3">
          <button
            @click="loadEnvConfig"
            :disabled="envSaving || restartSubmitting"
            class="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm rounded-lg border border-gray-700 transition disabled:opacity-50"
          >
            刷新
          </button>
          <button
            @click="saveEnvConfig"
            :disabled="envSaving || restartSubmitting"
            class="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition disabled:opacity-50"
          >
            {{ envSaving ? '保存中...' : '保存 .env' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { api, setApiKey, clearApiKey } from '../api.js'

const props = defineProps({
  adminStatus: {
    type: Object,
    default: null,
  },
  codexStatus: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['refresh', 'admin-progress'])

const envFields = ref([])
const envForm = ref({})
const envLoadedForm = ref({})
const envPath = ref('')
const envSaving = ref(false)
const envSaved = ref(false)
const envMessage = ref('')
const envMessageClass = ref('')
const envSensitiveClears = ref({})
const restartRequired = ref(false)
const restartSubmitting = ref(false)

const email = ref('')
const sessionEmail = ref('')
const sessionToken = ref('')
const password = ref('')
const code = ref('')
const workspaceOptionId = ref('')
const loginEmail = ref('')
const codexPassword = ref('')
const codexCode = ref('')
const submitting = ref(false)
const syncingMain = ref(false)
const mainCodexSubmittingAction = ref('')
const deletingMainCpa = ref(false)
const message = ref('')
const messageClass = ref('')
const adminSubmittingHint = ref('')
const codexSubmittingHint = ref('')

const adminConfigured = computed(() => !!props.adminStatus?.configured)
const adminBusy = computed(() => !!props.adminStatus?.login_in_progress)
const codexBusy = computed(() => !!props.codexStatus?.in_progress)
const codexActionLabel = computed(() => props.codexStatus?.action === 'sync' ? '同步' : '登录')
const envGroups = computed(() => {
  const groups = []
  const index = new Map()
  for (const field of envFields.value) {
    const name = field.group || '其他'
    if (!index.has(name)) {
      index.set(name, { name, fields: [] })
      groups.push(index.get(name))
    }
    index.get(name).fields.push(field)
  }
  return groups
})

watch(
  () => props.adminStatus,
  (next) => {
    if (next?.configured && next.email) {
      email.value = next.email
      sessionEmail.value = next.email
    }
    if (!next?.login_in_progress) {
      password.value = ''
      code.value = ''
      workspaceOptionId.value = ''
      adminSubmittingHint.value = ''
      loginEmail.value = next?.email || loginEmail.value
    }
    if (next?.login_step === 'workspace_required' && !workspaceOptionId.value) {
      const preferred = next?.workspace_options?.find(opt => opt.kind === 'preferred')
      workspaceOptionId.value = preferred?.id || next?.workspace_options?.[0]?.id || ''
    }
  },
  { immediate: true },
)

watch(
  () => props.codexStatus,
  (next) => {
    if (!next?.in_progress) {
      codexPassword.value = ''
      codexCode.value = ''
      codexSubmittingHint.value = ''
    }
  },
  { immediate: true },
)

onMounted(() => {
  loadEnvConfig()
})

function setMessage(text, type = 'success') {
  message.value = text
  messageClass.value = type === 'success'
    ? 'bg-green-500/10 text-green-400 border-green-500/20'
    : 'bg-red-500/10 text-red-400 border-red-500/20'
  window.clearTimeout(setMessage._timer)
  setMessage._timer = window.setTimeout(() => {
    message.value = ''
  }, 8000)
}

function setEnvMessage(text, type = 'success') {
  envMessage.value = text
  envMessageClass.value = type === 'success'
    ? 'bg-green-500/10 text-green-400 border-green-500/20'
    : 'bg-red-500/10 text-red-400 border-red-500/20'
  window.clearTimeout(setEnvMessage._timer)
  setEnvMessage._timer = window.setTimeout(() => {
    envMessage.value = ''
  }, 8000)
}

function applyEnvConfig(data) {
  const next = {}
  envFields.value = data?.fields || []
  for (const field of envFields.value) {
    next[field.key] = field.value ?? ''
  }
  envForm.value = next
  envLoadedForm.value = { ...next }
  envPath.value = data?.path || ''
  envSensitiveClears.value = {}
}

async function loadEnvConfig(options = {}) {
  try {
    const data = await api.getEnvConfig()
    applyEnvConfig(data)
    if (options.clearRestart) {
      restartRequired.value = false
    }
    const migrated = data?.migration?.migrated_keys || []
    if (migrated.length > 0) {
      setEnvMessage(`已从旧配置迁移到 .env: ${migrated.join(', ')}`)
    }
  } catch (e) {
    setEnvMessage(`加载环境变量失败: ${e.message}`, 'error')
  }
}

function fieldInputType(field) {
  if (field.type === 'number') return 'number'
  if (field.sensitive) return 'password'
  return 'text'
}

function envPlaceholder(field) {
  if (envSensitiveClears.value[field.key]) return '保存后清空'
  if (field.sensitive && field.has_value) return '已设置，输入新值覆盖'
  if (field.default) return field.default
  return ''
}

function envFieldHint(field) {
  if (envSensitiveClears.value[field.key]) return '保存后将清空该值。'
  if (field.sensitive && field.has_value) return '已设置；留空表示不修改。'
  if (field.masked) return '当前值已遮蔽；修改时请输入完整新值。'
  return field.description || ''
}

function sourceLabel(source) {
  if (source === 'env') return '.env'
  if (source === 'process') return '进程'
  if (source === 'default') return '默认'
  return source || '-'
}

function sourceBadgeClass(source) {
  if (source === 'env') return 'border-blue-500/20 bg-blue-500/10 text-blue-300'
  if (source === 'process') return 'border-cyan-500/20 bg-cyan-500/10 text-cyan-300'
  return 'border-gray-700 bg-gray-800 text-gray-400'
}

function setBoolEnvField(key, checked) {
  envForm.value = { ...envForm.value, [key]: checked ? '1' : '0' }
}

function toggleSensitiveClear(key) {
  const next = { ...envSensitiveClears.value }
  if (next[key]) {
    delete next[key]
  } else {
    next[key] = true
    envForm.value = { ...envForm.value, [key]: '' }
  }
  envSensitiveClears.value = next
}

async function saveEnvConfig() {
  const payload = {}
  for (const field of envFields.value) {
    const key = field.key
    if (envSensitiveClears.value[key]) {
      payload[key] = ''
      continue
    }
    const current = envForm.value[key] ?? ''
    const loaded = envLoadedForm.value[key] ?? ''
    if (field.sensitive) {
      if (current !== '') payload[key] = current
    } else if (current !== loaded) {
      payload[key] = current
    }
  }

  if (Object.keys(payload).length === 0) {
    setEnvMessage('没有需要保存的改动')
    return
  }

  envSaving.value = true
  envSaved.value = false
  try {
    const result = await api.setEnvConfig(payload)
    if (Object.prototype.hasOwnProperty.call(payload, 'API_KEY')) {
      if (payload.API_KEY) {
        setApiKey(payload.API_KEY)
      } else {
        clearApiKey()
      }
    }
    applyEnvConfig(result.config)
    restartRequired.value = restartRequired.value || !!result.restart_required
    envSaved.value = true
    setEnvMessage(result.restart_required ? '配置已保存，部分字段需重启后完整生效' : '配置已保存')
    setTimeout(() => { envSaved.value = false }, 3000)
    emit('refresh')
  } catch (e) {
    setEnvMessage(`保存环境变量失败: ${e.message}`, 'error')
  } finally {
    envSaving.value = false
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function waitForRestartRecovery() {
  const deadline = Date.now() + 60000
  await sleep(1500)
  while (Date.now() < deadline) {
    try {
      await api.getSetupStatus()
      await loadEnvConfig({ clearRestart: true })
      emit('refresh')
      return
    } catch {
      await sleep(2000)
    }
  }
  throw new Error('重启已提交，但 60 秒内未确认服务恢复')
}

async function restartApplication() {
  restartSubmitting.value = true
  try {
    await api.restartSystem()
    setEnvMessage('重启已提交，正在等待服务恢复...')
    await waitForRestartRecovery()
    setEnvMessage('服务已恢复，配置已重新加载')
  } catch (e) {
    setEnvMessage(`重启失败: ${e.message}`, 'error')
  } finally {
    restartSubmitting.value = false
  }
}

async function startLogin() {
  submitting.value = true
  adminSubmittingHint.value = '正在打开管理员登录页...'
  try {
    loginEmail.value = email.value
    const result = await api.startAdminLogin(email.value)
    setMessage(result.status === 'completed' ? '管理员登录完成' : '已进入下一步登录流程')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    submitting.value = false
    adminSubmittingHint.value = ''
  }
}

async function importSessionToken() {
  submitting.value = true
  adminSubmittingHint.value = '正在校验 session_token 并识别 workspace...'
  try {
    loginEmail.value = sessionEmail.value
    const result = await api.submitAdminSession(sessionEmail.value, sessionToken.value)
    sessionToken.value = ''
    setMessage(result.status === 'completed' ? 'session_token 导入成功' : 'session_token 已提交')
    emit('refresh')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    submitting.value = false
    adminSubmittingHint.value = ''
  }
}

async function submitPassword() {
  submitting.value = true
  adminSubmittingHint.value = '密码已提交，正在等待登录页响应...'
  try {
    const result = await api.submitAdminPassword(password.value)
    setMessage(result.status === 'completed' ? '管理员登录完成' : '密码已提交，请继续下一步')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    submitting.value = false
    adminSubmittingHint.value = ''
  }
}

async function submitCode() {
  submitting.value = true
  adminSubmittingHint.value = '验证码已提交，正在等待登录页响应，通常需要 5 到 10 秒...'
  try {
    const result = await api.submitAdminCode(code.value)
    setMessage(result.status === 'completed' ? '管理员登录完成' : '验证码已提交，请继续下一步')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    submitting.value = false
    adminSubmittingHint.value = ''
  }
}

async function submitWorkspace() {
  submitting.value = true
  adminSubmittingHint.value = '组织选择已提交，正在等待登录页响应...'
  try {
    const result = await api.submitAdminWorkspace(workspaceOptionId.value)
    setMessage(result.status === 'completed' ? '管理员登录完成' : '组织选择已提交，请继续下一步')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    submitting.value = false
    adminSubmittingHint.value = ''
  }
}

async function cancelLogin() {
  submitting.value = true
  try {
    await api.cancelAdminLogin()
    password.value = ''
    code.value = ''
    setMessage('管理员登录已取消')
    emit('refresh')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    submitting.value = false
  }
}

async function logoutAdmin() {
  submitting.value = true
  try {
    await api.logoutAdmin()
    password.value = ''
    code.value = ''
    setMessage('管理员登录态已清除')
    emit('refresh')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    submitting.value = false
  }
}

async function loginMainCodex() {
  syncingMain.value = true
  mainCodexSubmittingAction.value = 'login'
  codexSubmittingHint.value = '正在打开主号 Codex 登录页...'
  try {
    const result = await api.startMainCodexLogin()
    setMessage(result.status === 'completed' ? (result.message || '主号 Codex 已登录') : '主号 Codex 登录进入下一步')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    syncingMain.value = false
    mainCodexSubmittingAction.value = ''
    codexSubmittingHint.value = ''
  }
}

async function syncMainCodex() {
  syncingMain.value = true
  mainCodexSubmittingAction.value = 'sync'
  codexSubmittingHint.value = '正在打开主号 Codex 登录页...'
  try {
    const result = await api.startMainCodexSync()
    setMessage(result.status === 'completed' ? (result.message || '主号 Codex 已同步') : '主号 Codex 登录进入下一步')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    syncingMain.value = false
    mainCodexSubmittingAction.value = ''
    codexSubmittingHint.value = ''
  }
}

async function submitMainCodexPassword() {
  syncingMain.value = true
  mainCodexSubmittingAction.value = props.codexStatus?.action || 'login'
  codexSubmittingHint.value = '密码已提交，正在等待主号 Codex 登录页响应...'
  try {
    const result = await api.submitMainCodexPassword(codexPassword.value)
    setMessage(result.status === 'completed' ? (result.message || '主号 Codex 已同步') : '主号 Codex 密码已提交')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    syncingMain.value = false
    mainCodexSubmittingAction.value = ''
    codexSubmittingHint.value = ''
  }
}

async function submitMainCodexCode() {
  syncingMain.value = true
  mainCodexSubmittingAction.value = props.codexStatus?.action || 'login'
  codexSubmittingHint.value = '验证码已提交，正在等待主号 Codex 登录页响应，通常需要 5 到 10 秒...'
  try {
    const result = await api.submitMainCodexCode(codexCode.value)
    setMessage(result.status === 'completed' ? (result.message || '主号 Codex 已同步') : '主号 Codex 验证码已提交')
    emit('admin-progress')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    syncingMain.value = false
    mainCodexSubmittingAction.value = ''
    codexSubmittingHint.value = ''
  }
}

async function cancelMainCodexSync() {
  syncingMain.value = true
  try {
    await api.cancelMainCodexSync()
    setMessage('主号 Codex 登录已取消')
    emit('refresh')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    syncingMain.value = false
  }
}

async function deleteMainCodexFromCpa() {
  deletingMainCpa.value = true
  try {
    const result = await api.deleteMainCodexFromCpa()
    setMessage(result.message || '已从 CPA 删除主号文件')
    emit('refresh')
  } catch (e) {
    setMessage(e.message, 'error')
  } finally {
    deletingMainCpa.value = false
  }
}
</script>
