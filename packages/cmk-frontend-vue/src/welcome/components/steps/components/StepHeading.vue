<!--
Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->

<script setup lang="ts">
import CmkHeading from '@/components/typography/CmkHeading.vue'
</script>

<template>
  <CmkHeading type="h4" class="step-section-heading">
    <slot />
  </CmkHeading>
</template>

<style scoped>
.step-section-heading {
  margin-bottom: var(--spacing-half);
}
</style>
