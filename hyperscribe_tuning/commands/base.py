from hyperscribe_tuning.structures.coded_item import CodedItem


class Base:

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    @classmethod
    def schema_key(cls) -> str:
        raise NotImplementedError

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        raise NotImplementedError
