from gateway.engine.executor import _sanitize_assessment, _sanitize_trace


class TestSanitizeAssessment:
    def test_strips_match_from_pii_entities(self):
        assessment = {
            "sensitiveInformationPolicy": {
                "piiEntities": [
                    {
                        "action": "BLOCKED",
                        "detected": True,
                        "match": "john@example.com",
                        "type": "EMAIL",
                    }
                ],
                "regexes": [],
            }
        }
        result = _sanitize_assessment(assessment)
        assert result["sensitiveInformationPolicy"]["piiEntities"] == [
            {"action": "BLOCKED", "detected": True, "type": "EMAIL"}
        ]

    def test_strips_match_from_regexes(self):
        assessment = {
            "sensitiveInformationPolicy": {
                "piiEntities": [],
                "regexes": [
                    {
                        "action": "BLOCKED",
                        "detected": True,
                        "match": "1234-5678",
                        "name": "card-regex",
                        "regex": "\\d{4}-\\d{4}",
                    }
                ],
            }
        }
        result = _sanitize_assessment(assessment)
        assert result["sensitiveInformationPolicy"]["regexes"] == [
            {"action": "BLOCKED", "detected": True, "name": "card-regex", "regex": "\\d{4}-\\d{4}"}
        ]

    def test_strips_match_from_custom_words(self):
        assessment = {
            "wordPolicy": {
                "customWords": [{"action": "BLOCKED", "detected": True, "match": "badword"}],
                "managedWordLists": [],
            }
        }
        result = _sanitize_assessment(assessment)
        assert result["wordPolicy"]["customWords"] == [{"action": "BLOCKED", "detected": True}]

    def test_strips_match_from_managed_word_lists(self):
        assessment = {
            "wordPolicy": {
                "customWords": [],
                "managedWordLists": [
                    {"action": "BLOCKED", "detected": True, "match": "slur", "type": "PROFANITY"}
                ],
            }
        }
        result = _sanitize_assessment(assessment)
        assert result["wordPolicy"]["managedWordLists"] == [
            {"action": "BLOCKED", "detected": True, "type": "PROFANITY"}
        ]

    def test_passes_through_topic_policy(self):
        assessment = {
            "topicPolicy": {
                "topics": [
                    {"action": "BLOCKED", "detected": True, "name": "Violence", "type": "DENY"}
                ]
            }
        }
        result = _sanitize_assessment(assessment)
        assert result["topicPolicy"] == assessment["topicPolicy"]

    def test_passes_through_content_policy(self):
        assessment = {
            "contentPolicy": {
                "filters": [
                    {
                        "action": "BLOCKED",
                        "confidence": "HIGH",
                        "detected": True,
                        "filterStrength": "HIGH",
                        "type": "HATE",
                    }
                ]
            }
        }
        result = _sanitize_assessment(assessment)
        assert result["contentPolicy"] == assessment["contentPolicy"]

    def test_handles_missing_sensitive_information_policy(self):
        assessment = {"topicPolicy": {"topics": []}}
        result = _sanitize_assessment(assessment)
        assert "sensitiveInformationPolicy" not in result

    def test_handles_missing_word_policy(self):
        assessment = {"topicPolicy": {"topics": []}}
        result = _sanitize_assessment(assessment)
        assert "wordPolicy" not in result

    def test_handles_empty_pii_entities_and_regexes(self):
        assessment = {"sensitiveInformationPolicy": {"piiEntities": [], "regexes": []}}
        result = _sanitize_assessment(assessment)
        assert result["sensitiveInformationPolicy"] == {"piiEntities": [], "regexes": []}

    def test_does_not_mutate_input(self):
        assessment = {
            "sensitiveInformationPolicy": {
                "piiEntities": [
                    {"action": "BLOCKED", "detected": True, "match": "secret", "type": "EMAIL"}
                ],
                "regexes": [],
            }
        }
        _sanitize_assessment(assessment)
        assert assessment["sensitiveInformationPolicy"]["piiEntities"][0]["match"] == "secret"


class TestSanitizeTrace:
    def test_removes_model_output(self):
        trace = {"modelOutput": ["some model text"], "actionReason": "blocked"}
        result = _sanitize_trace(trace)
        assert "modelOutput" not in result

    def test_preserves_other_top_level_fields(self):
        trace = {"modelOutput": ["text"], "actionReason": "blocked"}
        result = _sanitize_trace(trace)
        assert result["actionReason"] == "blocked"

    def test_handles_missing_model_output(self):
        trace = {"actionReason": "blocked"}
        result = _sanitize_trace(trace)
        assert "modelOutput" not in result
        assert result["actionReason"] == "blocked"

    def test_sanitizes_input_assessment(self):
        trace = {
            "inputAssessment": {
                "guardrail-1": {
                    "sensitiveInformationPolicy": {
                        "piiEntities": [
                            {
                                "action": "BLOCKED",
                                "detected": True,
                                "match": "john@example.com",
                                "type": "EMAIL",
                            }
                        ],
                        "regexes": [],
                    }
                }
            }
        }
        result = _sanitize_trace(trace)
        entity = result["inputAssessment"]["guardrail-1"]["sensitiveInformationPolicy"][
            "piiEntities"
        ][0]
        assert "match" not in entity
        assert entity["type"] == "EMAIL"

    def test_sanitizes_all_guardrail_ids_in_input_assessment(self):
        trace = {
            "inputAssessment": {
                "guardrail-1": {
                    "wordPolicy": {
                        "customWords": [
                            {"action": "BLOCKED", "detected": True, "match": "badword"}
                        ],
                        "managedWordLists": [],
                    }
                },
                "guardrail-2": {
                    "wordPolicy": {
                        "customWords": [
                            {"action": "BLOCKED", "detected": True, "match": "otherword"}
                        ],
                        "managedWordLists": [],
                    }
                },
            }
        }
        result = _sanitize_trace(trace)
        assert (
            "match" not in result["inputAssessment"]["guardrail-1"]["wordPolicy"]["customWords"][0]
        )
        assert (
            "match" not in result["inputAssessment"]["guardrail-2"]["wordPolicy"]["customWords"][0]
        )

    def test_sanitizes_output_assessments(self):
        trace = {
            "outputAssessments": {
                "guardrail-1": [
                    {
                        "sensitiveInformationPolicy": {
                            "piiEntities": [
                                {
                                    "action": "BLOCKED",
                                    "detected": True,
                                    "match": "5555-4444-3333-2222",
                                    "type": "CREDIT_DEBIT_CARD",
                                }
                            ],
                            "regexes": [],
                        }
                    }
                ]
            }
        }
        result = _sanitize_trace(trace)
        entity = result["outputAssessments"]["guardrail-1"][0]["sensitiveInformationPolicy"][
            "piiEntities"
        ][0]
        assert "match" not in entity
        assert entity["type"] == "CREDIT_DEBIT_CARD"

    def test_sanitizes_multiple_assessments_per_guardrail_in_output_assessments(self):
        trace = {
            "outputAssessments": {
                "guardrail-1": [
                    {
                        "wordPolicy": {
                            "customWords": [
                                {"action": "BLOCKED", "detected": True, "match": "word1"}
                            ],
                            "managedWordLists": [],
                        }
                    },
                    {
                        "wordPolicy": {
                            "customWords": [
                                {"action": "BLOCKED", "detected": True, "match": "word2"}
                            ],
                            "managedWordLists": [],
                        }
                    },
                ]
            }
        }
        result = _sanitize_trace(trace)
        for assessment in result["outputAssessments"]["guardrail-1"]:
            assert "match" not in assessment["wordPolicy"]["customWords"][0]

    def test_handles_missing_input_assessment(self):
        trace = {"actionReason": "blocked"}
        result = _sanitize_trace(trace)
        assert "inputAssessment" not in result

    def test_handles_missing_output_assessments(self):
        trace = {"actionReason": "blocked"}
        result = _sanitize_trace(trace)
        assert "outputAssessments" not in result

    def test_does_not_mutate_input(self):
        trace = {
            "modelOutput": ["text"],
            "inputAssessment": {
                "guardrail-1": {
                    "sensitiveInformationPolicy": {
                        "piiEntities": [
                            {
                                "action": "BLOCKED",
                                "detected": True,
                                "match": "secret",
                                "type": "EMAIL",
                            }
                        ],
                        "regexes": [],
                    }
                }
            },
        }
        _sanitize_trace(trace)
        assert trace["modelOutput"] == ["text"]
        assert (
            trace["inputAssessment"]["guardrail-1"]["sensitiveInformationPolicy"]["piiEntities"][0][
                "match"
            ]
            == "secret"
        )
