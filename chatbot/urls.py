from django.urls import path
from .views import chat_api

urlpatterns = [
    path("chat/", chat_api, name="chat_api"),
]
from django.urls import path
from .views import chat_api, chat_page


urlpatterns = [
    path('assistant/', chat_page, name='chat_page'),
    path('chat/', chat_api, name='chat_api'),
]
