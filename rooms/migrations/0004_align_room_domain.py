import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('rooms', '0003_alter_roomtype_capacity_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='room',
            old_name='room_number',
            new_name='number',
        ),
        migrations.AddField(
            model_name='room',
            name='floor',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='room',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='room',
            name='number',
            field=models.CharField(max_length=10, unique=True),
        ),
        migrations.AlterField(
            model_name='room',
            name='status',
            field=models.CharField(
                choices=[
                    ('CLEAN', 'Clean'),
                    ('DIRTY', 'Dirty'),
                    ('MAINTENANCE', 'Maintenance'),
                ],
                default='CLEAN',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='RoomAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('is_available', models.BooleanField(default=True)),
                ('note', models.CharField(blank=True, max_length=200)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availabilities', to='rooms.room')),
            ],
            options={
                'verbose_name_plural': 'Room availabilities',
                'ordering': ['date'],
                'unique_together': {('room', 'date')},
            },
        ),
    ]
