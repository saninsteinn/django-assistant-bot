# Generated by Django 4.2.13 on 2024-12-17 19:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assistant_bot', '0003_botuser_instance_dialog_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='photos/'),
        ),
    ]
