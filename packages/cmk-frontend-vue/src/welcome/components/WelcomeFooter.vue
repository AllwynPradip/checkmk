<!--
Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->

<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'
import usei18n from '@/lib/i18n'
import CmkCheckbox from '@/components/user-input/CmkCheckbox.vue'
import CmkParagraph from '@/components/typography/CmkParagraph.vue'

const props = defineProps<{
  is_start_url: boolean
}>()

const { t } = usei18n('welcome-footer')
const showWelcomeOnStart = ref(props.is_start_url)
const welcomeString = ref('welcome.py')

watch(showWelcomeOnStart, async (newValue) => {
  if (newValue) {
    await setStartUrl(welcomeString.value)
  } else {
    await setStartUrl()
  }
})

const setStartUrl = async (startUrlValue?: string): Promise<void> => {
  try {
    const url = 'ajax_set_dashboard_start_url.py'
    const response = await axios.post(url, null, {
      params: {
        name: startUrlValue,
        // @ts-expect-error  TODO change if something is implemented to use CSRF token
        _csrf_token: global_csrf_token
      }
    })

    if (response.data.result_code !== 0) {
      console.error('Error setting start URL:', response.data.result)
    } else {
      window.top?.location.reload()
    }
  } catch (error) {
    console.error('Request failed:', error)
  }
}
</script>

<template>
  <section class="welcome-footer">
    <CmkCheckbox
      v-model="showWelcomeOnStart"
      :label="t('show-on-start', 'Show welcome page on start')"
    />
    <CmkParagraph class="welcome-footer__hint">
      {{
        t(
          'access-breadcrumbs',
          'You can still access it later via Help > Learning Checkmk > Welcome page'
        )
      }}
    </CmkParagraph>
  </section>
</template>

<style scoped>
.welcome-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
}

.welcome-footer__hint {
  color: var(--font-color-dimmed);
  margin-top: 4px;
}
</style>
