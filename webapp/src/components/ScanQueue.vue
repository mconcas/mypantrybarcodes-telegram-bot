<template>
  <div class="scan-queue">
    <!-- Empty state -->
    <v-card v-if="!scans.length" class="ma-4" variant="flat">
      <v-card-text class="text-center pa-8">
        <v-icon size="64" color="grey-lighten-1" class="mb-4">mdi-cart-outline</v-icon>
        <div class="text-h6 text-medium-emphasis mb-2">Queue is empty</div>
        <div class="text-body-2 text-medium-emphasis">
          Scan barcodes to add them to the queue, then send them all at once.
        </div>
      </v-card-text>
    </v-card>

    <!-- Queue list -->
    <template v-if="scans.length">
      <div class="queue-header d-flex align-center px-4 pt-4">
        <div class="text-subtitle-1 font-weight-medium">
          <v-icon class="mr-1" :color="mode === 'add' ? 'success' : 'error'">
            {{ mode === 'add' ? 'mdi-plus-circle' : 'mdi-minus-circle' }}
          </v-icon>
          {{ scans.length }} item{{ scans.length !== 1 ? 's' : '' }} to {{ mode }}
        </div>
        <v-spacer />
        <v-btn
          variant="text"
          color="error"
          size="small"
          prepend-icon="mdi-delete-sweep"
          @click="$emit('clear')"
        >
          Clear
        </v-btn>
      </div>

      <v-list class="mx-2">
        <v-list-item
          v-for="(scan, index) in scans"
          :key="scan.code + '-' + scan.timestamp"
          class="mb-1"
          rounded="lg"
        >
          <template v-slot:prepend>
            <v-avatar :color="getFormatColor(scan.format)" size="40">
              <v-icon color="white" size="20">mdi-barcode</v-icon>
            </v-avatar>
          </template>

          <v-list-item-title class="font-weight-medium">
            {{ scan.code }}
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ getFormatLabel(scan.format) }}
            <v-chip v-if="scan.count > 1" size="x-small" color="primary" variant="tonal" class="ml-1">
              ×{{ scan.count }}
            </v-chip>
          </v-list-item-subtitle>

          <template v-slot:append>
            <v-btn
              icon="mdi-close"
              variant="text"
              size="small"
              color="error"
              @click="$emit('remove', index)"
            />
          </template>
        </v-list-item>
      </v-list>

      <!-- Send all button -->
      <div class="send-bar pa-4">
        <v-btn
          block
          size="large"
          :color="mode === 'add' ? 'success' : 'error'"
          rounded="pill"
          :prepend-icon="mode === 'add' ? 'mdi-cart-plus' : 'mdi-cart-minus'"
          @click="$emit('send-all')"
        >
          {{ mode === 'add' ? 'Add' : 'Remove' }} {{ totalCount }} item{{ totalCount !== 1 ? 's' : '' }}
        </v-btn>
      </div>
    </template>
  </div>
</template>

<script>
export default {
  name: 'ScanQueue',

  props: {
    scans: { type: Array, required: true },
    mode: { type: String, default: 'add' },
    themeColors: { type: Object, required: true },
  },

  emits: ['remove', 'clear', 'send-all'],

  computed: {
    totalCount() {
      return this.scans.reduce((sum, s) => sum + (s.count || 1), 0)
    },
  },

  methods: {
    getFormatColor(format) {
      const map = {
        'EAN_13': '#4caf50',
        'EAN_8': '#4caf50',
        'CODE_128': '#2196f3',
        'QR_CODE': '#9c27b0',
      }
      return map[format] || '#757575'
    },

    getFormatLabel(format) {
      const map = {
        'EAN_13': 'EAN-13',
        'EAN_8': 'EAN-8',
        'CODE_128': 'Code 128',
        'QR_CODE': 'QR Code',
      }
      return map[format] || format
    },
  },
}
</script>

<style scoped>
.scan-queue {
  padding-bottom: 100px;
}

.send-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  z-index: 10;
}
</style>
