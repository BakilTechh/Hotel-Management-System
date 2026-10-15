from django.core.validators import MinValueValidator
from django.db import models

class RoomType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    capacity = models.PositiveIntegerField(default=2, validators=[MinValueValidator(1)])
 
    class Meta:
        db_table = 'room_types'
        ordering = ['name']
 
    def __str__(self):
        return self.name
 
 
class Room(models.Model):
    STATUS_CHOICES = [
        ('CLEAN', 'Clean'),
        ('DIRTY', 'Dirty'),
        ('MAINTENANCE', 'Maintenance'),
    ]
 
    number = models.CharField(max_length=10, unique=True)
    room_type = models.ForeignKey(
        RoomType, on_delete=models.PROTECT, related_name='rooms'
    )
    floor = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='CLEAN'
    )
    is_active = models.BooleanField(default=True)
 
    class Meta:
        db_table = 'rooms'
        ordering = ['number']
 
    def __str__(self):
        return f'Room {self.number} ({self.room_type})'


class RoomAvailability(models.Model): #ini buat ketersediaan room (?)
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name='availabilities'
    )
    date = models.DateField()
    is_available = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True)
 
    class Meta:
        ordering = ['date']
        unique_together = ('room', 'date')
        verbose_name_plural = 'Room availabilities'
 
    def __str__(self):
        state = 'Available' if self.is_available else 'Blocked'
        return f'{self.room.number} - {self.date} - {state}'


# Create your models here.
