import assert from 'node:assert/strict'
import { test } from 'node:test'
import { toConfig, toFormValues } from '../src/formValues.ts'
import type { Config, FormValues } from '../src/types.ts'

const config: Config = {
  aliases: {
    primary: { provider: 'bedrock', model: 'model-a' },
    fallback: { provider: 'bedrock', model: 'model-b' },
  },
  routing_rules: [
    {
      id: 'rule-1',
      name: 'Paid tier',
      match: { name: 'user-tier', value: 'paid' },
      targets: [{ alias: 'primary', weight: 3 }],
    },
  ],
  target_retries: 2,
  fallbacks: ['fallback'],
  initial_response_timeout: 30,
  stream_idle_timeout: 1,
  default_model: 'primary',
  cooldown_ttl: 60,
  prompt_cache: {
    ttl_seconds: 3600,
    temperature_threshold: 0.3,
    semantic: {
      similarity_threshold: 0.8,
      top_k: 3,
      conversation_size_threshold: 2,
    },
  },
}

test('converts API config records into editable form rows', () => {
  assert.deepEqual(toFormValues(config), {
    ...config,
    aliases: [
      { name: 'primary', provider: 'bedrock', model: 'model-a' },
      { name: 'fallback', provider: 'bedrock', model: 'model-b' },
    ],
    fallbacks: [{ value: 'fallback' }],
  })
})

test('round trips a config without changing its API shape', () => {
  assert.deepEqual(toConfig(toFormValues(config)), config)
})

test('coerces numeric form values before sending config to the API', () => {
  const values = {
    ...toFormValues(config),
    target_retries: '4',
    initial_response_timeout: '45',
    stream_idle_timeout: '3',
    cooldown_ttl: '90',
    routing_rules: [
      {
        ...config.routing_rules[0],
        targets: [{ alias: 'primary', weight: '6' }],
      },
    ],
    prompt_cache: {
      ttl_seconds: '7200',
      temperature_threshold: '0.5',
      semantic: {
        similarity_threshold: '0.9',
        top_k: '5',
        conversation_size_threshold: '4',
      },
    },
  } as unknown as FormValues

  assert.deepEqual(toConfig(values), {
    ...config,
    target_retries: 4,
    initial_response_timeout: 45,
    stream_idle_timeout: 3,
    cooldown_ttl: 90,
    routing_rules: [
      {
        ...config.routing_rules[0],
        targets: [{ alias: 'primary', weight: 6 }],
      },
    ],
    prompt_cache: {
      ttl_seconds: 7200,
      temperature_threshold: 0.5,
      semantic: {
        similarity_threshold: 0.9,
        top_k: 5,
        conversation_size_threshold: 4,
      },
    },
  })
})

test('preserves a disabled semantic cache', () => {
  const configWithoutSemanticCache: Config = {
    ...config,
    prompt_cache: {
      ...config.prompt_cache,
      semantic: null,
    },
  }

  assert.deepEqual(toConfig(toFormValues(configWithoutSemanticCache)), configWithoutSemanticCache)
})
