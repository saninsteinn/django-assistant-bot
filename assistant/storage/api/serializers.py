import time

from drf_yasg import openapi
from rest_framework import serializers

from assistant.bot.models import Bot
from assistant.storage.models import WikiDocument, WikiDocumentProcessing


class UnixTimestampField(serializers.DateTimeField):
    def to_representation(self, value):
        return int(time.mktime(value.timetuple())) if value else None

    class Meta:
        swagger_schema_fields = {
            "type": openapi.TYPE_INTEGER,
            "format": openapi.FORMAT_INT64,
            "description": "Unix timestamp"
        }


class WikiDocumentProcessingSerializer(serializers.ModelSerializer):
    class Meta:
        model = WikiDocumentProcessing
        fields = ['completed']


class WikiDocumentSerializer(serializers.ModelSerializer):

    bot = serializers.CharField(source='bot.codename', required=False)
    created_at = UnixTimestampField(read_only=True)
    updated_at = UnixTimestampField(read_only=True)
    processing = serializers.SerializerMethodField()

    class Meta:
        model = WikiDocument
        exclude = ['lft', 'rght', 'tree_id', 'level']

    def get_processing(self, obj):
        processing_instance = obj.processing.last()
        return WikiDocumentProcessingSerializer(processing_instance).data if processing_instance else None

    def create(self, validated_data):
        self._set_bot(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._set_bot(validated_data)
        return super().update(instance, validated_data)

    # @classmethod
    # def bulk_create(cls, validated_data_list):
    #     instances = []
    #     for validated_data in validated_data_list:
    #         cls._set_bot(validated_data)
    #         instances.append(cls.Meta.model(**validated_data))
    #     return cls.Meta.model.objects.bulk_create(instances)  # TODO проблемы с MPTT и сигналами

    @staticmethod
    def _set_bot(validated_data):
        bot_codename = validated_data.pop('bot', {}).get('codename')
        if bot_codename:
            try:
                print('BOT CODENAME:', bot_codename)
                bot = Bot.objects.get(codename=bot_codename)
            except Bot.DoesNotExist:
                raise serializers.ValidationError({"bot": "Bot does not exist."})
            validated_data['bot'] = bot
        return validated_data
