import hashlib
import hmac
import json
import logging
import mimetypes
import os
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, RedirectView

from rooms.models import Room

from .forms import BookingForm, PaymentForm, ReviewForm
from .models import Booking, BookingModification, Payment, Review
from .services import (
    InvalidTransition,
    ModificationError,
    PaymentError,
    apply_booking_modification,
    calculate_cancellation_refund,
    cancel_booking_with_policy,
    process_gateway_event,
    request_booking_modification,
    submit_payment_proof,
)

logger = logging.getLogger(__name__)


class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    form_class = BookingForm
    template_name = 'reservations/booking_form.html'

    def get_initial(self):
        initial = super().get_initial()
        for key in ('room', 'check_in', 'check_out'):
            value = self.request.GET.get(key)
            if value:
                initial['room' if key == 'room' else f'tanggal_{key}'] = value
        guests = self.request.GET.get('guests')
        if guests and guests.isdigit():
            initial['jumlah_tamu'] = int(guests)
        return initial

    def form_valid(self, form):
        """Create the booking, price it and its payment in one transaction.

        The room row is locked and availability is checked again so two guests
        cannot book the same room through a simultaneous request.
        """
        return self._create_booking(form)

    @transaction.atomic
    def _create_booking(self, form):
        check_in = form.cleaned_data['tanggal_check_in']
        check_out = form.cleaned_data['tanggal_check_out']
        
        # Lock the room first to prevent concurrent bookings
        room = (
            Room.objects.select_for_update()
            .select_related('room_type')
            .get(pk=form.cleaned_data['room'].pk)
        )
        
        # Verify room is in bookable status
        if not room.is_active:
            form.add_error(None, 'Kamar ini tidak aktif dan tidak dapat dipesan.')
            return self.form_invalid(form)
        
        if room.status != 'CLEAN':
            form.add_error(None, f'Kamar ini dalam status {room.get_status_display()} dan tidak dapat dipesan saat ini.')
            return self.form_invalid(form)
        
        # Verify guest count doesn't exceed capacity
        jumlah_tamu = form.cleaned_data.get('jumlah_tamu', 1)
        if jumlah_tamu > room.room_type.capacity:
            form.add_error('jumlah_tamu', f'Kamar ini hanya menampung maksimal {room.room_type.capacity} tamu.')
            return self.form_invalid(form)
        
        # Check availability with locked room
        if not Booking.available_rooms(check_in, check_out).filter(pk=room.pk).exists():
            form.add_error(None, 'Kamar tidak tersedia pada periode tersebut.')
            return self.form_invalid(form)
        
        form.instance.room = room
        form.instance.user = self.request.user

        try:
            # Create booking first
            self.object = form.save()
            
            # Calculate pricing
            self.object.hitung_total_biaya()
            
            # Consume voucher quota if applicable (with locking)
            # This must happen before ensure_payment to get the final price
            if self.object.voucher_id and getattr(self.object, '_voucher_applied', False):
                voucher = (
                    form.cleaned_data.get('voucher')
                    if 'voucher' in form.cleaned_data
                    else self.object.voucher
                )
                if voucher:
                    self.object.konsumsi_voucher()
            
            # Create payment record
            self.object.ensure_payment()
            
        except ValidationError as exc:
            form.add_error(None, exc.messages[0] if exc.messages else str(exc))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f'Reservasi {self.object.booking_code} berhasil dibuat. '
            'Selesaikan pembayaran untuk mengunci kamar Anda.',
        )
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('booking_detail', kwargs={'pk': self.object.pk})


class BookingDetailView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'reservations/booking_detail.html'

    def get_queryset(self):
        queryset = (
            Booking.objects.select_related(
                'room', 'room__room_type', 'voucher', 'payment',
            )
            .prefetch_related('service_orders__items')
        )
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = self.object
        context.update({
            'active_section': 'bookings',
            'nights': booking.durasi_malam,
            'can_review': booking.review_allowed,
            'can_pay': (
                booking.status_pesanan == 'PENDING_PAYMENT'
                and (
                    booking.payment_record is None
                    or booking.payment_record.status_pembayaran in (
                        Payment.UNPAID, Payment.REJECTED, Payment.FAILED,
                    )
                )
            ),
            'service_orders': booking.service_orders.all()[:5],
        })
        return context


class BookingListView(LoginRequiredMixin, ListView):
    """Guest booking history with clear payment status and filters."""

    model = Booking
    template_name = 'reservations/booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 12

    def get_queryset(self):
        today = timezone.localdate()
        queryset = (
            Booking.objects.filter(user=self.request.user)
            .select_related('room', 'room__room_type', 'voucher', 'payment')
            .prefetch_related('service_orders__items')
        )
        selected = self.request.GET.get('filter', 'all')
        search = self.request.GET.get('q', '').strip()

        if selected == 'upcoming':
            queryset = queryset.filter(
                status_pesanan__in=('PENDING_PAYMENT', 'CONFIRMED', 'CHECKED_IN'),
                tanggal_check_out__gte=today,
            ).order_by('tanggal_check_in')
        elif selected == 'pending_payment':
            queryset = queryset.filter(
                status_pesanan='PENDING_PAYMENT',
                tanggal_check_out__gte=today,
            ).order_by('tanggal_check_in')
        elif selected == 'completed':
            queryset = queryset.filter(status_pesanan='CHECKED_OUT').order_by('-tanggal_check_out')
        elif selected == 'cancelled':
            queryset = queryset.filter(status_pesanan='CANCELLED').order_by('-created_at')
        else:
            selected = 'all'
            queryset = queryset.order_by('-created_at')

        if search:
            if search.isdigit():
                queryset = queryset.filter(pk=int(search))
            else:
                queryset = queryset.filter(room__number__icontains=search)

        self.selected_filter = selected
        self.search = search
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        all_bookings = Booking.objects.filter(user=self.request.user)
        context.update({
            'active_section': 'bookings',
            'current_filter': self.selected_filter,
            'search': self.search,
            'total_count': all_bookings.count(),
            'upcoming_count': all_bookings.filter(
                status_pesanan__in=('PENDING_PAYMENT', 'CONFIRMED', 'CHECKED_IN'),
                tanggal_check_out__gte=today,
            ).count(),
            'pending_payment_count': all_bookings.filter(
                status_pesanan='PENDING_PAYMENT',
                tanggal_check_out__gte=today,
            ).count(),
            'completed_count': all_bookings.filter(status_pesanan='CHECKED_OUT').count(),
            'cancelled_count': all_bookings.filter(status_pesanan='CANCELLED').count(),
        })
        return context


class BookingLatestView(LoginRequiredMixin, RedirectView):
    """Redirect to the most recent reservation detail."""

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        latest = Booking.objects.filter(user=self.request.user).order_by('-created_at').first()
        if latest is None:
            return reverse('booking_list')
        return reverse('booking_detail', kwargs={'pk': latest.pk})


class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        payment = booking.payment_record
        was_paid = payment is not None and payment.status_pembayaran == Payment.VERIFIED
        if booking.batalkan_pesanan():
            if was_paid:
                messages.success(
                    request,
                    'Reservasi dibatalkan. Pembayaran Anda masuk antrean pengembalian dana; '
                    'tim kami akan memprosesnya.',
                )
            else:
                messages.success(request, 'Reservasi berhasil dibatalkan.')
        else:
            messages.error(request, 'Reservasi ini sudah tidak dapat dibatalkan.')
        return redirect('booking_detail', pk=booking.pk)


class PaymentCreateView(LoginRequiredMixin, View):
    """Upload payment proof for a pending booking.

    All mutations go through :func:`reservations.services.submit_payment_proof`,
    which locks the records and re-checks every state transition server-side.
    """

    template_name = 'reservations/payment_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(
            Booking.objects.select_related('room', 'room__room_type', 'payment'),
            pk=kwargs['booking_id'],
            user=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def _can_pay(self):
        payment = self.booking.payment_record
        return (
            self.booking.status_pesanan == 'PENDING_PAYMENT'
            and (
                payment is None
                or payment.status_pembayaran in (
                    Payment.UNPAID, Payment.REJECTED, Payment.FAILED,
                )
            )
        )

    def _context(self, form):
        return {
            'active_section': 'bookings',
            'booking': self.booking,
            'form': form,
            'payment': self.booking.payment_record,
        }

    def get(self, request, *args, **kwargs):
        if not self._can_pay():
            messages.error(request, 'Booking ini tidak dapat menerima pembayaran baru.')
            return redirect('booking_detail', pk=self.booking.pk)
        form = PaymentForm(instance=self.booking.payment_record)
        return render(request, self.template_name, self._context(form))

    def post(self, request, *args, **kwargs):
        if not self._can_pay():
            messages.error(request, 'Booking ini tidak dapat menerima pembayaran baru.')
            return redirect('booking_detail', pk=self.booking.pk)

        form = PaymentForm(
            request.POST, request.FILES, instance=self.booking.payment_record,
        )
        if form.is_valid():
            try:
                submit_payment_proof(
                    self.booking,
                    metode_pembayaran=form.cleaned_data['metode_pembayaran'],
                    proof=form.cleaned_data.get('bukti_transfer_url'),
                    actor=request.user,
                )
            except PaymentError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    'Bukti pembayaran diterima. Tim kami akan memverifikasi '
                    'dalam 1×24 jam pada hari kerja.',
                )
                return redirect('booking_detail', pk=self.booking.pk)

        return render(request, self.template_name, self._context(form))


class PaymentProofView(LoginRequiredMixin, View):
    """Serve payment proofs only to the booking owner and hotel staff.

    Media files are otherwise publicly addressable through MEDIA_URL during
    development; bank transfer receipts should not be.
    """

    def get(self, request, pk, *args, **kwargs):
        payment = get_object_or_404(
            Payment.objects.select_related('booking'), pk=pk,
        )
        if not (request.user.is_staff or payment.booking.user_id == request.user.pk):
            raise PermissionDenied('Anda tidak berhak melihat bukti pembayaran ini.')
        if not payment.bukti_transfer_url:
            raise Http404('Bukti pembayaran tidak tersedia.')

        try:
            path = payment.bukti_transfer_url.path
        except (ValueError, NotImplementedError) as exc:
            raise Http404('Bukti pembayaran tidak tersedia.') from exc
        if not os.path.isfile(path):
            raise Http404('File bukti pembayaran tidak ditemukan.')

        content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        response = FileResponse(
            open(path, 'rb'),
            content_type=content_type,
            as_attachment=False,
            filename=os.path.basename(path),
        )
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'private, no-store'
        return response


class ReviewCreateView(LoginRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = 'reservations/review_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(
            Booking, pk=kwargs['booking_id'], user=request.user,
        )
        if self.booking.status_pesanan != 'CHECKED_OUT':
            messages.error(request, 'Review hanya dapat diberikan setelah check-out.')
            return redirect('booking_detail', pk=self.booking.pk)
        if Review.objects.filter(booking=self.booking).exists():
            messages.error(request, 'Review untuk booking ini sudah pernah diberikan.')
            return redirect('booking_detail', pk=self.booking.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'active_section': 'bookings', 'booking': self.booking})
        return context

    def form_valid(self, form):
        form.instance.booking = self.booking
        form.instance.guest = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            'Terima kasih! Ulasan Anda sudah tayang di halaman Ulasan Tamu.',
        )
        return response

    def get_success_url(self):
        return reverse('booking_detail', kwargs={'pk': self.booking.pk})


class ReceptionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Reception desk for check-in / check-out."""

    template_name = 'reservations/reception.html'

    def test_func(self):
        user = self.request.user
        role = getattr(getattr(user, 'guest_profile', None), 'role', None)
        return user.is_staff or role == 'ADMIN'

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        arriving = (
            Booking.objects.filter(status_pesanan='CONFIRMED')
            .select_related('room', 'room__room_type', 'user')
            .order_by('tanggal_check_in')
        )
        in_house = (
            Booking.objects.filter(status_pesanan='CHECKED_IN')
            .select_related('room', 'room__room_type', 'user')
            .order_by('tanggal_check_out')
        )
        context = {
            'arriving': arriving,
            'in_house': in_house,
            'today': today,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        booking = get_object_or_404(
            Booking.objects.select_related('room'), pk=request.POST.get('booking_id'),
        )
        action = request.POST.get('action')
        today = timezone.localdate()
        now = timezone.now()

        if action == 'check_in':
            if booking.status_pesanan != 'CONFIRMED':
                messages.error(request, 'Hanya booking berstatus Confirmed yang dapat check-in.')
            elif today < booking.tanggal_check_in:
                messages.error(
                    request,
                    f'Belum waktunya check-in. Dijadwalkan {booking.tanggal_check_in:%d %b %Y}.',
                )
            elif today > booking.tanggal_check_out:
                messages.error(
                    request,
                    f'Periode reservasi sudah berakhir ({booking.tanggal_check_out:%d %b %Y}). '
                    'Buat reservasi baru atau hubungi manajemen.',
                )
            elif booking.room.status != 'CLEAN':
                messages.error(
                    request,
                    f'Kamar {booking.room.number} belum siap (status: {booking.room.get_status_display()}). '
                    'Pastikan housekeeping sudah menyelesaikan persiapan.',
                )
            elif booking.check_in():
                messages.success(request, f'Booking {booking.booking_code} berhasil check-in.')
            else:
                messages.error(request, 'Check-in gagal. Periksa kembali status booking.')
        elif action == 'check_out':
            if booking.status_pesanan != 'CHECKED_IN':
                messages.error(request, 'Hanya tamu yang sedang menginap yang dapat check-out.')
            elif today > booking.tanggal_check_out:
                # Allow late checkout but show warning
                if booking.check_out():
                    messages.warning(
                        request,
                        f'Booking {booking.booking_code} berhasil check-out (terlambat {(today - booking.tanggal_check_out).days} hari). '
                        'Kamar ditandai Dirty.',
                    )
                else:
                    messages.error(request, 'Check-out gagal.')
            elif booking.check_out():
                messages.success(
                    request,
                    f'Booking {booking.booking_code} berhasil check-out. Kamar ditandai Dirty.',
                )
            else:
                messages.error(request, 'Check-out gagal. Periksa kembali status booking.')
        else:
            messages.error(request, 'Aksi tidak dikenali.')

        return redirect('reception')


class PaymentVerificationView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Staff payment verification queue showing pending payments."""
    
    model = Payment
    template_name = 'reservations/payment_verification.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def test_func(self):
        """Only staff and admin can verify payments."""
        user = self.request.user
        role = getattr(getattr(user, 'guest_profile', None), 'role', None)
        return user.is_staff or role in ('STAFF', 'ADMIN')
    
    def get_queryset(self):
        queryset = (
            Payment.objects
            .select_related('booking', 'booking__user', 'booking__room', 'booking__room__room_type')
            .order_by('-created_at')
        )
        
        status_filter = self.request.GET.get('status', 'pending')
        
        if status_filter == 'pending':
            queryset = queryset.filter(status_pembayaran=Payment.PENDING_VERIFICATION)
        elif status_filter == 'verified':
            queryset = queryset.filter(status_pembayaran=Payment.VERIFIED)
        elif status_filter == 'rejected':
            queryset = queryset.filter(status_pembayaran=Payment.REJECTED)
        elif status_filter == 'refund':
            queryset = queryset.filter(status_pembayaran__in=[Payment.REFUND_PENDING, Payment.REFUNDED])
        
        self.status_filter = status_filter
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_filter': self.status_filter,
            'pending_count': Payment.objects.filter(status_pembayaran=Payment.PENDING_VERIFICATION).count(),
            'verified_count': Payment.objects.filter(status_pembayaran=Payment.VERIFIED).count(),
            'rejected_count': Payment.objects.filter(status_pembayaran=Payment.REJECTED).count(),
            'refund_count': Payment.objects.filter(
                status_pembayaran__in=[Payment.REFUND_PENDING, Payment.REFUNDED]
            ).count(),
        })
        return context


class PaymentVerifyActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Handle payment approval/rejection actions."""
    
    def test_func(self):
        """Only staff and admin can verify payments."""
        user = self.request.user
        role = getattr(getattr(user, 'guest_profile', None), 'role', None)
        return user.is_staff or role in ('STAFF', 'ADMIN')
    
    def post(self, request, *args, **kwargs):
        payment_id = request.POST.get('payment_id')
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()
        
        if not payment_id or not action:
            messages.error(request, 'Data tidak lengkap.')
            return redirect('payment_verification')
        
        try:
            payment = get_object_or_404(Payment, pk=payment_id)
            
            if action == 'approve':
                verify_payment(payment, approved=True, actor=request.user)
                messages.success(
                    request,
                    f'Pembayaran untuk booking {payment.booking.booking_code} telah disetujui. '
                    'Booking sekarang berstatus Confirmed.'
                )
            elif action == 'reject':
                if not reason:
                    reason = 'Bukti pembayaran tidak valid atau tidak sesuai.'
                verify_payment(payment, approved=False, actor=request.user, reason=reason)
                messages.warning(
                    request,
                    f'Pembayaran untuk booking {payment.booking.booking_code} ditolak. '
                    'Tamu dapat mengupload bukti pembayaran baru.'
                )
            elif action == 'request_refund':
                if not reason:
                    reason = 'Permintaan refund dari staff.'
                from .services import request_refund
                request_refund(payment, actor=request.user, reason=reason)
                messages.success(
                    request,
                    f'Pembayaran untuk booking {payment.booking.booking_code} ditandai untuk refund.'
                )
            elif action == 'complete_refund':
                if not reason:
                    reason = 'Refund selesai diproses.'
                from .services import complete_refund
                complete_refund(payment, actor=request.user, reason=reason)
                messages.success(
                    request,
                    f'Refund untuk booking {payment.booking.booking_code} telah diselesaikan.'
                )
            else:
                messages.error(request, 'Aksi tidak dikenali.')
        
        except InvalidTransition as exc:
            messages.error(request, str(exc))
        except Exception as e:
            logger.exception('Error processing payment verification')
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
        
        return redirect('payment_verification')


@csrf_exempt
@require_POST
def payment_webhook(request):
    """Signed, idempotent webhook endpoint for a payment provider.

    The provider signs the raw request body with ``PAYMENT_WEBHOOK_SECRET``
    (HMAC-SHA256) and sends it in ``X-Nocturn-Signature``.  The endpoint is
    deliberately disabled when no secret is configured.
    """
    secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
    if not secret:
        return JsonResponse(
            {'detail': 'Webhook pembayaran belum dikonfigurasi.'}, status=503,
        )

    signature = request.headers.get('X-Nocturn-Signature', '').strip()
    if signature.startswith('sha256='):
        signature = signature[len('sha256='):]
    expected = hmac.new(secret.encode('utf-8'), request.body, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        return JsonResponse({'detail': 'Signature tidak valid.'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Payload bukan JSON yang valid.'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'detail': 'Payload harus berupa objek JSON.'}, status=400)

    event_id = str(payload.get('event_id') or '').strip()
    event_type = str(payload.get('type') or payload.get('event') or '').strip()
    provider = str(payload.get('provider') or 'generic').strip()[:30]
    if not event_id or not event_type:
        return JsonResponse(
            {'detail': 'event_id dan type wajib diisi.'}, status=400,
        )

    try:
        event, outcome = process_gateway_event(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
    except InvalidTransition as exc:
        logger.warning('Payment webhook rejected: %s', exc)
        return JsonResponse({'status': 'rejected', 'detail': str(exc)}, status=409)
    except Exception:  # pragma: no cover - defensive boundary for providers
        logger.exception('Unexpected error processing payment webhook')
        return JsonResponse({'detail': 'Webhook gagal diproses.'}, status=500)

    return JsonResponse({'status': outcome, 'event_id': event.event_id})



class BookingModificationView(LoginRequiredMixin, DetailView):
    """Display all modifications made to a booking."""
    
    model = Booking
    template_name = 'reservations/booking_modifications.html'
    
    def get_queryset(self):
        queryset = Booking.objects.prefetch_related('modifications')
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = self.object
        
        # Calculate cancellation refund info
        refund_amount, refund_pct, policy_reason = calculate_cancellation_refund(booking)
        
        context.update({
            'active_section': 'bookings',
            'modifications': booking.modifications.all().order_by('-created_at'),
            'can_modify': booking.status_pesanan in ('PENDING_PAYMENT', 'CONFIRMED'),
            'refund_amount': refund_amount,
            'refund_percentage': refund_pct,
            'cancellation_policy': policy_reason,
        })
        return context


class BookingModifyRequestView(LoginRequiredMixin, View):
    """Handle booking modification requests from guests."""
    
    template_name = 'reservations/booking_modify.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(
            Booking.objects.select_related('room', 'room__room_type'),
            pk=kwargs['pk'],
        )
        
        # Authorization: own booking or staff
        if not (request.user.is_staff or self.booking.user_id == request.user.pk):
            raise PermissionDenied('Anda tidak berhak mengubah reservasi ini.')
        
        # Can only modify pending/confirmed bookings
        if self.booking.status_pesanan not in ('PENDING_PAYMENT', 'CONFIRMED'):
            messages.error(request, 'Booking ini tidak dapat diubah.')
            return redirect('booking_detail', pk=self.booking.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        available_rooms = Booking.available_rooms(
            self.booking.tanggal_check_in,
            self.booking.tanggal_check_out,
        ).exclude(pk=self.booking.room_id)
        
        # Calculate cancellation refund
        refund_amount, refund_pct, policy_reason = calculate_cancellation_refund(self.booking)
        
        context = {
            'active_section': 'bookings',
            'booking': self.booking,
            'available_rooms': available_rooms,
            'today': today,
            'min_checkin': today + timedelta(days=1),
            'refund_amount': refund_amount,
            'refund_percentage': refund_pct,
            'cancellation_policy': policy_reason,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        modification_type = request.POST.get('modification_type')
        
        try:
            if modification_type == 'DATE_CHANGE':
                new_check_in = request.POST.get('new_check_in')
                new_check_out = request.POST.get('new_check_out')
                
                # Parse dates
                from datetime import datetime
                new_check_in = datetime.strptime(new_check_in, '%Y-%m-%d').date() if new_check_in else None
                new_check_out = datetime.strptime(new_check_out, '%Y-%m-%d').date() if new_check_out else None
                
                if not new_check_in and not new_check_out:
                    raise ModificationError('Tanggal check-in atau check-out baru harus diisi.')
                
                if new_check_out and new_check_out <= (new_check_in or self.booking.tanggal_check_in):
                    raise ModificationError('Tanggal check-out harus setelah check-in.')
                
                modification = request_booking_modification(
                    self.booking,
                    modification_type='DATE_CHANGE',
                    new_check_in=new_check_in,
                    new_check_out=new_check_out,
                    actor=request.user,
                    notes=request.POST.get('notes', ''),
                )
                
            elif modification_type == 'ROOM_CHANGE':
                new_room_id = request.POST.get('new_room')
                if not new_room_id:
                    raise ModificationError('Kamar baru harus dipilih.')
                
                new_room = get_object_or_404(Room, pk=new_room_id)
                
                # Check availability
                available = Booking.available_rooms(
                    self.booking.tanggal_check_in,
                    self.booking.tanggal_check_out,
                ).filter(pk=new_room.pk).exists()
                
                if not available:
                    raise ModificationError('Kamar yang dipilih tidak tersedia pada periode ini.')
                
                modification = request_booking_modification(
                    self.booking,
                    modification_type='ROOM_CHANGE',
                    new_room=new_room,
                    actor=request.user,
                    notes=request.POST.get('notes', ''),
                )
            
            elif modification_type == 'GUEST_COUNT':
                new_guest_count = int(request.POST.get('new_guest_count', 0))
                if new_guest_count <= 0:
                    raise ModificationError('Jumlah tamu harus lebih dari 0.')
                
                if new_guest_count > self.booking.room.room_type.capacity:
                    raise ModificationError(
                        f'Kamar ini hanya menampung maksimal {self.booking.room.room_type.capacity} tamu.'
                    )
                
                modification = request_booking_modification(
                    self.booking,
                    modification_type='GUEST_COUNT',
                    new_guest_count=new_guest_count,
                    actor=request.user,
                    notes=request.POST.get('notes', ''),
                )
            
            elif modification_type == 'EARLY_CHECKIN':
                modification = request_booking_modification(
                    self.booking,
                    modification_type='EARLY_CHECKIN',
                    actor=request.user,
                    notes=request.POST.get('notes', ''),
                )
            
            elif modification_type == 'LATE_CHECKOUT':
                modification = request_booking_modification(
                    self.booking,
                    modification_type='LATE_CHECKOUT',
                    actor=request.user,
                    notes=request.POST.get('notes', ''),
                )
            
            elif modification_type == 'CANCEL_WITH_REFUND':
                refund_amount, policy_reason = cancel_booking_with_policy(
                    self.booking,
                    actor=request.user,
                    reason=request.POST.get('notes', ''),
                )
                
                if refund_amount > 0:
                    messages.success(
                        request,
                        f'Booking dibatalkan. Refund sebesar Rp {refund_amount:,.0f} '
                        f'akan diproses sesuai kebijakan: {policy_reason}'
                    )
                else:
                    messages.warning(
                        request,
                        f'Booking dibatalkan. {policy_reason}'
                    )
                
                return redirect('booking_detail', pk=self.booking.pk)
            
            else:
                raise ModificationError('Tipe modifikasi tidak dikenali.')
            
            # Show success message
            if modification.status == 'APPROVED':
                if modification.total_cost > 0:
                    messages.success(
                        request,
                        f'Permintaan perubahan disetujui. Biaya tambahan: Rp {modification.total_cost:,.0f}. '
                        'Silakan selesaikan pembayaran untuk menerapkan perubahan.'
                    )
                else:
                    messages.success(
                        request,
                        'Permintaan perubahan disetujui dan dapat langsung diterapkan.'
                    )
                    # Auto-apply if no additional cost
                    apply_booking_modification(modification, actor=request.user)
                    messages.success(request, 'Perubahan berhasil diterapkan pada booking Anda.')
            else:
                messages.info(
                    request,
                    'Permintaan perubahan Anda telah dikirim dan menunggu persetujuan staff.'
                )
            
        except ModificationError as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            logger.exception('Error processing booking modification')
            messages.error(request, f'Terjadi kesalahan: {str(exc)}')
        
        return redirect('booking_modifications', pk=self.booking.pk)
