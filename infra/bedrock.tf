resource "aws_bedrock_guardrail" "gw" {
  name        = "gw-${var.namespace}-guardrails"
  description = "LLM gateway content + PII + prompt injection guardrail"

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "financial-advice"
      definition = "Specific recommendations for buying, selling, or holding financial instruments. Does not include general financial education or definitions of financial concepts."
      type       = "DENY"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "CREDIT_DEBIT_CARD_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "US_SOCIAL_SECURITY_NUMBER"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "UK_UNIQUE_TAXPAYER_REFERENCE_NUMBER"
      action = "ANONYMIZE"
    }
  }

  blocked_input_messaging   = "This request was blocked by content policy"
  blocked_outputs_messaging = "This request was blocked by content policy"
}

resource "aws_bedrock_guardrail_version" "gw" {
  guardrail_arn = aws_bedrock_guardrail.gw.guardrail_arn
  description   = "v1 - Initial version"
}
