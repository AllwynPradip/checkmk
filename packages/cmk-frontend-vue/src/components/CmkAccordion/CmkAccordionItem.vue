<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import { AccordionContent, AccordionHeader, AccordionItem } from 'radix-vue'
import CmkAccordionTrigger from './CmkAccordionTrigger.vue'

export interface CmkAccordionItemProps {
  value: string
  headerAs?: string
  disabled?: boolean | undefined
}

const { headerAs = 'h3', value = '', disabled = false } = defineProps<CmkAccordionItemProps>()
</script>

<template>
  <AccordionItem :value="value" :disabled="disabled" class="cmk-accordion-item">
    <AccordionHeader :as="headerAs" class="cmk-accordion-item-header"
      ><CmkAccordionTrigger :value="value" :disabled="disabled ? true : false">
        <slot name="header" />
      </CmkAccordionTrigger>
    </AccordionHeader>
    <AccordionContent
      :id="'cmk-accordion-content-'.concat(value)"
      class="cmk-accordion-item-content"
      as="section"
      :aria-labelledby="'cmk-accordion-trigger-'.concat(value)"
    >
      <div class="cmk-accordion-item-content-wrapper">
        <slot name="content" />
      </div>
    </AccordionContent>
  </AccordionItem>
</template>

<style scoped>
.cmk-accordion-item {
  display: flex;
  flex-direction: column;
  border: 1px solid transparent;
  background: var(--ux-theme-3);
  border-radius: 4px;
  overflow: hidden;
  width: 100%;
  margin-bottom: 8px;

  &[data-state='open'] {
    border: 1px solid var(--color-corporate-green-50);
  }

  &:last-of-type {
    margin-bottom: 0;
  }
}

.cmk-accordion-item-content-wrapper {
  overflow: hidden;
}

.cmk-accordion-item-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  width: 100%;
  border-bottom: 1px transparent;
  border-radius: 4px;
  position: relative;
  margin: 0;

  &:hover {
    background: var(--ux-theme-6);
  }

  &[data-state='open'] {
    border-bottom: 1px solid var(--success);
    border-radius: 4px 4px 0 0;
  }
}

.cmk-accordion-item-content {
  margin: 20px 60px 8px 60px;
  &:focus-within {
    position: relative;
    z-index: 1;
  }

  &[data-state='open'] {
    animation: slideDown 0.3s ease-out;
  }

  &[data-state='closed'] {
    animation: slideUp 0.3s ease-out;
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    height: 0;
  }
  to {
    opacity: 1;
    height: var(--radix-accordion-content-height);
  }
}

@keyframes slideUp {
  from {
    opacity: 1;
    height: var(--radix-accordion-content-height);
  }
  to {
    opacity: 0;
    height: 0;
  }
}

/* Disabled Styling */
.cmk-accordion-item[data-disabled] {
  opacity: 0.7;
  cursor: default;

  .cmk-accordion-item-header[data-disabled]:hover {
    background: transparent;
  }
}
</style>
