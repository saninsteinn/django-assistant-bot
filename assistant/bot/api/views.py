import logging
from asgiref.sync import sync_to_async, async_to_sync

from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions, mixins

from assistant.bot.api.serializers import DialogSerializer, \
    MessageSerializer, AnsweredMessageSerializer, BotSerializer
from assistant.bot.domain import Update
from assistant.bot.models import Bot, Dialog, Message
from assistant.bot.services.dialog_service import create_user_message
from assistant.bot.services.instance_service import InstanceLock
from assistant.bot.utils import get_bot_platform, get_bot_class

logger = logging.getLogger(__name__)


class BotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Bot.objects.order_by('id')
    serializer_class = BotSerializer
    lookup_field = 'codename'

#     @swagger_auto_schema(
#         method='post',
#         request_body=ChatCompletionRequestSerializer,
#         responses={200: ChatCompletionResultSerializer, 204: 'No Content', 400: 'Bad Request', 404: 'Not Found'}
#     )
#     @action(detail=True, methods=['post'], url_path='chat/completions')
#     def chat_completion(self, request: Request, codename=None):
#         chat_completion_view = ChatCompletionView.as_view()
#         response = chat_completion_view(request._request, codename=codename)
#         return response
#
#
# class ChatCompletionView(APIView):
#
#     LANGUAGE = 'ru'
#
#     def post(self, request, *args, **kwargs):
#
#         handle_dialog_start_ts = time.time()
#
#         serializer = ChatCompletionRequestSerializer(data=request.data)
#         if serializer.is_valid():
#             data = serializer.validated_data
#
#             bot = self._get_bot()
#             resource_manager = ResourceManager(bot.codename, language=self.LANGUAGE)
#             chat_completion = ChatCompletion(
#                 bot=bot,
#                 resource_manager=resource_manager,
#                 fast_ai_model=ENV.str('DIALOG_FAST_AI_MODEL'),
#                 strong_ai_model=ENV.str('DIALOG_STRONG_AI_MODEL')
#             )
#
#             messages = data['messages']
#             debug_info = {}
#
#             answer = asyncio.run(chat_completion.generate_answer(messages, debug_info))
#
#             debug_info['total'] = {
#                 'took': time.time() - handle_dialog_start_ts
#             }
#             logger.debug('Debug info: %s', debug_info)
#
#             if answer:
#
#                 finish_reason = 'stop'
#                 if answer.buttons:
#                     for buttons in answer.buttons:
#                         if buttons[0].callback_data == '/continue':
#                             finish_reason = 'length'
#
#                 response_data = {
#                     "choices": [{
#                         "message": {
#                             "role": "assistant",
#                             "content": answer.text
#                         },
#                         "finish_reason": finish_reason
#                     }]
#                 }
#                 response_serializer = ChatCompletionResultSerializer(data=response_data)
#                 if response_serializer.is_valid():
#                     return Response(response_serializer.data, status=status.HTTP_200_OK)
#                 else:
#                     return Response(response_serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#             else:
#                 return Response({
#                     "choices": []
#                 }, status=status.HTTP_204_NO_CONTENT)
#
#         else:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#     @property
#     def codename(self) -> str:
#         return self.kwargs.get('codename', '')
#
#     def _get_bot(self) -> Bot:
#         try:
#             return Bot.objects.get(codename=self.codename)
#         except Bot.DoesNotExist:
#             raise Http404(f'Bot {self.codename} not found')
#

class DialogViewSet(viewsets.ModelViewSet):
    serializer_class = DialogSerializer
    permission_classes = [permissions.IsAuthenticated]

    queryset = Dialog.objects.all()

    # def get_queryset(self):
    #     return Dialog.objects.filter(instance=self.request.user)

    # def perform_create(self, serializer):
    #     # instance_data = {'user_id': self.request.user.id}
    #     serializer.save()

    # @action(detail=True, methods=['post'])
    # def run(self, request, pk=None):
    #     dialog = self.get_object()
    #     # Get all messages in the dialog
    #     messages = dialog.messages.all().order_by('created_at')
    #
    #     # Prepare dialog history for AI model
    #     conversation = []
    #     for message in messages:
    #         conversation.append({
    #             'role': message.role,
    #             'content': message.content
    #         })
    #
    #     # Call AI model to generate response
    #     assistant_response = self.generate_assistant_response(conversation)
    #
    #     # Save assistant's response as a new message
    #     Message.objects.create(
    #         dialog=dialog,
    #         role='assistant',
    #         content=assistant_response
    #     )
    #
    #     # Return updated dialog
    #     serializer = self.get_serializer(dialog)
    #     return Response(serializer.data)
    #
    # def generate_assistant_response(self, conversation):
    #     # Here integrate your AI model for generating response
    #     # Example with using the last user message
    #     last_user_message = conversation[-1]['content'] if conversation else ''
    #     return f"Assistant's response to: {last_user_message}"


class MessageViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        dialog_id = self.kwargs['dialog_pk']
        dialog = get_object_or_404(Dialog, pk=dialog_id)
        return Message.objects.filter(dialog=dialog)

    def create(self, request, *args, **kwargs):
        dialog_id = self.kwargs['dialog_pk']
        dialog = get_object_or_404(Dialog.objects.select_related('instance', 'instance__bot', 'instance__user'), pk=dialog_id)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with InstanceLock(dialog.instance):
            async_to_sync(
                self._generate_assistant_response
            )(dialog, serializer.validated_data['text'])

            user_message = Message.objects.filter(
                dialog=dialog,
                role__name='user',
            ).order_by('-id').first()

        headers = self.get_success_headers(serializer.data)
        serializer = AnsweredMessageSerializer(user_message)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    async def _generate_assistant_response(self, dialog, user_input):
        instance = dialog.instance
        username = dialog.instance.user.username

        bot = dialog.instance.bot
        bot_codename = bot.codename
        platform_codename = 'default_platform'  # Adjust this as needed

        # Get platform and bot class asynchronously
        platform = await sync_to_async(get_bot_platform)(bot_codename, platform_codename)
        bot_cls = get_bot_class(bot_codename)
        bot_instance = bot_cls(dialog=dialog, platform=platform)

        message_id = await sync_to_async(dialog.messages.count)()

        # Construct the update object
        update_dict = {
            'chat_id': dialog.id,
            'text': user_input,
            'message_id': message_id,
            'user': {
                'id': instance.id if instance else dialog.id,
                'username': username,
            }
        }
        update = Update.from_dict(update_dict)

        user_message = await sync_to_async(create_user_message)(dialog, update.message_id, update.text, update.photo)

        # Call handle_update and get the assistant's response
        answer = await bot_instance.handle_update(update)


        if answer:
            await bot_instance.on_answer_sent(answer)
