# TODO: Use a more precisely chosen value.
# Lowerower temp warrants a higher cache hit rate because user wants more deterministic results
CACHE_TEMP_THRESHOLD = 0.3


# TODO: (future bypass conditions) handle streaming and opt-out headers
def should_skip_cache(temperature: float | None) -> bool:
    return temperature > CACHE_TEMP_THRESHOLD if temperature is not None else False


# TODO: confirm whether providers ever return 2xx other than 200 for valid responses
def is_cacheable_response(status_code: int) -> bool:
    return status_code == 200
