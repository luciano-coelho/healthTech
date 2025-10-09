from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_remittance, name='upload_remittance'),
    path('detail/<int:id>/', views.remittance_detail, name='remittance_detail'),
    path('detail/<int:id>/reprocess/', views.reprocess_remittance, name='reprocess_remittance'),
    path('detail/<int:id>/qa/', views.qa_remittance, name='qa_remittance'),
    path('consolidated/qa/', views.qa_consolidated, name='qa_consolidated'),
]
