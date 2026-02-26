<template>
  <div class="mode-selector pa-3">
    <v-btn-toggle
      :model-value="modelValue"
      @update:model-value="$emit('update:modelValue', $event)"
      mandatory
      rounded="pill"
      density="comfortable"
      :color="modelValue === 'add' ? 'success' : 'error'"
      class="w-100"
    >
      <v-btn value="add" class="flex-grow-1">
        <v-icon start>mdi-plus-circle-outline</v-icon>
        Add Items
      </v-btn>
      <v-btn value="remove" class="flex-grow-1">
        <v-icon start>mdi-minus-circle-outline</v-icon>
        Remove Items
      </v-btn>
    </v-btn-toggle>
  </div>
</template>

<script>
export default {
  name: 'ModeSelector',

  props: {
    modelValue: { type: String, required: true },
    themeColors: { type: Object, required: true },
  },

  emits: ['update:modelValue'],
}
</script>

<style scoped>
.mode-selector {
  display: flex;
  justify-content: center;
}
.w-100 {
  width: 100%;
}
</style>
