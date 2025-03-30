import uuid

from django.shortcuts import get_object_or_404
from rest_framework import serializers

from assistant.bot.models import Dialog, Message, Instance, Role, Bot, BotUser


class ChatCompletionMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['system', 'user', 'assistant'])
    content = serializers.CharField()


class ChatCompletionRequestSerializer(serializers.Serializer):
    messages = serializers.ListField(child=ChatCompletionMessageSerializer())


class ChoiceSerializer(serializers.Serializer):
    message = ChatCompletionMessageSerializer()
    finish_reason = serializers.ChoiceField(choices=['stop', 'length'])


class ChatCompletionResultSerializer(serializers.Serializer):
    choices = serializers.ListField(child=ChoiceSerializer())


class BotUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = BotUser
        fields = ('user_id', 'username', 'language')


class DialogSerializer(serializers.ModelSerializer):

    bot = serializers.SlugRelatedField(
        'codename',
        queryset=Bot.objects.all(),
        source='instance.bot',
    )
    user = BotUserSerializer(source='instance.user', required=False)

    class Meta:
        model = Dialog
        fields = ('id', 'bot', 'user', 'is_completed')

    def to_representation(self, instance):
        # Override to return bot codename stored in the instance
        ret = super().to_representation(instance)
        # ret['bot'] = instance.instance.bot.codename  # Assuming 'bot' is a related object on Dialog
        return ret

    def create(self, validated_data):
        # bot_codename = validated_data.pop('bot')
        instance_data = validated_data.pop('instance', {})
        user_data = instance_data.pop('user', {})

        bot = instance_data['bot']
        # bot = get_object_or_404(Bot, codename=bot_codename)
        _uuid = uuid.uuid4()

        bot_user, _ = BotUser.objects.get_or_create(
            user_id=user_data.pop('user_id', str(_uuid)),
            platform='api',
            defaults=user_data
        )

        instance, _ = Instance.objects.get_or_create(
            bot=bot,
            user=bot_user,
        )
        return Dialog.objects.create(id=_uuid, instance=instance, **validated_data)

    def update(self, instance, validated_data):
        if 'bot' in validated_data:
            bot_codename = validated_data.pop('bot')
            instance.bot = Bot.objects.get(codename=bot_codename)
        return super().update(instance, validated_data)


class MessageSerializer(serializers.ModelSerializer):

    timestamp = serializers.SerializerMethodField()
    # timestamp = serializers.DateTimeField(format='%s', required=False)

    class Meta:
        model = Message
        fields = ('id', 'timestamp', 'text')
        extra_kwargs = {
            'dialog': {'required': False},
            'role': {'required': False},
        }

    def get_timestamp(self, obj):
        if isinstance(obj, dict):
            return obj.get('timestamp', None)
        return int(obj.timestamp.timestamp())


class AnsweredMessageSerializer(MessageSerializer):

    answer = serializers.SerializerMethodField()

    class Meta(MessageSerializer.Meta):
        fields = MessageSerializer.Meta.fields + ('answer',)

    def get_answer(self, obj):
        if isinstance(obj, dict):
            return obj.get('answer', None)
        answer_messages = Message.objects.filter(
            dialog_id=obj.dialog_id,
            role__name='assistant',
            id__gt=obj.id
        ).order_by('id')
        return MessageSerializer(answer_messages, many=True).data


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = ['codename']
