from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_add_personalization'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='orderdetail',
            options={'ordering': ['id']},
        ),
        migrations.AlterModelOptions(
            name='orderitem',
            options={'ordering': ['id']},
        ),
    ] 