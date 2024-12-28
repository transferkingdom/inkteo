from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_alter_orderitem_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='personalization',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
    ] 