from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class RoomServiceMenuItem(models.Model):
    """Menu item that guests can order from the room-service portal."""

    CATEGORY_CHOICES = [
        ('FOOD', 'Makanan'),
        ('BEVERAGE', 'Minuman'),
        ('DESSERT', 'Hidangan Penutup'),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='FOOD')
    price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    image = models.CharField(
        max_length=200, blank=True,
        help_text='Path static, contoh: chatbot/img/nasi-goreng.jpg',
    )
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'room_service_menu_items'
        ordering = ['category', 'sort_order', 'name']

    def __str__(self):
        return f'{self.name} (Rp {self.price:,.0f})'.replace(',', '.')

    @property
    def image_url(self):
        if not self.image:
            return ''
        from django.templatetags.static import static
        url = static(self.image)
        return url if url.startswith(('/', 'http://', 'https://')) else f'/{url}'


class ServiceOrder(models.Model):
    SERVICE_CHOICES = [
        ('FOOD', 'Pesan Makanan & Minuman'),
        ('AMENITIES', 'Request Amenities'),
        ('EXTRA_BED', 'Request Extra Bed'),
        ('LAUNDRY', 'Laundry'),
        ('RECEPTION', 'Chat dengan Resepsionis'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Menunggu Diproses'),
        ('CONFIRMED', 'Dikonfirmasi'),
        ('DELIVERED', 'Diantar / Selesai'),
        ('CANCELLED', 'Dibatalkan'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='service_orders',
    )
    booking = models.ForeignKey(
        'reservations.Booking', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='service_orders',
    )
    service_type = models.CharField(
        max_length=20, choices=SERVICE_CHOICES, default='FOOD',
    )
    detail = models.TextField(blank=True, help_text='Contoh: Nasi Goreng x1, Mie Goreng x2')
    special_instructions = models.TextField(
        blank=True,
        help_text='Permintaan khusus, misalnya tanpa pedas atau tanpa es.',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'service_orders'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_service_type_display()} - {self.user} ({self.status})'

    @property
    def total(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0'))

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def is_active(self):
        return self.status in ('PENDING', 'CONFIRMED')


class ServiceOrderItem(models.Model):
    """A priced line item.  Chatbot-created orders may not have line items."""

    order = models.ForeignKey(
        ServiceOrder, on_delete=models.CASCADE, related_name='items',
    )
    menu_item = models.ForeignKey(
        RoomServiceMenuItem, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='order_items',
    )
    name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
    )

    class Meta:
        db_table = 'room_service_order_items'
        ordering = ['pk']

    def __str__(self):
        return f'{self.name} x{self.quantity}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class ServiceOrderStatusLog(models.Model):
    """Audit trail for room-service order transitions."""

    order = models.ForeignKey(
        ServiceOrder, on_delete=models.CASCADE, related_name='status_logs',
    )
    status = models.CharField(max_length=20, choices=ServiceOrder.STATUS_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='service_order_status_changes',
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'room_service_order_status_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_id} -> {self.status}'
