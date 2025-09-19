from argparse import ArgumentParser
from argparse import Namespace

from evaluations.datastores.datastore_case import DatastoreCase
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class CaseRunner:
    @classmethod
    def parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Run the case based on the local settings")
        parser.add_argument("--case", type=str, required=True, help="The case to run")
        parser.add_argument(
            "--cycles",
            type=int,
            default=0,
            help="Split the transcript in as many cycles, use the stored cycles if not provided.",
        )
        parser.add_argument(
            "--chunk_duration_seconds",
            type=int,
            default=0,
            help="Split transcript by word count based on duration (assumes 140 words/minute)",
        )
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls.parameters()

        # retrieve the settings and credentials
        if not DatastoreCase.already_generated(parameters.case):
            print(f"Case '{parameters.case}' not generated yet")
            return
        auditor = HelperEvaluation.get_auditor(parameters.case, 0)
        
        if parameters.chunk_duration_seconds > 0:
            auditor.set_cycle_duration(parameters.chunk_duration_seconds)
            full_transcript = cls.prepare_cycles_by_word_count(
                auditor.full_transcript(), parameters.chunk_duration_seconds
            )
        else:
            full_transcript = cls.prepare_cycles(auditor.full_transcript(), parameters.cycles)

        identification = IdentificationParameters(
            patient_uuid=Constants.FAUX_PATIENT_UUID,
            note_uuid=auditor.note_uuid(),
            provider_uuid=Constants.FAUX_PROVIDER_UUID,
            canvas_instance="runner-environment",
        )

        chart_data = auditor.limited_chart()
        limited_cache = LimitedCache.load_from_json(chart_data)
        chatter = AudioInterpreter(auditor.settings, auditor.s3_credentials, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        # run the cycles
        errors: dict = {}
        try:
            for cycle, transcript in enumerate(full_transcript.values(), start=1):
                discussion.set_cycle(cycle)
                auditor.set_cycle(cycle)
                previous, _ = Commander.transcript2commands(auditor, transcript, chatter, previous)
        except Exception as e:
            errors = HelperEvaluation.trace_error(e)
        finally:
            auditor.case_finalize(errors)

    @classmethod
    def prepare_cycles(cls, full_transcript: dict[str, list[Line]], cycles: int) -> dict[str, list[Line]]:
        if cycles <= 0:
            return full_transcript

        uncycled_transcript = [line for key, lines in full_transcript.items() for line in lines]
        fenced_cycles = min(max(1, cycles), len(uncycled_transcript))
        length, extra = divmod(len(uncycled_transcript), fenced_cycles)
        result = {}
        start = 0
        for cycle in range(fenced_cycles):
            size = length + (1 if cycle < extra else 0)
            result[f"cycle_{(cycle + 1):03d}"] = uncycled_transcript[start : start + size]
            start += size
        return result

    @classmethod
    def prepare_cycles_by_word_count(cls, full_transcript: dict[str, list[Line]], duration_seconds: int) -> dict[str, list[Line]]:
        """Split transcript by strict word count, splitting mid-sentence if needed.
        
        Args:
            full_transcript: Original transcript with cycle keys
            duration_seconds: Target duration per chunk in seconds
            
        Returns:
            Dictionary with new cycle keys and word-count-based chunks
        """
        # Flatten all lines from all cycles
        uncycled_transcript = [line for lines in full_transcript.values() for line in lines]
        
        if not uncycled_transcript:
            return full_transcript
            
        # Calculate target words per chunk (140 words/minute = 2.33 words/second)
        words_per_minute = 140
        target_words_per_chunk = int((duration_seconds / 60.0) * words_per_minute)
        
        # Flatten all words with their speaker info
        all_words = []
        for line in uncycled_transcript:
            words = line.text.split()
            for word in words:
                all_words.append((line.speaker, word))
        
        # Split into chunks of exactly target_words_per_chunk
        result = {}
        cycle_number = 1
        
        for i in range(0, len(all_words), target_words_per_chunk):
            chunk_words = all_words[i:i + target_words_per_chunk]
            
            # Reconstruct Lines from word chunks
            current_lines = []
            current_speaker = None
            current_text_words = []
            
            for speaker, word in chunk_words:
                if speaker != current_speaker:
                    # Speaker changed, save previous line if exists
                    if current_speaker is not None and current_text_words:
                        current_lines.append(Line(current_speaker, " ".join(current_text_words)))
                    current_speaker = speaker
                    current_text_words = [word]
                else:
                    current_text_words.append(word)
            
            # Add final line
            if current_speaker is not None and current_text_words:
                current_lines.append(Line(current_speaker, " ".join(current_text_words)))
            
            if current_lines:
                result[f"cycle_{cycle_number:03d}"] = current_lines
                cycle_number += 1
            
        return result


if __name__ == "__main__":
    CaseRunner.run()
