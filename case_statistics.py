from evaluations.datastores.store_results import StoreResults


class CaseStatistics:

    @classmethod
    def run(cls) -> None:
        headers = [
            "case",
            "run count",
            "audio -> transcript",
            "-> instructions",
            "-> parameters",
            "-> command",
            "end to end"
        ]
        records = StoreResults.case_test_statistics()
        widths = [len(h) for h in headers]
        if (len_cases := max([len(r.case_name) for r in records] or [0])) and len_cases >= widths[0]:
            widths[0] = len_cases

        header_row = " | ".join(f"{header:<{width}}" for header, width in zip(headers, widths))
        line = "-" * (4 + len(header_row))

        print(line)
        print(f"| {header_row} |")
        print(line)
        for case in records:
            values = [
                f"{case.case_name:<{widths[0]}}",
                str(case.run_count),
                str(case.audio2transcript) if case.audio2transcript > -1 else "",
                str(case.transcript2instructions) if case.transcript2instructions > -1 else "",
                str(case.instruction2parameters) if case.instruction2parameters > -1 else "",
                str(case.parameters2command) if case.parameters2command > -1 else "",
                str(case.end2end),
            ]
            row = " | ".join(f"{value:^{width}}" for value, width in zip(values, widths))
            print(f"| {row} |")
        print(line)


if __name__ == "__main__":
    CaseStatistics.run()
