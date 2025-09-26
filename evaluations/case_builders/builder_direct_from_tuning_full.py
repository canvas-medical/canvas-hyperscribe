import json
from argparse import ArgumentParser
from pathlib import Path
from uuid import uuid4

from evaluations.case_builders.builder_direct_from_tuning import BuilderDirectFromTuning
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog


class BuilderDirectFromTuningFull(BuilderDirectFromTuning):
    @classmethod
    def _parameters(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--direct-full", action="store_true")

    def _run(self) -> None:
        print(f"collect webm, collate to mp3...")
        mp3_file = self.collated_webm_to_mp3()
        print(f"split mp3 into chunks...")
        mp3_files = self.split_audio(mp3_file)

        with (mp3_file.parent / "limited_chart.json").open("r") as f:
            cache = LimitedCache.load_from_json(json.load(f))

        chat_transcript = AudioInterpreter(self.settings, self.s3_logs_credentials, cache, self.identification)
        print(f"create transcripts...")
        transcript_files = self.create_transcripts(mp3_files, chat_transcript)
        compacted_transcript_files = self.compact_transcripts(transcript_files)
        print(f"de-identification transcripts...")
        anonymization = self.anonymize_transcripts(compacted_transcript_files)
        print("de-identification limited cache...")
        cache = self.anonymize_limited_cache(anonymization.substitutions, cache)
        print(f"case name and summary...")
        case_summary = self.exchange_summary(anonymization.files)
        print(f"build case {case_summary.title}:")
        case_exchange = [
            line for file in anonymization.files for line in CaseExchange.load_from_json(json.loads(file.read_text()))
        ]
        self.generate_case(cache, case_summary, case_exchange)

    def exchange_summary(self, transcript_files: list[Path]) -> CaseExchangeSummary:
        result: list[CaseExchangeSummary] = []
        memory_log = MemoryLog.instance(self.identification, "detect_summary", self.s3_logs_credentials)
        schema_summary = self.schema_summary()

        summary_detection = transcript_files[0].parent / f"summary_detection.json"
        if summary_detection.exists() and not self.force_refresh:
            with summary_detection.open("r") as f:
                result = CaseExchangeSummary.load_from_json(json.load(f))

        str_uuid = str(uuid4())
        for fragment, transcript in enumerate(transcript_files, start=1):
            if fragment <= len(result):
                continue

            chatter = Helper.chatter(self.settings, memory_log)
            chatter.set_system_prompt(
                [
                    "The conversation is in the medical context, and related to a visit of a patient with a "
                    "healthcare provider.",
                    "",
                    "Your task is to give meaningful title and summary to the *whole* discussion.",
                    "",
                    "But because the conversation is too long, it has been divided into sequential fragment of "
                    "several seconds each, "
                    "so the user will provide you the title and summary defined so far when giving you a new fragment.",
                    "",
                    "The title should be as concise as possible, composed of about 25 to 40 characters.",
                    "",
                    "Format your response following the JSON Schema:",
                    "```json",
                    json.dumps(schema_summary, indent=1),
                    "```",
                    "",
                ],
            )
            if fragment > 1:
                previous = result[fragment - 2]
                chatter.set_user_prompt(["Here how to describe the discussion so far:", previous.summary, ""])
            with transcript.open("r") as f:
                chatter.set_user_prompt(
                    [
                        f"The fragment of the discussion is:",
                        "```json",
                        f.read(),
                        "```",
                        "",
                        "Follow rigorously the instructions and provide the requested information using "
                        "the mentioned JSON Schema within a Markdown code block:",
                        "```json",
                        "YOUR JSON OUTPUT HERE",
                        "```",
                    ],
                )
                response = chatter.chat([schema_summary])

                last = CaseExchangeSummary.load_from_json(response.content[0])[-1]
                result.append(
                    CaseExchangeSummary(
                        title=f"{last.title}_{str_uuid[:10]}".lower().replace(" ", "_"),
                        summary=last.summary,
                    ),
                )
                with summary_detection.open("w") as f2:
                    json.dump([summary.to_json() for summary in result], f2, indent=2)

        return result[-1]
