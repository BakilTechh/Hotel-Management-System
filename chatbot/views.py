from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from accounts.models import GuestProfile
from reservations.models import Booking

from .forms import ServiceOrderForm
from .models import RoomServiceMenuItem, ServiceOrder


class RoomServicePortalView(LoginRequiredMixin, View):
    """Self-service room-service ordering page for guests.

    Guests can browse the live menu, attach the order to an active/upcoming
    reservation and track existing orders. This is the single room-service
    surface of the application (the legacy conversational page was retired).
    """

    template_name = 'chatbot/room_service_portal.html'

    def _context(self, request, form):
        profile, _ = GuestProfile.objects.get_or_create(
            user=request.user,
            defaults={'role': 'ADMIN' if request.user.is_superuser else 'GUEST'},
        )
        orders = (
            ServiceOrder.objects.filter(user=request.user)
            .select_related('booking', 'booking__room', 'booking__room__room_type')
            .prefetch_related('items', 'status_logs')
            .order_by('-created_at')[:10]
        )
        return {
            'active_section': 'room_service',
            'profile': profile,
            'form': form,
            'menu_items': RoomServiceMenuItem.objects.filter(is_available=True),
            'orders': orders,
            'eligible_stay_count': form.fields['booking'].queryset.count(),
        }

    def get(self, request, *args, **kwargs):
        form = ServiceOrderForm(user=request.user)
        return render(request, self.template_name, self._context(request, form))

    def post(self, request, *args, **kwargs):
        form = ServiceOrderForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save()
            messages.success(
                request,
                f'Pesanan #{order.pk:04d} diterima. Tim room service akan '
                'menghubungi kamar Anda untuk konfirmasi.',
            )
            return redirect('room_service_portal')
        messages.error(request, 'Periksa kembali pesanan Anda.')
        return render(request, self.template_name, self._context(request, form))
