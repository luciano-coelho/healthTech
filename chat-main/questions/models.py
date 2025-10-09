from django.db import models


class Question(models.Model):
    question = models.CharField(max_length=256, null=False, blank=False)
    index = models.PositiveIntegerField(unique=True)

    def __str__(self):
        return f"{self.index}: {self.question}"
