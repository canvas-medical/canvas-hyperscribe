from dataclasses import dataclass


@dataclass
class StatisticCaseTest:
    case_name: str = ""
    run_count: int = 0
    full_run: int = 0
    staged_questionnaires: int = -1
    audio2transcript: int = -1
    transcript2instructions: int = -1
    instruction2parameters: int = -1
    parameters2command: int = -1
    end2end: int = 0
