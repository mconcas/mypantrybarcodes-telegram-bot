<template>
  <div class="barcode-scanner">
    <!-- Camera viewfinder -->
    <v-card
      class="scanner-card"
      variant="flat"
      rounded="xl"
    >
      <div class="camera-container" :class="{ active: isScanning }">
        <div id="barcode-reader" ref="reader"></div>

        <!-- Scanning overlay with animated line -->
        <div v-if="isScanning" class="scan-overlay">
          <div class="scan-region">
            <div class="scan-line"></div>
            <div class="corner tl"></div>
            <div class="corner tr"></div>
            <div class="corner bl"></div>
            <div class="corner br"></div>
          </div>
        </div>

        <!-- Loading state -->
        <div v-if="isLoading" class="loading-overlay">
          <v-progress-circular indeterminate color="white" size="48" />
          <div class="text-white mt-3">Starting camera…</div>
        </div>
      </div>

      <!-- Controls bar -->
      <v-card-actions class="pa-3 justify-center">
        <v-btn
          v-if="!isScanning"
          color="primary"
          rounded="pill"
          prepend-icon="mdi-camera"
          :loading="isLoading"
          @click="startScanning"
        >
          Start Scanner
        </v-btn>
        <v-btn
          v-else
          color="error"
          variant="tonal"
          rounded="pill"
          prepend-icon="mdi-stop"
          @click="stopScanning"
        >
          Stop
        </v-btn>
      </v-card-actions>

      <!-- Last scanned feedback -->
      <v-slide-y-transition>
        <div v-if="lastScanned" class="last-scanned mx-3 mb-3">
          <v-chip
            :color="mode === 'add' ? 'success' : 'error'"
            variant="tonal"
            prepend-icon="mdi-barcode"
            closable
            @click:close="lastScanned = null"
          >
            {{ mode === 'add' ? '+ Added' : '- Queued' }}: {{ lastScanned.code }}
          </v-chip>
        </div>
      </v-slide-y-transition>

      <!-- Hint -->
      <div class="text-center text-caption text-medium-emphasis pb-3 px-4">
        <template v-if="continuous">
          📷 Continuous mode — keep scanning! Items are added to the queue automatically.
        </template>
        <template v-else>
          Point the camera at a barcode. Supports EAN-13, Code 128, QR Code and more.
        </template>
      </div>
    </v-card>
  </div>
</template>

<script>
import { Html5Qrcode } from 'html5-qrcode'

export default {
  name: 'BarcodeScanner',

  props: {
    continuous: { type: Boolean, default: false },
    mode: { type: String, default: 'add' },
  },

  emits: ['detected', 'send'],

  data() {
    return {
      scanner: null,
      isScanning: false,
      isLoading: false,
      lastScanned: null,
      lastScannedCode: '',
      lastScannedTime: 0,
      retried: false,
    }
  },

  beforeUnmount() {
    this.stopScanning()
  },

  methods: {
    async startScanning() {
      this.isLoading = true
      this.lastScanned = null

      try {
        this.scanner = new Html5Qrcode('barcode-reader', { verbose: false })

        const config = {
          fps: 15,
          qrbox: (w, h) => {
            const side = Math.min(w, h) * 0.75
            return { width: Math.floor(side), height: Math.floor(side * 0.45) }
          },
          disableFlip: false,
          formatsToSupport: [0, 3, 4, 7, 8, 11],
          experimentalFeatures: { useBarCodeDetectorIfSupported: true },
        }

        const videoConstraints = {
          facingMode: 'environment',
          width: { ideal: 1280 },
          height: { ideal: 720 },
        }

        await this.scanner.start(
          videoConstraints,
          config,
          this.onScanSuccess,
          () => { /* scan-in-progress errors — ignore */ }
        )

        this.applyAutofocus()
        this.isScanning = true
      } catch (err) {
        console.error('Camera error:', err)
        if (!this.retried) {
          this.retried = true
          await this.startScanningFallback()
        }
      } finally {
        this.isLoading = false
      }
    },

    async startScanningFallback() {
      try {
        this.scanner = new Html5Qrcode('barcode-reader', { verbose: false })

        const config = {
          fps: 15,
          qrbox: (w, h) => {
            const side = Math.min(w, h) * 0.75
            return { width: Math.floor(side), height: Math.floor(side * 0.45) }
          },
          disableFlip: false,
          formatsToSupport: [0, 3, 4, 7, 8, 11],
          experimentalFeatures: { useBarCodeDetectorIfSupported: true },
        }

        await this.scanner.start(
          { facingMode: 'environment' },
          config,
          this.onScanSuccess,
          () => {}
        )

        this.applyAutofocus()
        this.isScanning = true
      } catch (err) {
        console.error('Camera fallback also failed:', err)
      }
    },

    applyAutofocus() {
      try {
        const videoEl = document.querySelector('#barcode-reader video')
        if (!videoEl || !videoEl.srcObject) return
        const track = videoEl.srcObject.getVideoTracks()[0]
        if (!track) return
        const caps = track.getCapabilities?.()
        if (caps?.focusMode?.includes('continuous')) {
          track.applyConstraints({ advanced: [{ focusMode: 'continuous' }] })
        }
        if (caps?.zoom) {
          const zoom = Math.min(caps.zoom.max, Math.max(caps.zoom.min, 1.5))
          track.applyConstraints({ advanced: [{ zoom }] })
        }
      } catch { /* not supported — ok */ }
    },

    async stopScanning() {
      if (this.scanner && this.isScanning) {
        try {
          await this.scanner.stop()
        } catch { /* already stopped */ }
      }
      this.isScanning = false
    },

    onScanSuccess(decodedText, decodedResult) {
      const now = Date.now()
      // Debounce: ignore the same code within 2 seconds
      if (decodedText === this.lastScannedCode && now - this.lastScannedTime < 2000) {
        return
      }
      this.lastScannedCode = decodedText
      this.lastScannedTime = now

      const formatName = decodedResult?.result?.format?.formatName || 'CODE_128'

      const result = {
        code: decodedText,
        format: formatName,
        timestamp: now,
      }

      // In continuous mode, emit and keep scanning
      if (this.continuous) {
        this.$emit('detected', result)
        this.lastScanned = result

        // Haptic feedback
        try {
          window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success')
        } catch { /* not in telegram */ }

        // Brief visual flash then auto-clear
        setTimeout(() => {
          if (this.lastScanned?.timestamp === result.timestamp) {
            this.lastScanned = null
          }
        }, 3000)
      } else {
        // Single-scan mode: pause and show result
        this.scanner.pause(true)
        this.isScanning = false
        this.$emit('detected', result)

        try {
          window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success')
        } catch { /* not in telegram */ }
      }
    },
  },
}
</script>

<style scoped>
.scanner-card {
  overflow: hidden;
}

.camera-container {
  position: relative;
  width: 100%;
  min-height: 280px;
  background: #000;
  overflow: hidden;
}

.camera-container :deep(video) {
  object-fit: cover !important;
  width: 100% !important;
}

/* Hide the default html5-qrcode UI chrome */
.camera-container :deep(#barcode-reader) {
  border: none !important;
}
.camera-container :deep(#barcode-reader__scan_region) {
  min-height: 250px;
}
/* Hide the built-in scan region box to prevent overlap with our custom overlay */
.camera-container :deep(#barcode-reader__scan_region img),
.camera-container :deep(#barcode-reader__scan_region > br) {
  display: none !important;
}
.camera-container :deep(#qr-shaded-region) {
  display: none !important;
}
.camera-container :deep(#barcode-reader__dashboard_section),
.camera-container :deep(#barcode-reader__dashboard_section_swaplink),
.camera-container :deep(#barcode-reader__status_span),
.camera-container :deep(#barcode-reader__header_message),
.camera-container :deep(#barcode-reader img) {
  display: none !important;
}

/* Scanning overlay */
.scan-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.scan-region {
  position: relative;
  width: 75%;
  height: 40%;
  max-width: 350px;
  max-height: 180px;
}

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #3390ec, transparent);
  box-shadow: 0 0 12px rgba(51, 144, 236, 0.6);
  animation: scan-sweep 2s ease-in-out infinite;
}

@keyframes scan-sweep {
  0%, 100% { top: 0; }
  50% { top: 100%; }
}

/* Corner markers */
.corner {
  position: absolute;
  width: 24px;
  height: 24px;
  border-color: #3390ec;
  border-style: solid;
  border-width: 0;
}
.corner.tl { top: 0; left: 0; border-top-width: 3px; border-left-width: 3px; border-top-left-radius: 6px; }
.corner.tr { top: 0; right: 0; border-top-width: 3px; border-right-width: 3px; border-top-right-radius: 6px; }
.corner.bl { bottom: 0; left: 0; border-bottom-width: 3px; border-left-width: 3px; border-bottom-left-radius: 6px; }
.corner.br { bottom: 0; right: 0; border-bottom-width: 3px; border-right-width: 3px; border-bottom-right-radius: 6px; }

/* Loading */
.loading-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
}

/* Last scanned chip */
.last-scanned {
  display: flex;
  justify-content: center;
  animation: pop-in 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes pop-in {
  0% { transform: scale(0); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
</style>
