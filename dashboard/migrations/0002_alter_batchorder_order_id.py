from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batchorder',
            name='order_id',
            field=models.CharField(max_length=50, unique=True),
        ),
    ] 