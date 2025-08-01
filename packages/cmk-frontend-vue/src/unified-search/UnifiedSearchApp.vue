<!--
Copyright (C) 2025 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import { inject, nextTick, onMounted, ref } from 'vue'
import { UnifiedSearch, type UnifiedSearchResult } from '@/lib/unified-search/unified-search'
import { type Providers } from 'cmk-shared-typing/typescript/unified_search'
import {
  SearchHistorySearchProvider,
  type SearchHistorySearchResult
} from '@/lib/unified-search/providers/history'
import UnifiedSearchHeader from './UnifiedSearchHeader.vue'
import UnifiedSearchStart from './UnifiedSearchStart.vue'
import UnifiedSearchFooter from './UnifiedSearchFooter.vue'
import { apiServiceProvider } from './providers/api'
import { SearchHistoryService } from '@/lib/unified-search/searchHistory'
import { Api } from '@/lib/api-client'
import DefaultPopup from '@/main-menu/DefaultPopup.vue'
import UnifiedSearchTabResults from './UnifiedSearchTabResults.vue'
import {
  initSearchUtils,
  provideSearchUtils,
  type UnifiedSearchQueryLike
} from './providers/search-utils'
import {
  UnifiedSearchProvider,
  type UnifiedSearchProviderIdentifier
} from '@/lib/unified-search/providers/unified'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const cmk: any

const searchId = 'unified-search'

const api = inject(apiServiceProvider, new Api(), true)
const searchHistoryService = new SearchHistoryService(searchId)

const props = defineProps<{
  providers: Providers
}>()

const searchProviderIdentifiers: { id: UnifiedSearchProviderIdentifier; sort: number }[] = []
if (props.providers.setup.active) {
  searchProviderIdentifiers.push({ id: 'setup', sort: props.providers.setup.sort })
}
if (props.providers.customize.active) {
  searchProviderIdentifiers.push({ id: 'customize', sort: props.providers.customize.sort })
}
if (props.providers.monitoring.active) {
  searchProviderIdentifiers.push({ id: 'monitoring', sort: props.providers.monitoring.sort })
}

const searchHistorySearchProvider = new SearchHistorySearchProvider(
  searchHistoryService as SearchHistoryService
)
const search = new UnifiedSearch(searchId, api, [
  new UnifiedSearchProvider(
    searchProviderIdentifiers.sort((a, b) => a.sort - b.sort).map((p) => p.id)
  ),
  searchHistorySearchProvider
])
search.onSearch((result?: UnifiedSearchResult) => {
  searchResult.value = undefined
  void nextTick(() => {
    searchResult.value = result
  })
})
const searchResult = ref<UnifiedSearchResult>()
const searchUtils = initSearchUtils()

searchUtils.search = search
searchUtils.history = searchHistoryService

provideSearchUtils(searchUtils)

searchUtils.onResetSearch(() => {
  searchResult.value = undefined
})

searchUtils.onCloseSearch(() => {
  cmk.popup_menu.close_popup()
})

searchUtils.input.onSetQuery((query?: UnifiedSearchQueryLike) => {
  if (query && query.input !== '/') {
    search.initSearch(query)
  }
})

searchUtils.shortCuts.onEscape(() => {
  if (searchUtils.input.suggestionsActive.value === false) {
    searchUtils.resetSearch()
    searchUtils.closeSearch()
  }
})

function showTabResults(): boolean {
  return (
    typeof searchResult.value !== 'undefined' &&
    (search.get('unified') as UnifiedSearchProvider).shouldExecuteSearch(
      searchUtils.query.toQueryLike()
    )
  )
}

onMounted(() => {
  searchUtils.shortCuts.enable()
})
</script>

<template>
  <DefaultPopup class="unified-search-root">
    <UnifiedSearchHeader> </UnifiedSearchHeader>
    <UnifiedSearchStart
      v-if="!showTabResults()"
      :history-result="searchResult?.get('search-history') as SearchHistorySearchResult"
    >
    </UnifiedSearchStart>
    <UnifiedSearchTabResults v-if="!!showTabResults()" :unified-result="searchResult">
    </UnifiedSearchTabResults>
    <UnifiedSearchFooter></UnifiedSearchFooter>
  </DefaultPopup>
</template>

<style scoped>
.unified-search-root {
  position: absolute;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 58px);
  background: var(--ux-theme-1);
  z-index: +1;
  left: 0;
  top: 58px;
  border-right: 4px solid var(--success);
  border-top-width: 0;
  width: 750px;
  max-width: 750px;
}
</style>
