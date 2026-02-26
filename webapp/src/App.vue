<template>
  <v-app :style="appStyle">
    <v-main>
      <v-container fluid class="pa-0">
        <!-- Header -->
        <v-toolbar
          :color="themeColors.bgColor"
          flat
          density="compact"
        >
          <v-toolbar-title class="text-h6 font-weight-bold" :style="{ color: themeColors.textColor }">
            <v-icon class="mr-2">mdi-fridge-outline</v-icon>
            Pantry Scanner
          </v-toolbar-title>
        </v-toolbar>

        <!-- Mode Toggle -->
        <ModeSelector
          v-model="mode"
          :theme-colors="themeColors"
        />

        <!-- Tab Navigation -->
        <v-tabs
          v-model="activeTab"
          :bg-color="themeColors.bgColor"
          :color="themeColors.buttonColor"
          grow
          density="comfortable"
        >
          <v-tab value="scan">
            <v-icon start>mdi-camera</v-icon>
            Scan
          </v-tab>
          <v-tab value="queue">
            <v-icon start>mdi-cart-outline</v-icon>
            Queue
            <v-badge
              v-if="scanQueue.length"
              :content="scanQueue.length"
              color="primary"
              inline
              class="ml-1"
            />
          </v-tab>
        </v-tabs>

        <v-divider />

        <!-- Scan Tab -->
        <v-window v-model="activeTab">
          <v-window-item value="scan">
            <ScanView
              :theme-colors="themeColors"
              :is-telegram-client="isTelegramClient"
              :mode="mode"
              @detected="onDetected"
              @send-single="addToQueue"
            />
          </v-window-item>

          <!-- Queue Tab -->
          <v-window-item value="queue">
            <ScanQueue
              :scans="scanQueue"
              :mode="mode"
              :theme-colors="themeColors"
              @remove="onRemoveFromQueue"
              @clear="onClearQueue"
              @send-all="sendAllToBot"
            />
          </v-window-item>
        </v-window>

        <!-- Not compatible warning -->
        <v-dialog v-model="showWarning" max-width="400" persistent>
          <v-card>
            <v-card-title class="text-h6">
              <v-icon color="warning" class="mr-2">mdi-alert</v-icon>
              Compatibility Note
            </v-card-title>
            <v-card-text>
              This Mini App works best on Telegram mobile clients.
              QR scanning may not be available on web or desktop clients.
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn color="primary" @click="showWarning = false">Got it</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-container>
    </v-main>
  </v-app>
</template>

<script>
import ScanView from './components/ScanView.vue'
import ScanQueue from './components/ScanQueue.vue'
import ModeSelector from './components/ModeSelector.vue'

export default {
  components: { ScanView, ScanQueue, ModeSelector },

  data() {
    return {
      activeTab: 'scan',
      mode: 'add',  // 'add' or 'remove'
      showWarning: false,
      scanQueue: [],
      isTelegramClient: false,
    }
  },

  computed: {
    themeColors() {
      const tg = this.TMA
      return {
        bgColor: tg?.themeParams?.bg_color || '#ffffff',
        textColor: tg?.themeParams?.text_color || '#000000',
        hintColor: tg?.themeParams?.hint_color || '#999999',
        buttonColor: tg?.themeParams?.button_color || '#3390ec',
        buttonTextColor: tg?.themeParams?.button_text_color || '#ffffff',
        secondaryBgColor: tg?.themeParams?.secondary_bg_color || '#f0f0f0',
      }
    },

    appStyle() {
      return {
        backgroundColor: this.themeColors.bgColor,
        color: this.themeColors.textColor,
        minHeight: '100vh',
      }
    },
  },

  created() {
    const tg = this.TMA
    if (tg?.platform && tg.platform !== 'unknown') {
      this.isTelegramClient = true
    }

    if (!this.isTelegramClient) {
      this.showWarning = true
    }

    // Parse initial mode from URL params
    const params = new URLSearchParams(window.location.search)
    const urlMode = params.get('mode')
    if (urlMode === 'add' || urlMode === 'remove') {
      this.mode = urlMode
    }

    this.loadQueue()
  },

  mounted() {
    this.TMA?.ready()
    this.TMA?.expand()
  },

  methods: {
    onDetected(result) {
      // Continuous scanning: auto-add to queue
      this.addToQueue(result)
    },

    addToQueue(result) {
      // Deduplicate within queue — increment count instead
      const existing = this.scanQueue.find(s => s.code === result.code)
      if (existing) {
        existing.count = (existing.count || 1) + 1
        this.haptic('warning')
      } else {
        this.scanQueue.push({ ...result, count: 1 })
        this.haptic('success')
      }
      this.saveQueue()
    },

    onRemoveFromQueue(index) {
      this.scanQueue.splice(index, 1)
      this.saveQueue()
    },

    onClearQueue() {
      this.scanQueue = []
      this.saveQueue()
    },

    sendAllToBot() {
      if (!this.scanQueue.length) return

      const payload = JSON.stringify({
        mode: this.mode,
        scans: this.scanQueue.map(s => ({
          code: s.code,
          format: s.format,
          count: s.count || 1,
        })),
      })

      this.scanQueue = []
      this.saveQueue()
      this.TMA.sendData(payload)
      setTimeout(() => this.TMA.close(), 300)
    },

    loadQueue() {
      try {
        const stored = sessionStorage.getItem('pantry_queue')
        if (stored) this.scanQueue = JSON.parse(stored)
      } catch { /* ignore */ }
    },

    saveQueue() {
      try {
        sessionStorage.setItem('pantry_queue', JSON.stringify(this.scanQueue))
      } catch { /* ignore */ }
    },

    haptic(type) {
      try {
        this.TMA?.HapticFeedback?.notificationOccurred(type)
      } catch { /* not supported */ }
    },
  },
}
</script>

<style>
html, body {
  margin: 0;
  padding: 0;
  overflow-x: hidden;
  width: 100%;
  max-width: 100vw;
}

.v-application {
  max-width: 100vw;
  overflow-x: hidden;
}

.v-card-actions {
  flex-wrap: wrap;
  gap: 4px;
}

.v-btn {
  max-width: 100%;
}
</style>
