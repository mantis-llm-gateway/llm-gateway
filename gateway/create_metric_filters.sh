#!/usr/bin/env bash
set -euo pipefail

LOG_GROUP="/ecs/gw/gateway"
REGION="us-east-1"
PROFILE="gw"

put_filter() {
  local name="$1"
  local pattern="$2"
  local transforms="$3"
  echo "  → $name"
  aws logs put-metric-filter \
    --log-group-name "$LOG_GROUP" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --filter-name "$name" \
    --filter-pattern "$pattern" \
    --metric-transformations "$transforms"
}

echo "Creating 22 metric filters on $LOG_GROUP..."

# Non-streamed success
put_filter "non-streamed-success-count" \
  '{ $.message = "successful non-streamed LLM response" }' \
  '[{"metricName":"NonStreamedSuccessCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "non-streamed-latency" \
  '{ $.message = "successful non-streamed LLM response" }' \
  '[{"metricName":"NonStreamedLatencyMs","metricNamespace":"LLMGateway","metricValue":"$.latency_ms","unit":"Milliseconds"}]'

put_filter "non-streamed-input-tokens" \
  '{ $.message = "successful non-streamed LLM response" }' \
  '[{"metricName":"NonStreamedInputTokens","metricNamespace":"LLMGateway","metricValue":"$.input_tokens","unit":"Count"}]'

put_filter "non-streamed-output-tokens" \
  '{ $.message = "successful non-streamed LLM response" }' \
  '[{"metricName":"NonStreamedOutputTokens","metricNamespace":"LLMGateway","metricValue":"$.output_tokens","unit":"Count"}]'

# Stream completed
put_filter "stream-completed-count" \
  '{ $.message = "stream completed" }' \
  '[{"metricName":"StreamCompletedCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "stream-latency" \
  '{ $.message = "stream completed" }' \
  '[{"metricName":"StreamLatencyMs","metricNamespace":"LLMGateway","metricValue":"$.latency_ms","unit":"Milliseconds"}]'

put_filter "stream-input-tokens" \
  '{ $.message = "stream completed" }' \
  '[{"metricName":"StreamInputTokens","metricNamespace":"LLMGateway","metricValue":"$.input_tokens","unit":"Count"}]'

put_filter "stream-output-tokens" \
  '{ $.message = "stream completed" }' \
  '[{"metricName":"StreamOutputTokens","metricNamespace":"LLMGateway","metricValue":"$.output_tokens","unit":"Count"}]'

# Cache hit
put_filter "cache-hit-count" \
  '{ $.message = "cache hit" }' \
  '[{"metricName":"CacheHitCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "cache-hit-latency" \
  '{ $.message = "cache hit" }' \
  '[{"metricName":"CacheHitLatencyMs","metricNamespace":"LLMGateway","metricValue":"$.latency_ms","unit":"Milliseconds"}]'

# Cache hit by type
put_filter "exact-cache-hit" \
  '{ $.message = "exact cache hit" }' \
  '[{"metricName":"ExactCacheHitCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "semantic-cache-hit" \
  '{ $.message = "semantic cache hit" }' \
  '[{"metricName":"SemanticCacheHitCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

# Request outcomes
put_filter "abort" \
  '{ $.message = "abort" }' \
  '[{"metricName":"AbortCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "targets-exhausted" \
  '{ $.message = "targets exhausted" }' \
  '[{"metricName":"TargetsExhaustedCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "guardrail-intervened" \
  '{ $.message = "guardrail intervened" }' \
  '[{"metricName":"GuardrailIntervenedCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

# Routing events
put_filter "failover" \
  '{ $.message = "failover" }' \
  '[{"metricName":"FailoverCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "cooldown" \
  '{ $.message = "target put into cooldown" }' \
  '[{"metricName":"CooldownCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "retry" \
  '{ $.message = "retry target" }' \
  '[{"metricName":"RetryCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

# Bedrock errors
put_filter "bedrock-error" \
  '{ $.message = "bedrock call failed" }' \
  '[{"metricName":"BedrockErrorCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "mid-stream-error" \
  '{ $.message = "mid-stream error" }' \
  '[{"metricName":"MidStreamErrorCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

# Infrastructure errors
put_filter "redis-cache-error" \
  '{ ($.message = "redis exact cache get failed") || ($.message = "redis exact cache set failed") || ($.message = "redis semantic cache lookup failed") || ($.message = "redis semantic cache store failed") }' \
  '[{"metricName":"RedisCacheErrorCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

put_filter "embedding-failure" \
  '{ $.message = "bedrock embedding call failed" }' \
  '[{"metricName":"EmbeddingFailureCount","metricNamespace":"LLMGateway","metricValue":"1","unit":"Count"}]'

echo "Done. 22 filters created."
