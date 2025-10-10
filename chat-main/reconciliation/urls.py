from django.urls import path
from . import views

from .views_extrato import extrato_redirect
from . import views

urlpatterns = [
    path('extrato/', extrato_redirect, name='extrato_redirect'),
    path('consolidated/', views.consolidated_dashboard, name='consolidated_dashboard'),
    path('upload/', views.upload_remittance, name='upload_remittance'),
    path('detail/<int:id>/', views.remittance_detail, name='remittance_detail'),
    path('detail/<int:id>/reprocess/', views.reprocess_remittance, name='reprocess_remittance'),
    path('detail/<int:id>/qa/', views.qa_remittance, name='qa_remittance'),
    path('consolidated/qa/', views.qa_consolidated, name='qa_consolidated'),
    path('prices/', views.list_prices, name='prices_list'),
    path('prices/new/', views.price_create, name='price_create'),
    path('prices/<int:id>/edit/', views.price_update, name='price_update'),
    path('prices/<int:id>/delete/', views.price_delete, name='price_delete'),
]
