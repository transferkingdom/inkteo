from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0002_alter_batchorder_order_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderitem',
            name='size',
            field=models.CharField(max_length=100),
        ),
    ] 