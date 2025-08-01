<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->
<script setup lang="ts">
import usei18n from '@/lib/i18n'
import { onBeforeUnmount, ref } from 'vue'
import CmkTabs from '@/components/CmkTabs/CmkTabs.vue'
import CmkTab from '@/components/CmkTabs/CmkTab.vue'
import CmkTabContent from '@/components/CmkTabs/CmkTabContent.vue'
import type { CmkIconProps } from '@/components/CmkIcon.vue'
import type { SearchProviderResult, UnifiedSearchResult } from '@/lib/unified-search/unified-search'
import ResultList from './result/ResultList.vue'
import ResultItem from './result/ResultItem.vue'
import { immediateWatch } from '@/lib/watch'
import CmkIcon from '@/components/CmkIcon.vue'
import CmkScrollContainer from '@/components/CmkScrollContainer.vue'
import { getSearchUtils } from './providers/search-utils'
import {
  providerIcons,
  type UnifiedSearchProvider,
  type UnifiedSearchResultElement,
  type UnifiedSearchResultResponse
} from '@/lib/unified-search/providers/unified'
import CmkChip from '@/components/CmkChip.vue'
import { HistoryEntry } from '@/lib/unified-search/searchHistory'
import UnifiedSearchEmptyResults from './UnifiedSearchEmptyResults.vue'

const { t } = usei18n('unified-search-app')

export interface TabbedResult {
  count: number
  results?: UnifiedSearchResultElement[] | undefined
  title: string
  icon?: CmkIconProps | undefined
}

const searchUtils = getSearchUtils()
const currentlySelected = ref<number>(-1)
const currentlySelectedTab = ref<number>(0)
const renderTabs = ref<boolean>(false)
const tabModel = ref<string>('0')
const tabbedResults = ref<TabbedResult[]>([])
searchUtils.input?.onSetFocus(() => {
  currentlySelected.value = -1
})

const scCallbackIds = ref<string[]>([])
scCallbackIds.value.push(searchUtils.shortCuts.onArrowDown(toggleDown))
scCallbackIds.value.push(searchUtils.shortCuts.onArrowUp(toggleUp))
scCallbackIds.value.push(searchUtils.shortCuts.onCtrlArrowRight(toggleRight))
scCallbackIds.value.push(searchUtils.shortCuts.onCtrlArrowLeft(toggleLeft))

function toggleDown() {
  calcCurrentlySelected(+1)
}

function toggleUp() {
  calcCurrentlySelected(-1)
}

function toggleRight() {
  calcCurrentlySelectedTab(+1)
}

function toggleLeft() {
  calcCurrentlySelectedTab(-1)
}

function calcCurrentlySelected(d: number, set: boolean = false) {
  if (searchUtils.input.suggestionsActive.value === false && searchResultNotEmpty()) {
    if (set) {
      currentlySelected.value = d
    } else {
      currentlySelected.value += d
    }

    const curTabResLength = tabbedResults.value[parseInt(tabModel.value)]?.results?.length || 0

    if (currentlySelected.value === -1 || currentlySelected.value > curTabResLength - 1) {
      currentlySelected.value = -1
      searchUtils.input?.setFocus()
      return
    }

    if (currentlySelected.value < -1) {
      currentlySelected.value = curTabResLength - 1
    }
  }
}

function calcCurrentlySelectedTab(d: number, set: boolean = false) {
  if (searchUtils.input.suggestionsActive.value === false && searchResultNotEmpty()) {
    if (set) {
      currentlySelectedTab.value = d
    } else {
      currentlySelectedTab.value += d
    }

    if (tabbedResults.value[currentlySelectedTab.value]?.count === 0) {
      calcCurrentlySelectedTab(d)
      return
    }

    if (currentlySelectedTab.value === -1) {
      currentlySelectedTab.value = tabbedResults.value.length - 1
    }

    if (currentlySelectedTab.value >= tabbedResults.value.length) {
      currentlySelectedTab.value = 0
    }

    tabModel.value = currentlySelectedTab.value.toString()
    searchUtils.input.setBlur()
    currentlySelected.value = -1
    setTimeout(() => {
      toggleDown()
    }, 0)
  }
}

function handleItemClick(item: UnifiedSearchResultElement) {
  searchUtils.history?.add(new HistoryEntry(searchUtils.query.toQueryLike(), item))
  searchUtils.resetSearch()
  searchUtils.closeSearch()
}

const isFocused = (tab: number, i: number): boolean =>
  currentlySelectedTab.value === tab && currentlySelected.value === i

const props = defineProps<{
  unifiedResult?: UnifiedSearchResult | undefined
}>()

immediateWatch(
  () => ({ newResult: props.unifiedResult }),
  async ({ newResult }) => {
    if (newResult) {
      const tR: TabbedResult[] = []
      const uspr = newResult.get('unified') as SearchProviderResult<UnifiedSearchResultResponse>
      const res = (await uspr.result) as UnifiedSearchResultResponse
      if (res) {
        tR.push({
          count: res.counts.total,
          title: t('all-results', 'All results'),
          results: res.results
        })
        for (const provider of (searchUtils.search?.get('unified') as UnifiedSearchProvider)
          .providers) {
          tR.push({
            count: res.counts[provider] || 0,
            title: t(provider, provider),
            results: res.results.filter((el) => el.provider === provider),
            icon: providerIcons[provider]
          })
        }

        tabbedResults.value = tR
        renderTabs.value = true
      }
    }
  }
)

onBeforeUnmount(() => {
  searchUtils.shortCuts.remove(scCallbackIds.value)
})

function searchResultNotEmpty(): boolean {
  return (
    typeof tabbedResults.value[0] !== 'undefined' &&
    typeof tabbedResults.value[0].results !== 'undefined' &&
    tabbedResults.value[0].results.length > 0
  )
}
</script>

<template>
  <div v-if="searchResultNotEmpty()" class="cmk-unified-search-result-tabs">
    <div class="cmk-unified-search-tab-info">
      <span>{{ t('press', 'Press') }}</span>
      <CmkChip size="small" :content="t('ctrl', 'Ctrl')"></CmkChip>+<CmkChip
        class="arrow-key left"
        size="small"
        content=""
      ></CmkChip
      >|<CmkChip class="arrow-key right" size="small" content=""></CmkChip><br />
      <span>{{ t('to-nav-tabs', 'to navigate between tabs') }}</span>
    </div>
    <CmkTabs v-model="tabModel">
      <template #tabs>
        <CmkTab
          v-for="(tab, idx) in tabbedResults"
          :id="idx.toString()"
          :key="tab.title"
          :disabled="!tab.results || tab.results?.length === 0"
          class="cmk-unified-search-result-tab"
        >
          <CmkIcon v-if="tab.icon" :name="tab.icon.name" class="tab-icon"></CmkIcon>
          <div>
            {{ tab.title }} <span>({{ tab.count }})</span>
          </div>
        </CmkTab>
      </template>
      <template #tab-contents>
        <CmkTabContent
          v-for="(tab, idx) in tabbedResults"
          :id="idx.toString()"
          :key="tab.title"
          spacing="none"
          class="cmk-unified-search-result-tab-content"
        >
          <CmkScrollContainer max-height="calc(100vh - 260px)">
            <ResultList>
              <ResultItem
                v-for="(item, idxe) in tab.results"
                ref="recently-viewed-item"
                :key="item.url ? item.url : item.title"
                :idx="idxe"
                :title="item.title"
                :context="item.context"
                :icon="providerIcons[item.provider]"
                :url="item.url"
                :html="searchUtils.highlightQuery(item.title)"
                :breadcrumb="searchUtils.breadcrumb(item.provider, item.topic)"
                :focus="isFocused(idx, idxe)"
                @keypress.enter="
                  () => {
                    handleItemClick(item)
                  }
                "
                @click="
                  () => {
                    handleItemClick(item)
                  }
                "
              ></ResultItem>
            </ResultList>
          </CmkScrollContainer>
        </CmkTabContent>
      </template>
    </CmkTabs>
  </div>
  <UnifiedSearchEmptyResults v-if="!searchResultNotEmpty()"></UnifiedSearchEmptyResults>
</template>

<style scoped>
.cmk-unified-search-tab-info {
  position: absolute;
  max-width: 200px;
  right: var(--spacing-double);
  margin-top: 3px;
  line-height: 14px;
  font-size: var(--font-size-small);
  opacity: 0.5;

  .arrow-key {
    width: 11px;
    display: inline-flex;
    height: 12px;
    margin-bottom: -4px;

    &::after {
      font-size: 21px;
      position: absolute;
      margin: -4px 0 0 -5px;
    }

    &.left::after {
      content: '\2190';
    }

    &.right::after {
      content: '\2192';
    }
  }
}

.arrow-key {
  width: 11px;
  display: inline-flex;
  height: 12px;
  margin-bottom: -4px;

  &::after {
    font-size: 21px;
    position: absolute;
    margin: -4px 0 0 -5px;
  }

  &.left::after {
    content: '\2190';
  }

  &.right::after {
    content: '\2192';
  }

  &.enter::after {
    content: '\21B5';
  }
}

.cmk-unified-search-result-tabs {
  margin: var(--spacing-double);
  height: 100%;
}

.cmk-unified-search-result-tab {
  display: flex;
  flex-direction: row;
  align-items: center;

  .tab-icon {
    margin-right: var(--spacing);
  }

  div {
    &::first-letter {
      text-transform: capitalize;
    }

    span {
      font-weight: var(--font-weight-default);
    }
  }
}
</style>
