# Generated by Django 4.2.13 on 2025-03-29 21:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assistant_bot', '0005_alter_bot_telegram_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='botuser',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='instance',
            name='is_unavailable',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
