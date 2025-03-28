# consumer.py
import os
import django
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fashion_app.settings')
django.setup()

from .models import Supplier, Category, Material, Inventory, Order, OrderLine, Receipt, ReceiptLine, Issue, ProductCategory, ProductType, Collection, Size, Color, Design, SKU, InventorySKU, QC, Import, ImportLine, Export, ExportLine, Employee, ColorInDesign, SizeInDesign, Progress, Message
import json


class UserChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'user_chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        username = data['username']
        room = data['room']

        await self.save_message(username, room, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def save_message(self, username, room, message):
        Message.objects.create(username=username, room=room, content=message)

class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user1 = self.scope['url_route']['kwargs']['user1']
        self.user2 = self.scope['url_route']['kwargs']['user2']
        self.private_chat_group = f'private_chat_{min(self.user1, self.user2)}_{max(self.user1, self.user2)}'

        await self.channel_layer.group_add(
            self.private_chat_group,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.private_chat_group,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender = data['sender']
        recipient = data['recipient']
        room = f'private_{min(sender, recipient)}_{max(sender, recipient)}'

        await self.save_message(sender, room, message)

        await self.channel_layer.group_send(
            self.private_chat_group,
            {
                'type': 'private_message',
                'message': message,
                'sender': sender
            }
        )

    async def private_message(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def save_message(self, sender, room, message):
        Message.objects.create(username=sender, room=room, content=message)

class PrivateChatBotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['url_route']['kwargs']['user']
        self.bot = "ChatBot"
        self.private_chat_group = f'private_chatbot_{self.user}'

        await self.channel_layer.group_add(
            self.private_chat_group,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.private_chat_group,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender = data['sender']
        room = f'private_chatbot_{sender}'

        await self.save_message(sender, room, message)

        bot_response = await self.get_bot_response(message)
        
        await self.channel_layer.group_send(
            self.private_chat_group,
            {
                'type': 'private_message',
                'message': message,
                'sender': sender
            }
        )

        if bot_response:
            await self.save_message(self.bot, room, bot_response)
            await self.channel_layer.group_send(
                self.private_chat_group,
                {
                    'type': 'private_message',
                    'message': bot_response,
                    'sender': self.bot
                }
            )

    async def private_message(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def save_message(self, sender, room, message):
        Message.objects.create(username=sender, room=room, content=message)

    @sync_to_async
    def check_inventory(self, material_name):
        inventory_item = Inventory.objects.filter(material__material_name__icontains=material_name).first()
        if inventory_item:
            return f"Số lượng {inventory_item.material.material_name} còn lại trong kho: {inventory_item.quantity}"
        return "Nguyên vật liệu không có trong kho."
    
    @sync_to_async
    def check_inventory_sku(self, sku_name):
        inventory_sku = InventorySKU.objects.filter(sku__sku_name__icontains=sku_name).first()
        if inventory_sku:
            return f"Số lượng SKU {inventory_sku.sku.sku_name} còn lại trong kho: {inventory_sku.quantity}"
        return "SKU không có trong kho."

    async def get_bot_response(self, message):
        """ Phản hồi của chatbot theo quy tắc bằng tiếng Việt """
        message = message.lower()
        
        rules = {
            "xin chào": "Xin chào! Tôi có thể giúp gì cho bạn hôm nay?",
            "chào": "Chào bạn! Bạn cần hỗ trợ gì không?",
            "bạn khỏe không": "Tôi chỉ là một chatbot, nhưng tôi luôn sẵn sàng giúp đỡ bạn!",
            "tạm biệt": "Tạm biệt! Chúc bạn một ngày tốt lành!",
            "giúp tôi": "Chắc chắn rồi! Bạn có thể hỏi tôi về các dịch vụ của chúng tôi.",
            "bạn tên gì": "Tôi là ChatBot, trợ lý ảo của bạn!",
            "thời tiết hôm nay thế nào": "Tôi không thể kiểm tra thời tiết, nhưng bạn có thể thử với Google Weather!",
            "cảm ơn": "Không có gì! Rất vui khi được giúp bạn!",
            "bạn có thể làm gì": "Tôi có thể giúp bạn kiểm tra tồn kho nguyên vật liệu, SKU, hoặc trả lời các câu hỏi cơ bản!",
            "tôi cần kiểm tra tồn kho nguyên vật liệu": "Bạn vui lòng cho tôi biết tên nguyên vật liệu cần kiểm tra?",
            "tôi cần kiểm tra tồn kho sku": "Bạn vui lòng cho tôi biết tên SKU cần kiểm tra?",
            "có bao nhiêu sản phẩm trong kho": "Bạn vui lòng cung cấp tên SKU hoặc nguyên vật liệu để tôi kiểm tra giúp bạn!"
        }

        for key in rules:
            if key in message:
                return rules[key]
        
        if hasattr(self, "awaiting_material") and self.awaiting_material:
            self.awaiting_material = False
            return await self.check_inventory(message)
        
        if hasattr(self, "awaiting_sku") and self.awaiting_sku:
            self.awaiting_sku = False
            return await self.check_inventory_sku(message)
        
        if "kiểm tra tồn kho nguyên vật liệu" in message:
            self.awaiting_material = True
            return "Bạn vui lòng nhập tên nguyên vật liệu cần kiểm tra."
        
        if "kiểm tra tồn kho sku" in message:
            self.awaiting_sku = True
            return "Bạn vui lòng nhập tên SKU cần kiểm tra."
        
        return "Xin lỗi, tôi chưa hiểu yêu cầu của bạn. Bạn có thể hỏi về nguyên vật liệu hoặc SKU trong kho."


# class PrivateChatBotConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         self.user = self.scope['url_route']['kwargs']['user']
#         self.bot = "ChatBot"
#         self.private_chat_group = f'private_chatbot_{self.user}'

#         await self.channel_layer.group_add(
#             self.private_chat_group,
#             self.channel_name
#         )

#         await self.accept()

#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(
#             self.private_chat_group,
#             self.channel_name
#         )

#     async def receive(self, text_data):
#         data = json.loads(text_data)
#         message = data['message']
#         sender = data['sender']
#         room = f'private_chatbot_{sender}'

#         await self.save_message(sender, room, message)

#         bot_response = await self.get_bot_response(message)
        
#         await self.channel_layer.group_send(
#             self.private_chat_group,
#             {
#                 'type': 'private_message',
#                 'message': message,
#                 'sender': sender
#             }
#         )

#         if bot_response:
#             await self.save_message(self.bot, room, bot_response)
#             await self.channel_layer.group_send(
#                 self.private_chat_group,
#                 {
#                     'type': 'private_message',
#                     'message': bot_response,
#                     'sender': self.bot
#                 }
#             )

#     async def private_message(self, event):
#         await self.send(text_data=json.dumps(event))

#     @sync_to_async
#     def save_message(self, sender, room, message):
#         Message.objects.create(username=sender, room=room, content=message)

#     async def get_bot_response(self, message):
#         """ Phản hồi của chatbot theo quy tắc """
#         message = message.lower()
        
#         rules = {
#             "xin chào": "Xin chào! Tôi có thể giúp gì cho bạn hôm nay?",
#             "bạn khỏe không": "Tôi chỉ là một chatbot, nhưng tôi luôn sẵn sàng giúp đỡ bạn!",
#             "tạm biệt": "Tạm biệt! Chúc bạn một ngày tốt lành!",
#             "cảm ơn": "Không có gì! Rất vui khi được giúp bạn!",
#             "bạn có thể làm gì": "Tôi có thể giúp bạn trả lời các câu hỏi cơ bản!",
#         }

#         for key in rules:
#             if key in message:
#                 return rules[key]

#         return "Xin lỗi, tôi chưa hiểu yêu cầu của bạn. Bạn có thể hỏi về thông tin cơ bản!"