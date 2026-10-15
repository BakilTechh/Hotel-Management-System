from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, RedirectView
from django.urls import reverse, reverse_lazy
from .models import Booking, Payment, Review
from .forms import BookingForm, PaymentForm, ReviewForm

# Mewarisi CreateView dari Django untuk OOP yang lebih rapi
class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    form_class = BookingForm
    template_name = 'reservations/booking_form.html' # Mutia bakal bikin ui di sini

    def get_initial(self):
        initial = super().get_initial()
        room_id = self.request.GET.get('room')
        if room_id:
            initial['room'] = room_id
        return initial
    
    def form_valid(self, form):
        # Otomatis ngisi user yang sedang login
        form.instance.user = self.request.user
        response = super().form_valid(form)
        # Menghitung total harga otomatis (enkapsulasi)
        self.object.hitung_total_biaya()
        # Kurangi kuota voucher kalau memang dipakai
        self.object.konsumsi_voucher()
        self.object.ensure_payment()
        return response

    def get_success_url(self):
        return reverse_lazy('booking_detail', kwargs={'pk': self.object.pk})

class BookingDetailView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'reservations/booking_detail.html' # Mutia bakal bikin UI-nya di sini

    def get_queryset(self):
        if self.request.user.is_staff:
            return Booking.objects.select_related('room', 'payment')
        return Booking.objects.filter(user=self.request.user).select_related('room', 'payment')

class BookingListView(LoginRequiredMixin, ListView):
    """Riwayat pemesanan milik tamu yang sedang login ("Pemesanan Saya")."""
    model = Booking
    template_name = 'reservations/booking_list.html'
    context_object_name = 'bookings'

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            'room', 'room__room_type', 'payment'
        ).order_by('-created_at')

class BookingLatestView(LoginRequiredMixin, RedirectView):
    """Lompat ke rincian reservasi terbaru ("Rincian Pemesanan")."""
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        latest = Booking.objects.filter(user=self.request.user).order_by('-created_at').first()
        if latest is None:
            return reverse('booking_list')
        return reverse('booking_detail', kwargs={'pk': latest.pk})


class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        if booking.batalkan_pesanan():
            messages.success(request, 'Reservasi berhasil dibatalkan.')
        else:
            messages.error(request, 'Reservasi ini sudah tidak dapat dibatalkan.')
        return redirect('booking_detail', pk=booking.pk)

class PaymentCreateView(LoginRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'reservations/payment_form.html'

    def post(self, request, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=kwargs['booking_id'], user=request.user)
        payment = Payment.objects.filter(booking=booking).first()
        if booking.status_pesanan != 'PENDING_PAYMENT' or payment and payment.status_pembayaran not in ('UNPAID', 'REJECTED'):
            messages.error(request, 'Booking ini tidak dapat menerima pembayaran baru.')
            return redirect('booking_detail', pk=booking.pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        booking = Booking.objects.get(pk=self.kwargs['booking_id'], user=self.request.user)
        payment = Payment.objects.filter(booking=booking).first()
        if payment is not None:
            form.instance = payment
        form.instance.booking = booking
        form.instance.amount = booking.total_biaya_akhir
        # Bukti diunggah → tandai menunggu verifikasi manual oleh staf.
        form.instance.status_pembayaran = 'PENDING_VERIFICATION'
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('booking_detail', kwargs={'pk': self.object.booking.pk})


class ReviewCreateView(LoginRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = 'reservations/review_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(Booking, pk=kwargs['booking_id'], user=request.user)
        if self.booking.status_pesanan != 'CHECKED_OUT':
            messages.error(request, 'Review hanya dapat diberikan setelah check-out.')
            return redirect('booking_detail', pk=self.booking.pk)
        if Review.objects.filter(booking=self.booking).exists():
            messages.error(request, 'Review untuk booking ini sudah pernah diberikan.')
            return redirect('booking_detail', pk=self.booking.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.booking = self.booking
        form.instance.guest = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('booking_detail', kwargs={'pk': self.booking.pk})


class ReceptionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Halaman resepsionis untuk check-in / check-out tamu.

    Hanya staf (is_staff) atau akun dengan role ADMIN yang boleh mengakses.
    Check-in hanya boleh dilakukan pada atau setelah tanggal check-in booking.
    """

    template_name = 'reservations/reception.html'

    def test_func(self):
        user = self.request.user
        role = getattr(getattr(user, 'guest_profile', None), 'role', None)
        return user.is_staff or role == 'ADMIN'

    def get(self, request, *args, **kwargs):
        today = timezone.localdate()
        arriving = Booking.objects.filter(
            status_pesanan='CONFIRMED'
        ).select_related('room', 'room__room_type', 'user').order_by('tanggal_check_in')
        in_house = Booking.objects.filter(
            status_pesanan='CHECKED_IN'
        ).select_related('room', 'room__room_type', 'user').order_by('tanggal_check_out')
        context = {
            'arriving': arriving,
            'in_house': in_house,
            'today': today,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        booking = get_object_or_404(
            Booking.objects.select_related('room'), pk=request.POST.get('booking_id')
        )
        action = request.POST.get('action')
        today = timezone.localdate()

        if action == 'check_in':
            if booking.status_pesanan != 'CONFIRMED':
                messages.error(request, 'Hanya booking berstatus Confirmed yang dapat check-in.')
            elif today < booking.tanggal_check_in:
                messages.error(
                    request,
                    f'Belum waktunya check-in. Dijadwalkan {booking.tanggal_check_in:%d %b %Y}.'
                )
            elif booking.check_in():
                messages.success(request, f'Booking NH-{booking.pk:04d} berhasil check-in.')
            else:
                messages.error(request, 'Check-in gagal. Periksa kembali status booking.')
        elif action == 'check_out':
            if booking.check_out():
                messages.success(
                    request,
                    f'Booking NH-{booking.pk:04d} berhasil check-out. Kamar ditandai Dirty.'
                )
            else:
                messages.error(request, 'Hanya tamu yang sedang menginap yang dapat check-out.')
        else:
            messages.error(request, 'Aksi tidak dikenali.')

        return redirect('reception')