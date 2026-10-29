import json
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views import View

from accounts.models import GuestProfile
from reservations.models import Booking

from .forms import ServiceOrderForm
from .menu import available_menu, build_menu_groups, menu_stats, recommended_items
from .models import ServiceOrder
from .services import (
    CONCIERGE_NAME,
    check_rate_limit,
    clear_chat_history,
    generate_concierge_reply,
    load_chat_history,
    remember_exchange,
)

logger = logging.getLogger(__name__)

RECENT_ORDER_LIMIT = 8


def _guest_profile(user):
    profile, _created = GuestProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'ADMIN' if user.is_superuser else 'GUEST'},
    )
    return profile


def _order_queryset(user):
    queryset = (
        ServiceOrder.objects.select_related(
            'booking', 'booking__room', 'booking__room__room_type',
        )
        .prefetch_related('items__menu_item', 'status_logs')
        .order_by('-created_at')
    )
    if not user.is_staff:
        queryset = queryset.filter(user=user)
    return queryset


def _tracked_orders(user):
    """Active orders first, then the most recent finished ones."""
    queryset = _order_queryset(user)
    active = list(queryset.filter(status__in=ServiceOrder.ACTIVE_STATUSES)[:4])
    active_ids = {order.pk for order in active}
    recent = list(queryset.exclude(pk__in=active_ids)[:RECENT_ORDER_LIMIT - len(active)])
    return active + recent


def _order_status_payload(order, request):
    return {
        'id': order.pk,
        'code': order.order_code,
        'status': order.status,
        'status_label': order.get_status_display(),
        'status_tone': order.status_tone,
        'fulfillment': order.fulfillment,
        'fulfillment_label': order.get_fulfillment_display(),
        'active': order.is_active,
        'progress': order.progress_percent,
        'updated_at': timezone.localtime(order.updated_at).isoformat(),
        'html': render_to_string(
            'chatbot/_order_tracking.html',
            {'order': order},
            request=request,
        ),
    }


class RoomServicePortalView(LoginRequiredMixin, View):
    """Single room-service surface: menu, ordering and live tracking."""

    template_name = 'chatbot/room_service_portal.html'

    def _context(self, request, form):
        menu_items = form.menu_items
        eligible_bookings = list(form.eligible_bookings)
        primary_stay = next(
            (b for b in eligible_bookings if b.status_pesanan == 'CHECKED_IN'),
            eligible_bookings[0] if eligible_bookings else None,
        )
        orders = _tracked_orders(request.user)
        return {
            'active_section': 'room_service',
            'profile': _guest_profile(request.user),
            'form': form,
            'menu_items': menu_items,
            'menu_groups': build_menu_groups(menu_items),
            'recommended_items': recommended_items(menu_items),
            'menu_stats': menu_stats(menu_items),
            'orders': orders,
            'active_order_count': sum(1 for order in orders if order.is_active),
            'eligible_stay_count': len(eligible_bookings),
            'primary_stay': primary_stay,
            'today': timezone.localdate(),
            'chat_history': load_chat_history(request),
            'chat_configured': _gemini_configured(),
            'concierge_name': CONCIERGE_NAME,
            'tracking_endpoint': '/room-service/api/orders/status/',
        }

    def get(self, request, *args, **kwargs):
        form = ServiceOrderForm(user=request.user)
        return render(request, self.template_name, self._context(request, form))

    def post(self, request, *args, **kwargs):
        form = ServiceOrderForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                order = form.save()
            except ValidationError as exc:
                form.add_error(None, exc)
                messages.error(request, 'Pesanan belum dapat diproses.')
                return render(
                    request, self.template_name, self._context(request, form),
                )
            detail_url = reverse(
                'room_service_order_detail', kwargs={'pk': order.pk},
            )
            return redirect(f'{detail_url}?placed=1')
        messages.error(request, 'Periksa kembali pesanan Anda.')
        return render(request, self.template_name, self._context(request, form))


def _gemini_configured():
    from django.conf import settings
    return bool(str(getattr(settings, 'GEMINI_API_KEY', '') or '').strip())


class ServiceOrderDetailView(LoginRequiredMixin, View):
    """Track one order with a live, auto-refreshing timeline."""

    template_name = 'chatbot/order_detail.html'

    def get(self, request, pk, *args, **kwargs):
        order = get_object_or_404(_order_queryset(request.user), pk=pk)
        return render(request, self.template_name, {
            'active_section': 'room_service',
            'profile': _guest_profile(request.user),
            'order': order,
            'just_placed': request.GET.get('placed') == '1',
            'concierge_name': CONCIERGE_NAME,
            'tracking_endpoint': f'/room-service/api/orders/{order.pk}/status/',
        })


class ConciergeChatView(LoginRequiredMixin, View):
    """JSON endpoint for the floating concierge panel."""

    raise_exception = True

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse(
                {'ok': False, 'error': 'Format permintaan tidak valid.'},
                status=400,
            )
        if not isinstance(payload, dict):
            return JsonResponse(
                {'ok': False, 'error': 'Format permintaan tidak valid.'},
                status=400,
            )

        if payload.get('reset') is True:
            clear_chat_history(request)
            return JsonResponse({'ok': True, 'reset': True})

        message = str(payload.get('message', '')).strip()
        if not message:
            return JsonResponse(
                {'ok': False, 'error': 'Tuliskan pertanyaan Anda terlebih dahulu.'},
                status=400,
            )
        if len(message) > 1000:
            return JsonResponse(
                {'ok': False, 'error': 'Pesan terlalu panjang (maksimal 1.000 karakter).'},
                status=400,
            )

        allowed, retry_after = check_rate_limit(request)
        if not allowed:
            return JsonResponse(
                {
                    'ok': False,
                    'error': (
                        'Anda mengirim pesan terlalu cepat. '
                        f'Coba lagi dalam {retry_after} detik.'
                    ),
                    'retry_after': retry_after,
                },
                status=429,
            )

        history = load_chat_history(request)
        reply = generate_concierge_reply(
            message=message,
            user=request.user,
            history=history,
        )
        if reply.text and reply.configured and not reply.degraded:
            remember_exchange(request, message, reply.text)

        return JsonResponse({
            'ok': True,
            'reply': reply.text,
            'configured': reply.configured,
            'degraded': reply.degraded,
            'concierge': CONCIERGE_NAME,
        })


class RecentOrderStatusView(LoginRequiredMixin, View):
    """Polling endpoint for every tracking card on the portal."""

    raise_exception = True

    def get(self, request, *args, **kwargs):
        orders = _tracked_orders(request.user)
        response = JsonResponse({
            'ok': True,
            'has_active': any(order.is_active for order in orders),
            'server_time': timezone.localtime().isoformat(),
            'orders': [_order_status_payload(order, request) for order in orders],
        })
        response['Cache-Control'] = 'no-store'
        return response


class ServiceOrderStatusView(LoginRequiredMixin, View):
    """Polling endpoint for the single-order tracking page."""

    raise_exception = True

    def get(self, request, pk, *args, **kwargs):
        order = get_object_or_404(_order_queryset(request.user), pk=pk)
        response = JsonResponse({
            'ok': True,
            'server_time': timezone.localtime().isoformat(),
            'order': _order_status_payload(order, request),
        })
        response['Cache-Control'] = 'no-store'
        return response



class ServiceOrderQueueView(LoginRequiredMixin, View):
    """Staff queue for managing room service orders."""
    
    def get(self, request):
        # Check staff permission
        if not request.user.is_staff:
            return HttpResponseForbidden('Akses ditolak.')
        
        from django.db.models import Q, Count
        from django.shortcuts import render
        
        # Get filter parameters
        status_filter = request.GET.get('status', '')
        fulfillment_filter = request.GET.get('fulfillment', '')
        
        # Base queryset
        orders = ServiceOrder.objects.select_related(
            'user', 'booking', 'booking__room'
        ).prefetch_related('items').order_by('status', '-created_at')
        
        # Apply filters
        if status_filter:
            orders = orders.filter(status=status_filter)
        
        if fulfillment_filter:
            orders = orders.filter(fulfillment=fulfillment_filter)
        
        # Group orders by status
        incoming = orders.filter(status=ServiceOrder.STATUS_INCOMING)
        processing = orders.filter(status=ServiceOrder.STATUS_PROCESSING)
        completed = orders.filter(
            status__in=(ServiceOrder.STATUS_DELIVERED, ServiceOrder.STATUS_READY)
        )[:20]
        
        context = {
            'orders': orders[:50],
            'incoming_orders': incoming,
            'processing_orders': processing,
            'completed_orders': completed,
            'status_filter': status_filter,
            'fulfillment_filter': fulfillment_filter,
            'active_section': 'room_service_queue',
        }
        
        return render(request, 'chatbot/service_order_queue.html', context)
    
    def post(self, request):
        # Handle status updates
        if not request.user.is_staff:
            return HttpResponseForbidden('Akses ditolak.')
        
        from django.shortcuts import redirect
        from django.contrib import messages
        
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        
        if not order_id or not new_status:
            messages.error(request, 'Data tidak lengkap.')
            return redirect('service_order_queue')
        
        try:
            order = ServiceOrder.objects.get(pk=order_id)
            if order.transition_to(new_status, actor=request.user):
                messages.success(
                    request, 
                    f'Pesanan {order.order_code} berhasil diubah ke {order.get_status_display()}.'
                )
            else:
                messages.error(request, 'Transisi status tidak valid.')
        except ServiceOrder.DoesNotExist:
            messages.error(request, 'Pesanan tidak ditemukan.')
        except Exception as e:
            messages.error(request, f'Gagal mengubah status: {str(e)}')
        
        return redirect('service_order_queue')
