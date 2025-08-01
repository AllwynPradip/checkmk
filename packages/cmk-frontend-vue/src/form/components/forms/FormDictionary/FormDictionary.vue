<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import { cva } from 'class-variance-authority'
import { computed, ref } from 'vue'
import { useFormEditDispatcher } from '@/form/private'

import { immediateWatch } from '@/lib/watch'
import type * as FormSpec from 'cmk-shared-typing/typescript/vue_formspec_components'
import { groupNestedValidations, type ValidationMessages } from '@/form/components/utils/validation'
import FormHelp from '@/form/private/FormHelp.vue'
import { useId } from '@/form/utils'
import CmkCheckbox from '@/components/user-input/CmkCheckbox.vue'
import CmkHtml from '@/components/CmkHtml.vue'
import FormRequired from '@/form/private/FormRequired.vue'
import FormReadonly from '@/form/components/FormReadonly.vue'
import { rendersRequiredLabelItself } from '@/form/private/requiredValidator'
import FormIndent from '@/components/CmkIndent.vue'
import FormValidation from '@/components/user-input/CmkInlineValidation.vue'

import { getElementsInGroupsFromProps, toggleElement, titleRequired } from './_groups'

const dictionaryVariants = cva('', {
  variants: {
    group_layout: {
      none: '',
      horizontal: 'horizontal_groups',
      vertical: 'vertical_groups'
    }
  },
  defaultVariants: {
    group_layout: 'none'
  }
})

const props = defineProps<{
  spec: FormSpec.Dictionary
  backendValidation: ValidationMessages
}>()

const data = defineModel<Record<string, unknown>>('data', { required: true })
const elementValidation = ref<Record<string, ValidationMessages>>({})
const validation = ref<ValidationMessages>([])

immediateWatch(
  () => props.spec.additional_static_elements,
  (newAdditionalStaticElements: FormSpec.Dictionary['additional_static_elements'] | undefined) => {
    if (newAdditionalStaticElements) {
      for (const [key, value] of Object.entries(newAdditionalStaticElements)) {
        data.value[key] = value
      }
    }
  }
)

immediateWatch(
  () => props.backendValidation,
  (newValidation: ValidationMessages) => {
    const [dictionaryValidation, dictionaryElementsValidation] = groupNestedValidations(
      props.spec.elements,
      newValidation
    )
    elementValidation.value = dictionaryElementsValidation
    validation.value = dictionaryValidation
  }
)

function indentRequired(
  element: FormSpec.DictionaryElement,
  layout: FormSpec.DictionaryGroupLayout
): boolean {
  return (
    titleRequired(element) &&
    !(element.group && layout === 'horizontal') &&
    !(
      element.parameter_form.type === 'fixed_value' &&
      !(element.parameter_form as FormSpec.FixedValue).label &&
      !(element.parameter_form as FormSpec.FixedValue).value
    )
  )
}

const groups = computed(() => getElementsInGroupsFromProps(props.spec.elements, data))

const componentId = useId()

// eslint-disable-next-line @typescript-eslint/naming-convention
const { FormEditDispatcher } = useFormEditDispatcher()
</script>

<template>
  <table
    v-if="props.spec.elements.length > 0"
    class="dictionary"
    :aria-label="props.spec.title"
    role="group"
  >
    <tbody>
      <tr v-for="group in groups" :key="`${componentId}.${group.groupKey}`">
        <td class="dictleft">
          <div v-if="!!group.title" class="form-dictionary__group-title">{{ group?.title }}</div>
          <FormHelp v-if="group.help" :help="group.help" />
          <div
            class="form-dictionary__group-elems"
            :class="dictionaryVariants({ group_layout: group.layout })"
          >
            <div
              v-for="dict_element in group.elems"
              :key="`${componentId}.${dict_element.dict_config.name}`"
              class="form-dictionary__group_elem"
            >
              <span
                v-if="titleRequired(dict_element.dict_config)"
                class="form-dictionary__group-elem__title"
              >
                <span
                  v-if="dict_element.dict_config.required"
                  :class="{
                    'form-dictionary__required-without-indent': !indentRequired(
                      dict_element.dict_config,
                      group.layout
                    )
                  }"
                >
                  <CmkHtml :html="dict_element.dict_config.parameter_form.title" /><FormRequired
                    v-if="!rendersRequiredLabelItself(dict_element.dict_config.parameter_form)"
                    :spec="dict_element.dict_config.parameter_form"
                    :space="'before'"
                  />
                </span>
                <CmkCheckbox
                  v-else
                  v-model="dict_element.is_active"
                  :padding="
                    dict_element.is_active && indentRequired(dict_element.dict_config, group.layout)
                      ? 'top'
                      : 'both'
                  "
                  :label="dict_element.dict_config.parameter_form.title"
                  :help="dict_element.dict_config.parameter_form.help"
                  @update:model-value="
                    toggleElement(data, spec.elements, dict_element.dict_config.name)
                  "
                />
              </span>
              <FormIndent
                v-if="dict_element.is_active"
                :indent="indentRequired(dict_element.dict_config, group.layout)"
              >
                <FormEditDispatcher
                  v-if="!dict_element.dict_config.render_only"
                  v-model:data="data[dict_element.dict_config.name]"
                  :spec="dict_element.dict_config.parameter_form"
                  :backend-validation="elementValidation[dict_element.dict_config.name]!"
                />
                <FormReadonly
                  v-else
                  :data="data[dict_element.dict_config.name]"
                  :backend-validation="elementValidation[dict_element.dict_config.name]!"
                  :spec="dict_element.dict_config.parameter_form"
                ></FormReadonly>
              </FormIndent>
            </div>
          </div>
        </td>
      </tr>
    </tbody>
  </table>
  <span v-else>{{ spec.no_elements_text }}</span>
  <FormValidation :validation="validation.map((m) => m.message)"></FormValidation>
</template>

<style scoped>
.form-dictionary__group-title {
  font-weight: bold;
  margin: var(--spacing) 0;
}

tr:first-of-type > td > .form-dictionary__group-title {
  margin-top: 0;
}

tr:last-of-type > td > div > .form-dictionary__group_elem:last-of-type {
  margin-bottom: 0;
}

.form-dictionary__required-without-indent {
  display: inline-block;
  margin-bottom: var(--spacing-half);
}

.form-dictionary__group-elems {
  flex-direction: row;
  gap: 0.5em;
  &.horizontal_groups {
    display: flex;
  }
}

.form-dictionary__group_elem {
  margin-bottom: var(--spacing);
}
</style>
