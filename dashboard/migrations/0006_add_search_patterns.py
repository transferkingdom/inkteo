from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_update_ordering'),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchPattern',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pattern_type', models.CharField(choices=[('size', 'Size Pattern'), ('color', 'Color Pattern')], max_length=20)),
                ('pattern', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['pattern_type', 'pattern'],
            },
        ),
    ] 