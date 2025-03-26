from dataclasses import dataclass


@dataclass
class StatisticCaseTest:
    case_name: str = ""
    run_count: int = 0
    audio2transcript: int = -1
    transcript2instructions: int = -1
    instruction2parameters: int = -1
    parameters2command: int = -1
    end2end: int = 0

