#routing.py 
from django.urls import path
from .consumers import UserChatConsumer, PrivateChatBotConsumer, PrivateChatConsumer

websocket_urlpatterns = [
    path('ws/chat/<str:room_name>/', UserChatConsumer.as_asgi()),
    path('ws/chatbot/<str:user>/', PrivateChatBotConsumer.as_asgi()),
    path('ws/private/<str:user1>/<str:user2>/', PrivateChatConsumer.as_asgi()),
]
