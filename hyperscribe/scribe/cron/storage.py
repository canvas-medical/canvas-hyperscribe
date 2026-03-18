from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.handlers.cron_task import CronTask
from canvas_sdk.v1.data import Note

_CACHE_KEY_PREFIX = "scribe_transcript:"
_SUMMARY_CACHE_KEY_PREFIX = "scribe_summary:"


class StorageCronTask(CronTask):
    """A cron task that runs every monday at 3am that checks and extends storage."""

    SCHEDULE = "0 3 * * 1"

    def execute(self) -> list[Effect]:
        cache = get_cache()

        for note_id in Note.objects.all().values_list("id", flat=True):
            transcript_cache_key = f"{_CACHE_KEY_PREFIX}{note_id}"
            summary_cache_key = f"{_SUMMARY_CACHE_KEY_PREFIX}{note_id}"

            if transcript_cache_key in cache:
                value = cache.get(transcript_cache_key)
                cache.set(transcript_cache_key, value)

            if summary_cache_key in cache:
                value = cache.get(summary_cache_key)
                cache.set(summary_cache_key, value)

        return []
