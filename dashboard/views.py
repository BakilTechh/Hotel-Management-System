from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.models import GuestProfile
from chatbot.models import ServiceOrder
from reservations.models import Booking, Payment, PromoVoucher
from rooms.models import Room, RoomType


class DashboardView(TemplateView):
	template_name = 'dashboard/home.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		rooms = list(Room.objects.select_related('room_type').all()[:3])
		room_types = RoomType.objects.all()
		bookings = Booking.objects.select_related('room').order_by('-created_at')

		showcase_rooms = [
			{
				'name': 'Kamar Deluxe King',
				'eyebrow': 'Pilihan populer',
				'price': '1.800.000',
				'capacity': '2 tamu',
				'size': '38 m2',
				'view': 'Pemandangan kota',
				'image': 'https://images.unsplash.com/photo-1566665797739-1674de7a421a?auto=format&fit=crop&w=1000&q=85',
				'description': 'Kamar hangat dengan jendela tinggi, tempat tidur king, dan ruang kerja yang tenang.',
			},
			{
				'name': 'Suite Eksekutif Horizon',
				'eyebrow': 'Suite unggulan',
				'price': '3.200.000',
				'capacity': '4 tamu',
				'size': '65 m2',
				'view': 'Kota dan matahari terbenam',
				'image': 'https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1000&q=85',
				'description': 'Suite luas dengan ruang duduk, bathtub, dan pemandangan kota dari ketinggian.',
			},
			{
				'name': 'Grand Suite Presidensial',
				'eyebrow': 'Eksklusif apex',
				'price': '5.500.000',
				'capacity': '4 tamu',
				'size': '110 m2',
				'view': 'Teras privat',
				'image': 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1000&q=85',
				'description': 'Ruang privat berkelas dengan teras luas, lounge, dan layanan personal sepanjang hari.',
			},
		]

		for index, room in enumerate(rooms):
			showcase_rooms[index]['database_room'] = room
			showcase_rooms[index]['price'] = f'{room.room_type.price_per_night:,.0f}'.replace(',', '.')

		context.update({
			'rooms': showcase_rooms,
			'room_types': room_types,
			'recent_bookings': bookings[:4],
			'room_count': Room.objects.count(),
			'booking_count': Booking.objects.count(),
			'paid_booking_count': Booking.objects.filter(status_pesanan='CONFIRMED').count(),
		})
		return context


class FacilitiesView(TemplateView):
	template_name = 'dashboard/facilities.html'


class OffersView(TemplateView):
	template_name = 'dashboard/offers.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		now = timezone.now()
		context['vouchers'] = (
			PromoVoucher.objects
			.filter(kuota_penggunaan__gt=0, tanggal_kedaluwarsa__gte=now)
			.order_by('tanggal_kedaluwarsa', 'kode_voucher')
		)
		return context


class AboutView(TemplateView):
	template_name = 'dashboard/about.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['room_count'] = Room.objects.filter(is_active=True).count()
		context['room_type_count'] = RoomType.objects.count()
		return context


class GuestDashboardView(LoginRequiredMixin, TemplateView):
	"""Personal overview for a signed-in guest.

	Shows the next/active stay, payment health, recent room-service orders and
	profile completeness in one place.
	"""

	template_name = 'dashboard/guest_dashboard.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user = self.request.user
		today = timezone.localdate()

		bookings = (
			Booking.objects.filter(user=user)
			.select_related('room', 'room__room_type', 'voucher', 'payment')
			.order_by('-created_at')
		)
		active_stay = bookings.filter(status_pesanan='CHECKED_IN').first()
		upcoming_stay = (
			bookings.filter(
				status_pesanan__in=('PENDING_PAYMENT', 'CONFIRMED'),
				tanggal_check_out__gte=today,
			)
			.order_by('tanggal_check_in')
			.first()
		)
		next_stay = active_stay or upcoming_stay

		payments = Payment.objects.filter(booking__user=user)
		payment_counts = {
			'paid': payments.filter(status_pembayaran='VERIFIED').count(),
			'pending': payments.filter(status_pembayaran__in=('UNPAID', 'PENDING_VERIFICATION')).count(),
			'refund': payments.filter(status_pembayaran__in=('REFUND_PENDING', 'REFUNDED')).count(),
		}
		total_paid = (
			payments.filter(status_pembayaran='VERIFIED')
			.aggregate(total=Sum('amount'))['total'] or 0
		)

		profile, _ = GuestProfile.objects.get_or_create(
			user=user,
			defaults={'role': 'ADMIN' if user.is_superuser else 'GUEST'},
		)
		recent_orders = (
			ServiceOrder.objects.filter(user=user)
			.prefetch_related('items')
			.order_by('-created_at')[:3]
		)

		context.update({
			'active_section': 'dashboard',
			'profile': profile,
			'active_stay': active_stay,
			'upcoming_stay': upcoming_stay,
			'next_stay': next_stay,
			'recent_bookings': bookings[:4],
			'booking_count': bookings.count(),
			'upcoming_count': bookings.filter(
				status_pesanan__in=('PENDING_PAYMENT', 'CONFIRMED'),
				tanggal_check_out__gte=today,
			).count(),
			'completed_count': bookings.filter(status_pesanan='CHECKED_OUT').count(),
			'reviewable_count': bookings.filter(
				status_pesanan='CHECKED_OUT', review__isnull=True,
			).count(),
			'payment_counts': payment_counts,
			'total_paid': total_paid,
			'recent_orders': recent_orders,
			'service_eligible_count': bookings.filter(
				status_pesanan__in=Booking.SERVICE_ELIGIBLE_STATUSES,
				tanggal_check_out__gte=today,
			).count(),
			'today': today,
		})
		return context


class ReportView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	template_name = 'dashboard/report.html'

	def test_func(self):
		return self.request.user.is_staff

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({
			'total_bookings': Booking.objects.count(),
			'confirmed_bookings': Booking.objects.filter(status_pesanan='CONFIRMED').count(),
			'checked_in_bookings': Booking.objects.filter(status_pesanan='CHECKED_IN').count(),
			'checked_out_bookings': Booking.objects.filter(status_pesanan='CHECKED_OUT').count(),
			'verified_payments': Payment.objects.filter(status_pembayaran='VERIFIED').count(),
			'refund_pending': Payment.objects.filter(status_pembayaran='REFUND_PENDING').count(),
			'clean_rooms': Room.objects.filter(status='CLEAN').count(),
			'dirty_rooms': Room.objects.filter(status='DIRTY').count(),
			'maintenance_rooms': Room.objects.filter(status='MAINTENANCE').count(),
		})
		return context


class HousekeepingView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Housekeeping dashboard for managing room status.
	
	Shows all rooms grouped by status and allows staff to update room status
	after cleaning or maintenance.
	"""
	
	template_name = 'dashboard/housekeeping.html'
	
	def test_func(self):
		"""Only staff and admin can access housekeeping."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		today = timezone.localdate()
		
		# Get all rooms with related data
		all_rooms = (
			Room.objects
			.select_related('room_type')
			.prefetch_related('bookings')
			.order_by('floor', 'number')
		)
		
		# Group rooms by status
		clean_rooms = all_rooms.filter(status='CLEAN')
		dirty_rooms = all_rooms.filter(status='DIRTY')
		maintenance_rooms = all_rooms.filter(status='MAINTENANCE')
		
		# Get rooms with upcoming check-ins today
		checking_in_today = (
			Booking.objects
			.filter(
				status_pesanan='CONFIRMED',
				tanggal_check_in=today,
			)
			.select_related('room', 'room__room_type', 'user')
			.order_by('room__number')
		)
		
		# Get rooms with current check-outs today
		checking_out_today = (
			Booking.objects
			.filter(
				status_pesanan='CHECKED_IN',
				tanggal_check_out=today,
			)
			.select_related('room', 'room__room_type', 'user')
			.order_by('room__number')
		)
		
		context.update({
			'clean_rooms': clean_rooms,
			'dirty_rooms': dirty_rooms,
			'maintenance_rooms': maintenance_rooms,
			'clean_count': clean_rooms.count(),
			'dirty_count': dirty_rooms.count(),
			'maintenance_count': maintenance_rooms.count(),
			'checking_in_today': checking_in_today,
			'checking_out_today': checking_out_today,
			'total_rooms': all_rooms.count(),
			'today': today,
		})
		return context


class HousekeepingUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
	"""Handle room status updates from housekeeping staff."""
	
	def test_func(self):
		"""Only staff and admin can update room status."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def post(self, request, *args, **kwargs):
		room_id = request.POST.get('room_id')
		new_status = request.POST.get('status')
		
		if not room_id or not new_status:
			messages.error(request, 'Data tidak lengkap.')
			return redirect('housekeeping')
		
		if new_status not in dict(Room.STATUS_CHOICES):
			messages.error(request, 'Status tidak valid.')
			return redirect('housekeeping')
		
		try:
			room = get_object_or_404(Room, pk=room_id)
			old_status = room.get_status_display()
			room.status = new_status
			room.save(update_fields=['status'])
			
			messages.success(
				request,
				f'Status kamar {room.number} berhasil diubah dari {old_status} ke {room.get_status_display()}.'
			)
		except Exception as e:
			messages.error(request, f'Gagal mengubah status kamar: {str(e)}')
		
		return redirect('housekeeping')
