from evaluations.datastores.store_cases import StoreCases


class CaseList:

    @classmethod
    def run(cls) -> None:
        headers = {
            "environment": "environment",
            "case_group": "group",
            "case_type": "type",
            "case_name": "case",
            "patient_uuid": "patient UUID",
            "description": "description",
        }
        records = StoreCases.all()

        widths = [len(h) for h in headers.values()]
        for record in records:
            for idx, field in enumerate(headers.keys()):
                if (size := len(getattr(record, field))) > widths[idx]:
                    widths[idx] = size

        header_row = " | ".join(f"{header:<{width}}" for header, width in zip(headers.values(), widths))
        line = "-" * (4 + len(header_row))

        print(line)
        print(f"| {header_row} |")
        print(line)
        for case in records:
            values = [
                case.environment,
                case.case_group,
                case.case_type,
                case.case_name,
                case.patient_uuid,
                case.description,
            ]
            row = " | ".join(f"{value:<{width}}" for value, width in zip(values, widths))
            print(f"| {row} |")
        print(line)


if __name__ == "__main__":
    CaseList.run()
