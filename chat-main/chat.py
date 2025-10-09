import calendar
import datetime
import locale

import pymongo

locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")

mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
db = mongo_client["chat_database"]
questions_collection = db["questions"]
tags_collection = db["tags"]


def get_questions():
    return questions_collection.find({"index": {"$ne": None}}).sort(
        "index", pymongo.ASCENDING
    )


def get_tag_by_question_index(question_index):
    return tags_collection.find({"question_index": question_index})


def main():
    questions_cursor = get_questions()

    questions = list(questions_cursor)

    if not questions:
        print("There are no questions.")

    answers = {}

    for question in questions:
        question_text = question["question"]
        print(f"Pergunta: {question_text}")

        user_response = input("Sua resposta: ")

        answers[question["index"]] = user_response

        print(f"Você respondeu: {user_response}")
    replace_tags(answers)


def replace_tags(answers: dict) -> str:
    text = open("chatbot/templates/modelo.html", "r").read()

    for key in answers.keys():
        tags = list(get_tag_by_question_index(key))

        for t in tags:
            if is_tag_in_tags("##DATA_COMPLETA##", tags):
                data_atual = datetime.datetime.today()
                text = text.replace(
                    "##DATA_COMPLETA##", data_atual.strftime("%d de %B de %Y")
                )

            text = text.replace(t['tag'], answers[key])

    with open("result.html", "w") as result_file:
        result_file.write(text)


def is_tag_in_tags(tag_description: str, tags: list) -> bool:
    return any(tag_description in tag["tag"] for tag in tags)


if __name__ == "__main__":
    main()
