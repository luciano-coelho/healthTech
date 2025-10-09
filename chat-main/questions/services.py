from questions.models import Question


def get_ordered_questions():
    return Question.objects.all().order_by('index')
