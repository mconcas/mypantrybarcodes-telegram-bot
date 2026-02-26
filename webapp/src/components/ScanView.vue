<template>
  <div class="scan-view">
    <!-- Camera barcode scanner -->
    <div class="mx-4 mt-4">
      <BarcodeScanner
        :continuous="true"
        :mode="mode"
        @detected="$emit('detected', $event)"
        @send="$emit('send-single', $event)"
      />
    </div>

    <v-divider class="mx-4">
      <span class="text-medium-emphasis text-caption px-2">or enter manually</span>
    </v-divider>

    <!-- Manual entry -->
    <v-card class="ma-4" variant="outlined" rounded="xl">
      <v-card-text class="pa-5">
        <div class="text-subtitle-1 font-weight-medium mb-4">
          <v-icon class="mr-1">mdi-keyboard</v-icon>
          Manual Entry
        </div>

        <v-text-field
          v-model="manualCode"
          label="Barcode number"
          placeholder="e.g. 4006381333931"
          variant="outlined"
          rounded="lg"
          density="comfortable"
          prepend-inner-icon="mdi-barcode"
          clearable
          :rules="[v => !!v || 'Enter a code']"
          @keyup.enter="submitManual"
        />

        <v-btn
          block
          color="primary"
          rounded="pill"
          :disabled="!manualCode"
          prepend-icon="mdi-plus-circle"
          @click="submitManual"
        >
          Add to Queue
        </v-btn>
      </v-card-text>
    </v-card>
  </div>
</template>

<script>
import BarcodeScanner from './BarcodeScanner.vue'

export default {
  name: 'ScanView',

  components: { BarcodeScanner },

  props: {
    themeColors: { type: Object, required: true },
    isTelegramClient: { type: Boolean, default: false },
    mode: { type: String, default: 'add' },
  },

  emits: ['detected', 'send-single'],

  data() {
    return {
      manualCode: '',
    }
  },

  methods: {
    submitManual() {
      if (!this.manualCode) return
      const result = {
        code: this.manualCode.trim(),
        format: this.detectFormat(this.manualCode.trim()),
        timestamp: Date.now(),
      }
      this.$emit('send-single', result)
      this.manualCode = ''
    },

    detectFormat(code) {
      if (/^\d{13}$/.test(code)) return 'EAN_13'
      if (/^\d{8}$/.test(code)) return 'EAN_8'
      if (/^https?:\/\//.test(code) || code.length > 50) return 'QR_CODE'
      return 'CODE_128'
    },
  },
}
</script>

<style scoped>
.scan-view {
  padding-bottom: 80px;
}
</style>
