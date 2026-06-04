import type { Config, FormValues } from './types'

export function toFormValues(config: Config): FormValues {
  return {
    aliases: Object.entries(config.aliases).map(([name, { provider, model }]) => ({
      name,
      provider,
      model,
    })),
    routing_rules: config.routing_rules,
    target_retries: config.target_retries,
    fallbacks: config.fallbacks.map(value => ({ value })),
    initial_response_timeout: config.initial_response_timeout,
    stream_idle_timeout: config.stream_idle_timeout,
    default_model: config.default_model,
    cooldown_ttl: config.cooldown_ttl,
    prompt_cache: config.prompt_cache,
  }
}

export function toConfig(values: FormValues): Config {
  return {
    aliases: Object.fromEntries(
      values.aliases.map(({ name, provider, model }) => [name, { provider, model }])
    ),
    routing_rules: values.routing_rules.map(rule => ({
      ...rule,
      targets: rule.targets.map(target => ({ ...target, weight: Number(target.weight) })),
    })),
    target_retries: Number(values.target_retries),
    fallbacks: values.fallbacks.map(fallback => fallback.value),
    initial_response_timeout: Number(values.initial_response_timeout),
    stream_idle_timeout: Number(values.stream_idle_timeout),
    default_model: values.default_model,
    cooldown_ttl: Number(values.cooldown_ttl),
    prompt_cache: {
      ttl_seconds: Number(values.prompt_cache.ttl_seconds),
      temperature_threshold: Number(values.prompt_cache.temperature_threshold),
      semantic: values.prompt_cache.semantic
        ? {
            similarity_threshold: Number(values.prompt_cache.semantic.similarity_threshold),
            top_k: Number(values.prompt_cache.semantic.top_k),
            conversation_size_threshold: Number(
              values.prompt_cache.semantic.conversation_size_threshold
            ),
          }
        : null,
    },
  }
}
