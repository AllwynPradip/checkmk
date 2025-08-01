<!--
Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
conditions defined in the file COPYING, which is part of this source code package.
-->

<script setup lang="ts">
import {
  type ModeHostFormKeys,
  type ModeHostSite,
  type ModeHostAgentConnectionMode,
  type I18NPingHost
} from 'cmk-shared-typing/typescript/mode_host'
import PingHost from '@/mode-host/ping-host/PingHost.vue'
import { onMounted, ref, type Ref } from 'vue'
import AgentConnectionTest from '@/mode-host/agent-connection-test/AgentConnectionTest.vue'

const props = defineProps<{
  i18n_ping_host: I18NPingHost
  form_keys: ModeHostFormKeys
  sites: Array<ModeHostSite>
  agent_connection_modes: Array<ModeHostAgentConnectionMode>
  all_agents_url: string
  host_name: string
}>()

const formElement: Ref<HTMLFormElement | null> = ref(null)
const hostnameInputElement: Ref<HTMLInputElement | null> = ref(null)
const siteSelectElement: Ref<HTMLSelectElement | null> = ref(null)
const ipv4InputElement: Ref<HTMLInputElement | null> = ref(null)
const ipv4InputButtonElement: Ref<HTMLInputElement | null> = ref(null)
const ipv6InputElement: Ref<HTMLInputElement | null> = ref(null)
const ipv6InputButtonElement: Ref<HTMLInputElement | null> = ref(null)
const ipAddressFamilySelectElement: Ref<HTMLSelectElement | null> = ref(null)
const ipAddressFamilyInputElement: Ref<HTMLInputElement | null> = ref(null)
const tagAgentInputSelectElement: Ref<HTMLSelectElement | null> = ref(null)
const tagAgentInputButtonElement: Ref<HTMLInputElement | null> = ref(null)
const tagAgentDefaultElement: Ref<HTMLDivElement | null> = ref(null)
const cmkConnectionModeSelectElement: Ref<HTMLSelectElement | null> = ref(null)

onMounted(() => {
  formElement.value = getElementBySelector(`form[id="form_${props.form_keys.form}"]`)
  hostnameInputElement.value = document.querySelector(
    `input.text[name="${props.form_keys.host_name}"]`
  )
  // Create a fake input element for hostname if it doesn't exist
  // to also be able to add this component for editing hosts
  if (!hostnameInputElement.value) {
    hostnameInputElement.value = document.createElement('input')
    hostnameInputElement.value.style.display = 'none'
    hostnameInputElement.value.name = props.form_keys.host_name
    hostnameInputElement.value.value = props.host_name
  }
  ipv4InputElement.value = getElementBySelector(
    `input.text[name="${props.form_keys.ipv4_address}"]`
  )
  ipv6InputElement.value = getElementBySelector(
    `input.text[name="${props.form_keys.ipv6_address}"]`
  )
  siteSelectElement.value = getElementBySelector(`select[name="${props.form_keys.site}"]`)
  ipAddressFamilySelectElement.value = getElementBySelector(
    `select[name="${props.form_keys.ip_address_family}"]`
  )
  ipAddressFamilyInputElement.value = getElementBySelector(
    `input[id="${props.form_keys.cb_change}_${props.form_keys.ip_address_family}"]`
  )
  ipv4InputButtonElement.value = getElementBySelector(
    `input[id="${props.form_keys.cb_change}_${props.form_keys.ipv4_address}"]`
  )
  ipv6InputButtonElement.value = getElementBySelector(
    `input[id="${props.form_keys.cb_change}_${props.form_keys.ipv6_address}"]`
  )
  tagAgentInputSelectElement.value = getElementBySelector(
    `select[name="${props.form_keys.tag_agent}"]`
  )
  tagAgentInputButtonElement.value = getElementBySelector(
    `input[id="${props.form_keys.cb_change}_${props.form_keys.tag_agent}"]`
  )
  tagAgentDefaultElement.value = getElementBySelector(
    `div[id="attr_default_${props.form_keys.tag_agent}"]`
  )
  cmkConnectionModeSelectElement.value = document.querySelector(
    `select[name="${props.form_keys.cmk_agent_connection}"]`
  )
})

function getElementBySelector<T>(selector: string): T {
  const element = document.querySelector(selector) as T | null
  if (!element) {
    throw new Error(`Element with selector "${selector}" not found`)
  }
  return element
}
</script>

<template>
  <PingHost
    v-if="
      formElement &&
      hostnameInputElement &&
      siteSelectElement &&
      ipv4InputElement &&
      ipv6InputElement &&
      ipAddressFamilySelectElement &&
      ipAddressFamilyInputElement &&
      ipv4InputButtonElement &&
      ipv6InputButtonElement
    "
    :i18n="i18n_ping_host"
    :form-element="formElement"
    :ip-address-family-select-element="ipAddressFamilySelectElement"
    :ip-address-family-input-element="ipAddressFamilyInputElement"
    :hostname-input-element="hostnameInputElement"
    :ipv4-input-element="ipv4InputElement"
    :ipv4-input-button-element="ipv4InputButtonElement"
    :ipv6-input-element="ipv6InputElement"
    :ipv6-input-button-element="ipv6InputButtonElement"
    :site-select-element="siteSelectElement"
    :sites="sites"
  ></PingHost>
  <AgentConnectionTest
    v-if="
      formElement &&
      hostnameInputElement &&
      siteSelectElement &&
      ipv4InputElement &&
      ipv6InputElement &&
      ipAddressFamilySelectElement &&
      tagAgentInputSelectElement &&
      tagAgentInputButtonElement &&
      tagAgentDefaultElement
    "
    :form-element="formElement"
    :change-tag-agent="tagAgentInputButtonElement"
    :tag-agent="tagAgentInputSelectElement"
    :tag-agent-default="tagAgentDefaultElement"
    :hostname-input-element="hostnameInputElement"
    :ipv4-input-element="ipv4InputElement"
    :ipv6-input-element="ipv6InputElement"
    :site-select-element="siteSelectElement"
    :ip-address-family-select-element="ipAddressFamilySelectElement"
    :cmk-agent-connection-mode-select-element="cmkConnectionModeSelectElement"
    :sites="sites"
    :agent-connection-modes="agent_connection_modes"
    :all_agents_url="all_agents_url"
  ></AgentConnectionTest>
</template>

<style scoped></style>
