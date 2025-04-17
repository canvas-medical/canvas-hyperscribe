from enum import Enum


class QuestionnaireType(Enum):
    QUESTIONNAIRE = "QUES"
    PHYSICAL_EXAM = "EXAM"
    REVIEW_OF_SYSTEM = "ROS"
    STRUCTURED_ASSESSMENT = "SA"
