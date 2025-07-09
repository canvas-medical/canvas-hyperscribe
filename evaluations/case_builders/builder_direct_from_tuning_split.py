import json
from argparse import ArgumentParser
from itertools import groupby
from pathlib import Path
from uuid import uuid4

from evaluations.case_builders.builder_direct_from_tuning import BuilderDirectFromTuning
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from evaluations.structures.topical_exchange import TopicalExchange
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog


class BuilderDirectFromTuningSplit(BuilderDirectFromTuning):
    MAX_WORDS_PER_COMPACTED_TRANSCRIPT = 1000

    @classmethod
    def _parameters(cls, parser: ArgumentParser) -> None:
        parser.add_argument("--direct-split", action="store_true")

    @classmethod
    def compact_transcripts(cls, transcript_files: list[Path]) -> list[Path]:
        lines: list[CaseExchange] = []
        folder = transcript_files[0].parent
        result: list[Path] = [(folder / f"transcript_compacted_000.json")]
        words = 0
        for chunk, transcript in enumerate(transcript_files, start=1):
            with transcript.open("r") as f:
                for line in CaseExchange.load_from_json_default(json.load(f), chunk):
                    current = len(line.text.split())
                    if words + current < cls.MAX_WORDS_PER_COMPACTED_TRANSCRIPT:
                        words += current
                        lines.append(line)
                    else:
                        result.append(folder / f"transcript_compacted_{len(result):03d}.json")
                        words = current
                        lines = [line]
                    with result[-1].open("w") as f2:
                        json.dump([line.to_json() for line in lines], f2, indent=2)
        return result

    @classmethod
    def schema_topical_exchanges(cls) -> dict:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "text": {"type": "string", "minLength": 1},
                    "chunk": {"type": "integer"},
                    "topic": {"type": "integer"},
                },
                "required": ["speaker", "text", "chunk", "topic"],
                "additionalProperties": False,
            },
        }

    @classmethod
    def schema_summary(cls) -> dict:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9 ]+$",
                        "description": "a concise title composed with 25 to 40 characters",
                    },
                    "summary": {
                        "type": "string",
                        "description": "a summary of the exchange",
                    },
                },
                "required": ["title", "summary"],
                "additionalProperties": False,
            },
        }

    def _run(self) -> None:
        print(f"collect webm, collate to mp3...")
        mp3_file = self.collated_webm_to_mp3()
        print(f"split mp3 into chunks...")
        mp3_files = self.split_audio(mp3_file)

        with (mp3_file.parent / "limited_chart.json").open("r") as f:
            cache = LimitedCache.load_from_json(json.load(f))

        chat_transcript = AudioInterpreter(self.settings, self.s3_credentials, cache, self.identification)
        print(f"create transcripts...")
        transcript_files = self.create_transcripts(mp3_files, chat_transcript)
        # while it is important to keep the transcript generation with the same duration as the actual code,
        # it is preferable to give wider context to the LLM to identify the different topics
        compacted_transcript_files = self.compact_transcripts(transcript_files)
        print(f"de-identification transcripts...")
        anonymized_transcript_files = self.anonymize_transcripts(compacted_transcript_files)
        print(f"detect topical exchanges...")
        topic_exchanges = self.detect_topical_exchanges(anonymized_transcript_files)

        key2instruction = ImplementedCommands.schema_key2instruction()
        for topic, exchange in groupby(topic_exchanges, key=lambda x: x.topic):
            # # TODO debug
            # if topic > 2:
            #     break
            topic_exchange = [line for line in exchange]
            topic_summary = self.topical_exchange_summary(topic_exchange, mp3_file.parent)
            print(f"build case for topic {topic_summary.title}:")
            case_exchange = TopicalExchange.case_exchange_from(topic_exchange)
            instructions = self.generate_case(cache, topic_summary, case_exchange)
            cache.add_instructions_as_staged_commands(instructions, key2instruction)

    def topical_exchange_summary(
            self,
            topic_exchanges: list[TopicalExchange],
            temporary_folder: Path,
    ) -> CaseExchangeSummary:

        topic_summary = temporary_folder / f"topic_summary_{topic_exchanges[0].topic:03d}.json"
        if topic_summary.exists() and not self.force_refresh:
            with topic_summary.open("r") as f:
                return CaseExchangeSummary.load_from_json(json.load(f))[0]

        memory_log = MemoryLog.instance(self.identification, "topical_exchange_naming", self.s3_credentials)
        chatter = Helper.chatter(self.settings, memory_log)
        chatter.set_system_prompt([
            "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
            "",
            "Your task is to give a meaningful title to a provided sub set of the discussion, previously identified as a coherent topical exchange.",
            "",
            "The title should be as concise as possible, composed of about 25 to 40 characters.",
            "",
            "Format your response following the JSON Schema:",
            "```json",
            json.dumps(self.schema_summary(), indent=1),
            "```",
            "",
        ])
        result = CaseExchangeSummary(title=str(uuid4()), summary="")
        chatter.set_user_prompt([
            "Coherent topical exchange:",
            "```json",
            json.dumps([line.to_json() for line in topic_exchanges], indent=1),
            "```",
            "",
            "",
            "Follow rigorously the instructions and provide the requested information using "
            "the mentioned JSON Schema within a Markdown code block:",
            "```json",
            "YOUR JSON OUTPUT HERE",
            "```",
        ])
        response = chatter.chat([self.schema_summary()])
        if not response.has_error and (summaries := CaseExchangeSummary.load_from_json(response.content[0])):
            result = CaseExchangeSummary(
                title=f"{summaries[0].title}_{result.title[:10]}".lower().replace(" ", "_"),
                summary=summaries[0].summary,
            )
        with topic_summary.open("w") as f:
            json.dump([result.to_json()], f, indent=2)
        return result

    def detect_topical_exchanges(self, transcript_files: list[Path]) -> list[TopicalExchange]:
        result: list[TopicalExchange] = []
        memory_log = MemoryLog.instance(self.identification, "detect_topical_exchanges", self.s3_credentials)
        schema_topical_exchanges = self.schema_topical_exchanges()

        for fragment, transcript in enumerate(transcript_files, start=1):
            topic_detection = transcript.parent / f"topic_detection_{fragment:03d}.json"
            if topic_detection.exists() and not self.force_refresh:
                with topic_detection.open("r") as f:
                    result.extend(TopicalExchange.load_from_json(json.load(f)))
                continue

            chatter = Helper.chatter(self.settings, memory_log)
            chatter.set_system_prompt([
                "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
                "",
                "The conversation is divided into sequential fragment of several seconds each.",
                "",
                "Your task is to segment the conversation into coherent sets of topical medical exchanges.",
                "This means:",
                "* Each set should correspond to a distinct medical topic.",
                "* Non-medical content (e.g., small talk, greetings) should be included in the current medical topic set but should not initiate a new topic on its own.",
                "",
                "For each new fragment, you will be given:",
                "* The transcript of the current fragment.",
                "* The last previously identified topic exchange.",
                "",
                "",
                "Your job is to:",
                "* Determine whether the current fragment introduces a new medical topic.",
                "* If it does, increment the 'topic' field by one (1) for the exchanges starting from this new topic.",
                "* Topic shifts may occur anywhere within the fragment, not necessarily at the beginning.",
                "",
                "Be precise and consistent. Only mark a new topic when the medical focus clearly changes.",
                "",
                "Format your response following the JSON Schema:",
                "```json",
                json.dumps(schema_topical_exchanges, indent=1),
                "```",
                "",
            ])
            if result:
                topic_index = result[-1].topic
                topic_exchange = [topic for topic in result if topic.topic == topic_index]

                chatter.set_user_prompt([
                    f"Here is the current set of exchanges for the topic #{topic_index:02d}:",
                    "```json",
                    json.dumps([topic.to_json() for topic in topic_exchange], indent=1),
                    "```",
                    "",
                    "This is just for the context, so do not repeat it in your answer.",
                ])
            with transcript.open("r") as f:
                chatter.set_user_prompt([
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
                ])
                response = chatter.chat([schema_topical_exchanges])
                topical_exchanges = TopicalExchange.load_from_json(response.content[0])
                result.extend(topical_exchanges)
                with topic_detection.open("w") as f2:
                    json.dump([line.to_json() for line in topical_exchanges], f2, indent=2)

        return result
