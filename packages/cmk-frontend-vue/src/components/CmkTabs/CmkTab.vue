<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import { TabsTrigger } from 'radix-vue'

export interface CmkTabProps {
  id: string
  disabled?: boolean | undefined
}

defineProps<CmkTabProps>()
</script>

<template>
  <TabsTrigger :value="id" :disabled="!!disabled" as="li" class="cmk-tab-li">
    <slot />
  </TabsTrigger>
</template>

<style scoped>
.cmk-tab-li {
  display: flex;
  flex-direction: row;
  background: var(--ux-theme-0);
  padding: var(--spacing-half) var(--spacing) !important;
  border: 1px solid var(--ux-theme-7);
  font-weight: var(--font-weight-default);
  line-height: var(--form-field-height);
  border-right: 0 solid var(--ux-theme-0);

  &:first-of-type {
    border-top-left-radius: var(--border-radius);
  }

  &:last-of-type {
    border-top-right-radius: var(--border-radius);
    border-right: 1px solid var(--ux-theme-7);
  }

  &:hover {
    cursor: pointer;
    background: var(--ux-theme-2);
  }

  &:focus-visible {
    outline: none;
    border: 1px solid var(--success);
  }

  &[data-state='active'] {
    background: var(--ux-theme-7);
    font-weight: var(--font-weight-bold);
  }
  &[data-disabled] {
    opacity: 0.6;
    cursor: default;
    background: var(--ux-theme-0);
  }
}
</style>
