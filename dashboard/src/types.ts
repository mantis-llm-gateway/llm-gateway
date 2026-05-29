export interface AliasConfig {
  provider: string;
  model: string;
}

export interface RuleMatchConfig {
  name: string;
  value: string;
}

export interface TargetConfig {
  alias: string;
  weight: number;
}

export interface RoutingRuleConfig {
  id?: string;
  name: string;
  match: RuleMatchConfig;
  targets: TargetConfig[];
}

export interface SemanticCacheConfig {
  similarity_threshold: number;
  top_k: number;
  conversation_size_threshold: number;
}

export interface PromptCacheConfig {
  ttl_seconds: number;
  temperature_threshold: number;
  semantic: SemanticCacheConfig | null;
}

export interface Config {
  aliases: Record<string, AliasConfig>;
  routing_rules: RoutingRuleConfig[];
  target_retries: number;
  fallbacks: string[];
  initial_response_timeout: number;
  default_model: string;
  cooldown_ttl: number;
  prompt_cache: PromptCacheConfig;
}

// react-hook-form works with arrays, not dicts.
// We flatten aliases into a list for the form and convert back on submit.
export interface AliasRow {
  name: string;
  provider: string;
  model: string;
}

export interface FormValues {
  aliases: AliasRow[];
  routing_rules: RoutingRuleConfig[];
  target_retries: number;
  fallbacks: { value: string }[];
  initial_response_timeout: number;
  default_model: string;
  cooldown_ttl: number;
  prompt_cache: PromptCacheConfig;
}
