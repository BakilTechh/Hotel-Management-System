from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from reservations.models import Booking

from .models import (
    RoomServiceMenuItem,
    ServiceOrder,
    ServiceOrderItem,
    ServiceOrderStatusLog,
)


class ServiceOrderForm(forms.Form):
    """Structured room-service order built from the live menu.

    Only bookings that are active or upcoming for the logged-in guest are
    selectable.  Prices are copied server-side from the menu, not from POST
    data, so a guest cannot tamper with the invoice.
    """

    booking = forms.ModelChoiceField(
        queryset=Booking.objects.none(),
        label='Reservasi',
        empty_label='— Pilih reservasi —',
        widget=forms.Select(attrs={'class': 'nh-input'}),
    )
    special_instructions = forms.CharField(
        label='Catatan untuk dapur',
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'nh-input nh-textarea',
            'rows': 3,
            'placeholder': 'Contoh: tanpa pedas, tanpa es, antar pukul 19:00',
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        self.menu_items = list(
            RoomServiceMenuItem.objects.filter(is_available=True)
            .order_by('category', 'sort_order', 'name')
        )
        super().__init__(*args, **kwargs)

        today = timezone.localdate()
        self.fields['booking'].queryset = (
            Booking.objects.filter(
                user=user,
                status_pesanan__in=Booking.SERVICE_ELIGIBLE_STATUSES,
                tanggal_check_out__gte=today,
            )
            .select_related('room', 'room__room_type')
            .order_by('tanggal_check_in')
        )

        for item in self.menu_items:
            self.fields[f'quantity_{item.pk}'] = forms.IntegerField(
                label=item.name,
                min_value=0,
                max_value=20,
                required=False,
                initial=0,
                widget=forms.NumberInput(attrs={
                    'class': 'qty-input',
                    'min': 0,
                    'max': 20,
                    'inputmode': 'numeric',
                    'aria-label': f'Jumlah {item.name}',
                    'data-price': str(item.price),
                    'data-name': item.name,
                }),
            )
        self.estimated_total = Decimal('0')

    def menu_rows(self):
        """Template helper: [(menu item, bound quantity field), ...]."""
        return [
            (item, self[f'quantity_{item.pk}'])
            for item in self.menu_items
        ]

    def clean(self):
        cleaned_data = super().clean()
        selected = []
        total = Decimal('0')
        for item in self.menu_items:
            quantity = cleaned_data.get(f'quantity_{item.pk}') or 0
            if quantity:
                selected.append((item, quantity))
                total += item.price * quantity
        if not selected:
            raise ValidationError('Pilih minimal satu menu untuk dipesan.')
        if len(selected) > 12:
            raise ValidationError('Maksimal 12 jenis menu dalam satu pesanan.')
        self.cleaned_items = selected
        self.estimated_total = total
        return cleaned_data

    @transaction.atomic
    def save(self):
        booking = self.cleaned_data['booking']
        order = ServiceOrder.objects.create(
            user=self.user,
            booking=booking,
            service_type='FOOD',
            detail=', '.join(
                f'{item.name} x{quantity}' for item, quantity in self.cleaned_items
            ),
            special_instructions=self.cleaned_data.get('special_instructions', '').strip(),
            status='PENDING',
        )
        for item, quantity in self.cleaned_items:
            ServiceOrderItem.objects.create(
                order=order,
                menu_item=item,
                name=item.name,
                unit_price=item.price,
                quantity=quantity,
            )
        ServiceOrderStatusLog.objects.create(
            order=order,
            status='PENDING',
            note='Pesanan dibuat dari portal room service.',
            changed_by=self.user,
        )
        return order
