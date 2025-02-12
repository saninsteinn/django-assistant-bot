from django.contrib import admin

from assistant.bot.admin import BotAdmin, InstanceAdmin, DialogAdmin, MessageAdmin
from assistant.bot.models import Bot, Message, Dialog, Instance

admin.site.register(Bot, BotAdmin)
admin.site.register(Instance, InstanceAdmin)
admin.site.register(Dialog, DialogAdmin)
admin.site.register(Message, MessageAdmin)
