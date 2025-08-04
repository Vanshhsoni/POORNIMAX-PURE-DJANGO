from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('inbox/', views.inbox_view, name='inbox'),
    path('inbox_updates/', views.inbox_updates, name='inbox_updates'),
    path('inbox_content/', views.inbox_content, name='inbox_content'),
    path('inbox_unread_status/', views.inbox_unread_status, name='inbox_unread_status'),
    path('delete/<str:username>/', views.delete_chat, name='delete_chat'),
    path('<str:username>/', views.chat_view, name='chat_with_user'),
    path('<str:username>/poll/', views.poll_new_messages, name='poll_messages'),
]