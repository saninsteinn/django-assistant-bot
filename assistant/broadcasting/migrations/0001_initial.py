# Generated by Django 4.2.13 on 2025-03-29 21:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('assistant_bot', '0006_botuser_phone_number_instance_is_unavailable'),
    ]

    operations = [
        migrations.CreateModel(
            name='BroadcastCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, help_text='Optional name for easy identification in the admin interface.', max_length=255, null=True, verbose_name='Campaign Name')),
                ('message_text', models.TextField(help_text='The text content of the broadcast message.', verbose_name='Message Text')),
                ('platform', models.CharField(choices=[('telegram', 'Telegram')], default='telegram', help_text='The messaging platform for this campaign.', max_length=20, verbose_name='Platform')),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('SCHEDULED', 'Scheduled'), ('SENDING', 'Sending'), ('COMPLETED', 'Completed'), ('PARTIAL_FAILURE', 'Partial Failure'), ('FAILED', 'Failed'), ('CANCELED', 'Canceled')], db_index=True, default='DRAFT', max_length=20, verbose_name='Status')),
                ('scheduled_at', models.DateTimeField(blank=True, db_index=True, help_text='If set, the campaign will start sending at this time. If blank, it can be sent manually.', null=True, verbose_name='Scheduled At')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='Started Sending At')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completed At')),
                ('total_recipients', models.PositiveIntegerField(blank=True, help_text='Estimated or actual number of unique recipients targeted.', null=True, verbose_name='Total Recipients')),
                ('successful_sents', models.PositiveIntegerField(default=0, verbose_name='Successful Sends')),
                ('failed_sents', models.PositiveIntegerField(default=0, help_text='Includes users marked as unavailable and other delivery errors.', verbose_name='Failed Sends')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('bot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='broadcast_campaigns', to='assistant_bot.bot', verbose_name='Bot')),
            ],
            options={
                'verbose_name': 'Broadcast Campaign',
                'verbose_name_plural': 'Broadcast Campaigns',
                'ordering': ['-scheduled_at', '-created_at'],
            },
        ),
    ]
