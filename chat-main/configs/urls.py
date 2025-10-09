from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from chatbot import views

urlpatterns = [
    path('', views.chat_view, name='chat_view'),
    path('admin/', admin.site.urls),
    path('send_message/', views.send_message, name='send_message'),
    path('accounts/', include('accounts.urls')),
    
    path('list-users/', views.list_users, name='list-users'),
    path('edit-user/', views.edit_user, name='edit-user'),
    path('delete-user/<int:id>/', views.delete_user, name='delete-user'),
    
    path('list-teachers/', views.list_teachers, name='list-teachers'),
    path('edit-teacher/', views.edit_teacher, name='edit-teacher'),
    path('delete-teacher/<int:id>/', views.delete_teacher, name='delete-teacher'),


    path('list-proposals/', views.list_proposals, name='list-proposals'),
    path('update-proposal/', views.update_proposal, name='update-proposal'),
    
    
    path('briefing/', views.form_briefing, name='briefing'),
    path('generate_proposal/', views.generate_prosal, name='generate_proposal'),
   
   
    path('download_doc/', views.download_doc, name='download_doc'),

    
    path('create-user/', views.create_user, name='create-user'),
    path('create-teacher/', views.create_teacher, name='create-teacher'),
    path('change-password/', views.update_password, name='change_password'),




    path('testchat/', views.testchat, name='testchat'),
    
    path('reconciliation/', include('reconciliation.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
