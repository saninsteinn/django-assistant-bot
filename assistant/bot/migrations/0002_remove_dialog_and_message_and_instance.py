from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('assistant_bot', '0001_initial'),  # Replace with the name of the previous migration
    ]

    operations = [
        migrations.DeleteModel(
            name='Dialog',
        ),
        migrations.DeleteModel(
            name='Message',
        ),
        migrations.DeleteModel(
            name='Instance',
        )
    ]
