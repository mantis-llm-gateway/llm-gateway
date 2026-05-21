# TODO: Move policy values to config module (when that is ready for use)

# TODO: Use a more precisely chosen value.
# Lower temp warrants a higher cache hit rate because user wants more deterministic results
CACHE_TEMP_THRESHOLD = 0.3
# TODO: Set to 3 now to reduce false positives on long convos
CACHE_CONVERSATION_HISTORY_THRESHOLD = 3


# TODO: (future bypass conditions) handle streaming and opt-out headers
def should_skip_cache(temperature: float | None = None, total_messages: int | None = None) -> bool:
    if (temperature is not None and temperature > CACHE_TEMP_THRESHOLD) or (
        total_messages is not None and total_messages > CACHE_CONVERSATION_HISTORY_THRESHOLD
    ):
        return True
    return False


# TODO: confirm whether providers ever return 2xx other than 200 for valid responses
def is_cacheable_response(status_code: int) -> bool:
    return status_code == 200
