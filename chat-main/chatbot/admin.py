from django.contrib import admin

from questions.models import Question

from .models import Briefing, CustomUser, Teacher

admin.site.register(CustomUser)
admin.site.register(Teacher)
admin.site.register(Question)
admin.site.register(Briefing)

# Register your models here.
