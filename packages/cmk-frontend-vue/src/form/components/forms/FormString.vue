<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import type * as FormSpec from 'cmk-shared-typing/typescript/vue_formspec_components'
import { useValidation, type ValidationMessages } from '@/form/components/utils/validation'
import FormValidation from '@/components/user-input/CmkInlineValidation.vue'
import FormAutocompleter from '@/form/private/FormAutocompleter.vue'
import CmkInput from '@/components/user-input/CmkInput.vue'
import { inputSizes } from '@/components/user-input/sizes'
import CmkSpace from '@/components/CmkSpace.vue'
import CmkDropdownButton from '@/components/CmkDropdownButton.vue'
import { useId } from '@/form/utils'
import FormRequired from '@/form/private/FormRequired.vue'
import FormLabel from '@/form/private/FormLabel.vue'
import { X } from 'lucide-vue-next'

defineOptions({
  inheritAttrs: false
})

const props = defineProps<{
  spec: FormSpec.String
  backendValidation: ValidationMessages
}>()

const data = defineModel<string>('data', { required: true })
const [validation, value] = useValidation<string>(
  data,
  props.spec.validators,
  () => props.backendValidation
)

const componentId = useId()
</script>

<template>
  <template v-if="props.spec.label">
    <FormLabel :for="componentId">{{ props.spec.label }}<CmkSpace size="small" /> </FormLabel>
    <FormRequired :spec="props.spec" :space="'after'" />
  </template>
  <template v-if="spec.autocompleter">
    <div class="cmk-form-string--dropdown-container">
      <FormAutocompleter
        :id="componentId"
        v-model="value"
        class="cmk-form-string--dropdown"
        :size="inputSizes[props.spec.field_size].width"
        :reset-input-on-add="false"
        :autocompleter="spec.autocompleter"
        :placeholder="spec.input_hint ?? ''"
        :label="spec.label || ''"
        :start-of-group="true"
        :show-icon="true"
      /><CmkDropdownButton group="end" @click="value = ''">
        <X class="form-string__button-clear-x" />
      </CmkDropdownButton>
    </div>
    <FormValidation :validation="validation"></FormValidation>
  </template>
  <CmkInput
    v-else
    :id="componentId"
    v-model="value"
    :type="'text'"
    :placeholder="spec.input_hint || ''"
    :aria-label="spec.label || spec.title || ''"
    :size="props.spec.field_size"
    :external-errors="validation"
  />
</template>

<style scoped>
.form-string__button-clear-x {
  width: 13px;
}
.cmk-form-string--dropdown {
  display: block;
  float: left; /* align nicely with clear button*/
  margin-right: 1px;
}
</style>
