from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from datetime import timedelta

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
		from django.db.models import Count, Sum, Q
		from django.db.models.functions import TruncDate
		from datetime import timedelta
		
		today = timezone.localdate()
		thirty_days_ago = today - timedelta(days=30)
		
		# Basic counts
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
		
		# Revenue metrics
		total_revenue = Payment.objects.filter(
			status_pembayaran='VERIFIED'
		).aggregate(total=Sum('amount'))['total'] or 0
		
		revenue_30_days = Payment.objects.filter(
			status_pembayaran='VERIFIED',
			verified_at__gte=thirty_days_ago
		).aggregate(total=Sum('amount'))['total'] or 0
		
		context.update({
			'total_revenue': total_revenue,
			'revenue_30_days': revenue_30_days,
		})
		
		# Booking status distribution for chart
		status_distribution = Booking.objects.values('status_pesanan').annotate(
			count=Count('id')
		).order_by('status_pesanan')
		
		context['status_distribution'] = list(status_distribution)
		
		# Recent bookings trend (last 30 days)
		bookings_trend = Booking.objects.filter(
			created_at__gte=thirty_days_ago
		).annotate(
			date=TruncDate('created_at')
		).values('date').annotate(
			count=Count('id')
		).order_by('date')
		
		context['bookings_trend'] = list(bookings_trend)
		
		# Occupancy rate
		total_rooms = Room.objects.filter(is_active=True).count()
		occupied_rooms = Booking.objects.filter(
			status_pesanan='CHECKED_IN',
			tanggal_check_in__lte=today,
			tanggal_check_out__gt=today
		).count()
		
		context.update({
			'total_rooms': total_rooms,
			'occupied_rooms': occupied_rooms,
			'occupancy_rate': round((occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0, 1),
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



class GuestDirectoryView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Searchable guest directory for staff."""
	
	template_name = 'dashboard/guest_directory.html'
	
	def test_func(self):
		"""Only staff and admin can access guest directory."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		from django.contrib.auth import get_user_model
		from django.db.models import Count, Sum, Q
		
		context = super().get_context_data(**kwargs)
		User = get_user_model()
		
		# Get search query
		search_query = self.request.GET.get('q', '').strip()
		
		# Base queryset - all guests (non-staff users)
		guests = User.objects.filter(
			is_staff=False
		).select_related('guest_profile').annotate(
			booking_count=Count('bookings'),
			total_spent=Sum(
				'bookings__payment__amount',
				filter=Q(bookings__payment__status_pembayaran='VERIFIED')
			)
		).order_by('-date_joined')
		
		# Apply search filter
		if search_query:
			guests = guests.filter(
				Q(username__icontains=search_query) |
				Q(email__icontains=search_query) |
				Q(first_name__icontains=search_query) |
				Q(last_name__icontains=search_query) |
				Q(guest_profile__phone_number__icontains=search_query)
			)
		
		context.update({
			'guests': guests[:100],  # Limit to 100 results
			'search_query': search_query,
			'total_guests': User.objects.filter(is_staff=False).count(),
		})
		
		return context


class GuestDetailView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Detailed view of a single guest for staff."""
	
	template_name = 'dashboard/guest_detail.html'
	
	def test_func(self):
		"""Only staff and admin can access guest details."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		from django.contrib.auth import get_user_model
		from django.db.models import Sum, Q
		
		context = super().get_context_data(**kwargs)
		User = get_user_model()
		
		guest_id = kwargs.get('pk')
		guest = get_object_or_404(User, pk=guest_id, is_staff=False)
		
		# Get guest bookings
		bookings = Booking.objects.filter(
			user=guest
		).select_related(
			'room', 'room__room_type', 'payment'
		).order_by('-created_at')
		
		# Get guest service orders
		service_orders = ServiceOrder.objects.filter(
			user=guest
		).order_by('-created_at')[:10]
		
		# Calculate statistics
		total_spent = Payment.objects.filter(
			booking__user=guest,
			status_pembayaran='VERIFIED'
		).aggregate(total=Sum('amount'))['total'] or 0
		
		context.update({
			'guest': guest,
			'profile': getattr(guest, 'guest_profile', None),
			'bookings': bookings,
			'service_orders': service_orders,
			'total_bookings': bookings.count(),
			'total_spent': total_spent,
			'completed_stays': bookings.filter(status_pesanan='CHECKED_OUT').count(),
		})
		
		return context


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Main admin dashboard with operational overview and real metrics."""
	
	template_name = 'dashboard/admin_dashboard.html'
	
	def test_func(self):
		"""Only staff and admin can access admin dashboard."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		today = timezone.localdate()
		now = timezone.now()
		
		# Room inventory metrics
		total_rooms = Room.objects.filter(is_active=True).count()
		clean_rooms = Room.objects.filter(status='CLEAN', is_active=True).count()
		dirty_rooms = Room.objects.filter(status='DIRTY').count()
		maintenance_rooms = Room.objects.filter(status='MAINTENANCE').count()
		
		# Occupancy - rooms currently occupied by CHECKED_IN bookings
		occupied_bookings = Booking.objects.filter(
			status_pesanan='CHECKED_IN',
			tanggal_check_in__lte=today,
			tanggal_check_out__gt=today
		).select_related('room')
		occupied_rooms = occupied_bookings.count()
		occupancy_rate = round((occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0, 1)
		
		# Today's operations
		arrivals_today = Booking.objects.filter(
			status_pesanan='CONFIRMED',
			tanggal_check_in=today
		).select_related('room', 'room__room_type', 'user').order_by('room__number')
		
		departures_today = Booking.objects.filter(
			status_pesanan='CHECKED_IN',
			tanggal_check_out=today
		).select_related('room', 'room__room_type', 'user').order_by('room__number')
		
		# Reservation metrics
		pending_payment_count = Booking.objects.filter(
			status_pesanan='PENDING_PAYMENT',
			tanggal_check_out__gte=today
		).count()
		
		confirmed_count = Booking.objects.filter(
			status_pesanan='CONFIRMED'
		).count()
		
		checked_in_count = Booking.objects.filter(
			status_pesanan='CHECKED_IN'
		).count()
		
		# Payment verification queue
		pending_verification = Payment.objects.filter(
			status_pembayaran='PENDING_VERIFICATION'
		).select_related('booking', 'booking__user', 'booking__room').order_by('created_at')
		
		pending_verification_count = pending_verification.count()
		
		# Service orders needing attention
		pending_service_orders = ServiceOrder.objects.filter(
			status__in=ServiceOrder.ACTIVE_STATUSES
		).select_related('user', 'booking', 'booking__room').order_by('created_at')
		
		pending_service_count = pending_service_orders.count()
		
		# Financial metrics (last 30 days and total)
		thirty_days_ago = today - timedelta(days=30)
		
		verified_payments = Payment.objects.filter(status_pembayaran='VERIFIED')
		total_revenue = verified_payments.aggregate(total=Sum('amount'))['total'] or 0
		
		revenue_30_days = verified_payments.filter(
			verified_at__gte=thirty_days_ago
		).aggregate(total=Sum('amount'))['total'] or 0
		
		# Upcoming operations (next 7 days)
		seven_days = today + timedelta(days=7)
		upcoming_arrivals = Booking.objects.filter(
			status_pesanan='CONFIRMED',
			tanggal_check_in__gt=today,
			tanggal_check_in__lte=seven_days
		).count()
		
		# Recent activity (last 10 bookings)
		recent_bookings = Booking.objects.select_related(
			'room', 'room__room_type', 'user', 'payment'
		).order_by('-created_at')[:10]
		
		# Booking status distribution
		status_distribution = Booking.objects.values('status_pesanan').annotate(
			count=Count('id')
		).order_by('status_pesanan')
		
		context.update({
			'active_section': 'admin_dashboard',
			'today': today,
			# Room metrics
			'total_rooms': total_rooms,
			'clean_rooms': clean_rooms,
			'dirty_rooms': dirty_rooms,
			'maintenance_rooms': maintenance_rooms,
			'occupied_rooms': occupied_rooms,
			'occupancy_rate': occupancy_rate,
			'available_rooms': clean_rooms - occupied_rooms if clean_rooms >= occupied_rooms else 0,
			# Today's operations
			'arrivals_today': arrivals_today,
			'arrivals_count': arrivals_today.count(),
			'departures_today': departures_today,
			'departures_count': departures_today.count(),
			# Reservations
			'pending_payment_count': pending_payment_count,
			'confirmed_count': confirmed_count,
			'checked_in_count': checked_in_count,
			# Action queues
			'pending_verification': pending_verification[:5],  # Top 5 for dashboard
			'pending_verification_count': pending_verification_count,
			'pending_service_orders': pending_service_orders[:5],  # Top 5 for dashboard
			'pending_service_count': pending_service_count,
			# Financial
			'total_revenue': total_revenue,
			'revenue_30_days': revenue_30_days,
			# Upcoming
			'upcoming_arrivals': upcoming_arrivals,
			# Recent activity
			'recent_bookings': recent_bookings,
			# Charts
			'status_distribution': list(status_distribution),
		})
		
		return context



class StaffReservationListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Staff interface for managing all reservations."""
	
	template_name = 'dashboard/staff_reservations.html'
	
	def test_func(self):
		"""Only staff and admin can access."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		today = timezone.localdate()
		
		# Base queryset
		bookings = Booking.objects.select_related(
			'room', 'room__room_type', 'user', 'payment', 'voucher'
		).order_by('-created_at')
		
		# Apply filters
		status_filter = self.request.GET.get('status', '')
		payment_filter = self.request.GET.get('payment_status', '')
		search_query = self.request.GET.get('q', '').strip()
		date_from = self.request.GET.get('date_from', '')
		date_to = self.request.GET.get('date_to', '')
		
		if status_filter:
			bookings = bookings.filter(status_pesanan=status_filter)
		
		if payment_filter:
			bookings = bookings.filter(payment__status_pembayaran=payment_filter)
		
		if search_query:
			bookings = bookings.filter(
				Q(booking_code__icontains=search_query) |
				Q(user__email__icontains=search_query) |
				Q(user__first_name__icontains=search_query) |
				Q(user__last_name__icontains=search_query) |
				Q(room__number__icontains=search_query)
			)
		
		if date_from:
			try:
				from datetime import datetime
				date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
				bookings = bookings.filter(tanggal_check_in__gte=date_from_obj)
			except ValueError:
				pass
		
		if date_to:
			try:
				from datetime import datetime
				date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
				bookings = bookings.filter(tanggal_check_out__lte=date_to_obj)
			except ValueError:
				pass
		
		# Pagination
		from django.core.paginator import Paginator
		paginator = Paginator(bookings, 20)
		page_number = self.request.GET.get('page', 1)
		page_obj = paginator.get_page(page_number)
		
		context.update({
			'active_section': 'reservations',
			'page_obj': page_obj,
			'bookings': page_obj.object_list,
			'status_filter': status_filter,
			'payment_filter': payment_filter,
			'search_query': search_query,
			'date_from': date_from,
			'date_to': date_to,
			'status_choices': Booking.STATUS_CHOICES,
			'payment_status_choices': Payment.STATUS_PAYMENT,
			'today': today,
		})
		
		return context


class PaymentVerificationView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Payment verification interface for authorized staff."""
	
	template_name = 'dashboard/payment_verification.html'
	
	def test_func(self):
		"""Only staff and admin can verify payments."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		
		# Get payments needing verification
		pending_payments = Payment.objects.filter(
			status_pembayaran='PENDING_VERIFICATION'
		).select_related(
			'booking', 'booking__user', 'booking__room', 'booking__room__room_type'
		).order_by('created_at')
		
		# Get recently verified/rejected payments
		recent_processed = Payment.objects.filter(
			status_pembayaran__in=('VERIFIED', 'REJECTED')
		).select_related(
			'booking', 'booking__user', 'verified_by'
		).order_by('-verified_at')[:20]
		
		# Apply search filter
		search_query = self.request.GET.get('q', '').strip()
		if search_query:
			pending_payments = pending_payments.filter(
				Q(booking__booking_code__icontains=search_query) |
				Q(booking__user__email__icontains=search_query) |
				Q(booking__user__first_name__icontains=search_query) |
				Q(booking__user__last_name__icontains=search_query)
			)
		
		context.update({
			'active_section': 'payments',
			'pending_payments': pending_payments,
			'recent_processed': recent_processed,
			'search_query': search_query,
			'pending_count': pending_payments.count(),
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
		from reservations.services import verify_payment
		from reservations.models import InvalidTransition
		
		payment_id = request.POST.get('payment_id')
		action = request.POST.get('action')  # 'approve' or 'reject'
		rejection_reason = request.POST.get('rejection_reason', '').strip()
		
		if not payment_id or action not in ('approve', 'reject'):
			messages.error(request, 'Permintaan tidak valid.')
			return redirect('payment_verification')
		
		try:
			payment = get_object_or_404(Payment, pk=payment_id)
			
			if action == 'approve':
				# Use service layer for verification
				verify_payment(payment.id, request.user.id)
				messages.success(
					request,
					f'Pembayaran untuk reservasi {payment.booking.booking_code} telah diverifikasi. '
					f'Status reservasi diperbarui menjadi CONFIRMED.'
				)
			else:  # reject
				if not rejection_reason:
					messages.error(request, 'Alasan penolakan harus diisi.')
					return redirect('payment_verification')
				
				# Reject payment
				payment.status_pembayaran = 'REJECTED'
				payment.verified_by = request.user
				payment.verified_at = timezone.now()
				payment.catatan_verifikasi = rejection_reason
				payment.save()
				
				messages.warning(
					request,
					f'Pembayaran untuk reservasi {payment.booking.booking_code} ditolak. '
					f'Tamu dapat mengupload bukti pembayaran yang baru.'
				)
		
		except InvalidTransition as e:
			messages.error(request, f'Tidak dapat memverifikasi pembayaran: {str(e)}')
		except Exception as e:
			messages.error(request, f'Terjadi kesalahan: {str(e)}')
		
		return redirect('payment_verification')


class CheckInOutView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Dedicated interface for check-in and check-out operations."""
	
	template_name = 'dashboard/checkin_checkout.html'
	
	def test_func(self):
		"""Only staff and admin can perform check-in/out."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		today = timezone.localdate()
		
		# Today's expected arrivals (CONFIRMED bookings checking in today)
		arrivals_today = Booking.objects.filter(
			status_pesanan='CONFIRMED',
			tanggal_check_in=today
		).select_related(
			'room', 'room__room_type', 'user', 'payment'
		).order_by('room__number')
		
		# Today's expected departures (CHECKED_IN bookings checking out today)
		departures_today = Booking.objects.filter(
			status_pesanan='CHECKED_IN',
			tanggal_check_out=today
		).select_related(
			'room', 'room__room_type', 'user'
		).order_by('room__number')
		
		# Current guests (all CHECKED_IN)
		current_guests = Booking.objects.filter(
			status_pesanan='CHECKED_IN'
		).select_related(
			'room', 'room__room_type', 'user'
		).order_by('room__number')
		
		# Late check-outs (should have checked out before today)
		late_checkouts = Booking.objects.filter(
			status_pesanan='CHECKED_IN',
			tanggal_check_out__lt=today
		).select_related(
			'room', 'room__room_type', 'user'
		).order_by('tanggal_check_out')
		
		# Search functionality
		search_query = self.request.GET.get('q', '').strip()
		search_results = None
		
		if search_query:
			search_results = Booking.objects.filter(
				Q(booking_code__icontains=search_query) |
				Q(user__email__icontains=search_query) |
				Q(user__first_name__icontains=search_query) |
				Q(user__last_name__icontains=search_query) |
				Q(room__number__icontains=search_query),
				status_pesanan__in=('CONFIRMED', 'CHECKED_IN')
			).select_related(
				'room', 'room__room_type', 'user', 'payment'
			).order_by('-created_at')[:10]
		
		context.update({
			'active_section': 'checkin_checkout',
			'today': today,
			'arrivals_today': arrivals_today,
			'departures_today': departures_today,
			'current_guests': current_guests,
			'late_checkouts': late_checkouts,
			'search_query': search_query,
			'search_results': search_results,
		})
		
		return context


class CheckInActionView(LoginRequiredMixin, UserPassesTestMixin, View):
	"""Handle check-in action."""
	
	def test_func(self):
		"""Only staff and admin can check in guests."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def post(self, request, *args, **kwargs):
		booking_id = request.POST.get('booking_id')
		
		if not booking_id:
			messages.error(request, 'ID reservasi tidak valid.')
			return redirect('checkin_checkout')
		
		try:
			booking = get_object_or_404(Booking, pk=booking_id)
			
			# Verify booking can be checked in
			if booking.status_pesanan != 'CONFIRMED':
				messages.error(
					request,
					f'Reservasi {booking.booking_code} tidak dapat di-check-in. '
					f'Status saat ini: {booking.get_status_pesanan_display()}'
				)
				return redirect('checkin_checkout')
			
			# Perform check-in
			booking.check_in()
			
			messages.success(
				request,
				f'Tamu {booking.user.get_full_name() or booking.user.email} '
				f'berhasil check-in ke kamar {booking.room.number}.'
			)
		
		except Exception as e:
			messages.error(request, f'Gagal melakukan check-in: {str(e)}')
		
		return redirect('checkin_checkout')


class CheckOutActionView(LoginRequiredMixin, UserPassesTestMixin, View):
	"""Handle check-out action."""
	
	def test_func(self):
		"""Only staff and admin can check out guests."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def post(self, request, *args, **kwargs):
		booking_id = request.POST.get('booking_id')
		
		if not booking_id:
			messages.error(request, 'ID reservasi tidak valid.')
			return redirect('checkin_checkout')
		
		try:
			booking = get_object_or_404(Booking, pk=booking_id)
			
			# Verify booking can be checked out
			if booking.status_pesanan != 'CHECKED_IN':
				messages.error(
					request,
					f'Reservasi {booking.booking_code} tidak dapat di-check-out. '
					f'Status saat ini: {booking.get_status_pesanan_display()}'
				)
				return redirect('checkin_checkout')
			
			# Perform check-out
			booking.check_out()
			
			messages.success(
				request,
				f'Tamu {booking.user.get_full_name() or booking.user.email} '
				f'berhasil check-out dari kamar {booking.room.number}. '
				f'Kamar ditandai sebagai DIRTY dan memerlukan housekeeping.'
			)
		
		except Exception as e:
			messages.error(request, f'Gagal melakukan check-out: {str(e)}')
		
		return redirect('checkin_checkout')


class RoomManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Room and room type management interface."""
	
	template_name = 'dashboard/room_management.html'
	
	def test_func(self):
		"""Only admin can manage rooms."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role == 'ADMIN'
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		
		# Get all room types
		room_types = RoomType.objects.annotate(
			room_count=Count('rooms')
		).order_by('name')
		
		# Get all rooms with availability info
		rooms = Room.objects.select_related('room_type').annotate(
			booking_count=Count('bookings')
		).order_by('is_active', 'floor', 'number')
		
		# Apply filters
		status_filter = self.request.GET.get('status', '')
		type_filter = self.request.GET.get('room_type', '')
		active_filter = self.request.GET.get('active', '')
		
		if status_filter:
			rooms = rooms.filter(status=status_filter)
		
		if type_filter:
			rooms = rooms.filter(room_type_id=type_filter)
		
		if active_filter == 'active':
			rooms = rooms.filter(is_active=True)
		elif active_filter == 'inactive':
			rooms = rooms.filter(is_active=False)
		
		context.update({
			'active_section': 'rooms',
			'room_types': room_types,
			'rooms': rooms,
			'status_filter': status_filter,
			'type_filter': type_filter,
			'active_filter': active_filter,
			'room_status_choices': Room.STATUS_CHOICES,
		})
		
		return context


class ServiceOrderQueueStaffView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Staff interface for managing service orders."""
	
	template_name = 'dashboard/service_order_queue.html'
	
	def test_func(self):
		"""Only staff and admin can manage service orders."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		
		# Base queryset
		orders = ServiceOrder.objects.select_related(
			'user', 'booking', 'booking__room'
		).prefetch_related('items').order_by('-created_at')
		
		# Filter by status
		status_filter = self.request.GET.get('status', '')
		if status_filter:
			orders = orders.filter(status=status_filter)
		else:
			# Default: show active orders first
			orders = orders.filter(status__in=ServiceOrder.ACTIVE_STATUSES)
		
		# Filter by service type
		service_filter = self.request.GET.get('service_type', '')
		if service_filter:
			orders = orders.filter(service_type=service_filter)
		
		# Search
		search_query = self.request.GET.get('q', '').strip()
		if search_query:
			orders = orders.filter(
				Q(order_code__icontains=search_query) |
				Q(user__email__icontains=search_query) |
				Q(user__first_name__icontains=search_query) |
				Q(booking__room__number__icontains=search_query)
			)
		
		# Pagination
		from django.core.paginator import Paginator
		paginator = Paginator(orders, 25)
		page_number = self.request.GET.get('page', 1)
		page_obj = paginator.get_page(page_number)
		
		# Statistics
		pending_count = ServiceOrder.objects.filter(
			status__in=ServiceOrder.ACTIVE_STATUSES
		).count()
		
		completed_today = ServiceOrder.objects.filter(
			status__in=ServiceOrder.COMPLETE_STATUSES,
			updated_at__date=timezone.localdate()
		).count()
		
		context.update({
			'active_section': 'service_orders',
			'page_obj': page_obj,
			'orders': page_obj.object_list,
			'status_filter': status_filter,
			'service_filter': service_filter,
			'search_query': search_query,
			'status_choices': ServiceOrder.STATUS_CHOICES,
			'service_choices': ServiceOrder.SERVICE_CHOICES,
			'pending_count': pending_count,
			'completed_today': completed_today,
		})
		
		return context


class ServiceOrderUpdateStatusView(LoginRequiredMixin, UserPassesTestMixin, View):
	"""Update service order status."""
	
	def test_func(self):
		"""Only staff and admin can update service order status."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role in ('STAFF', 'ADMIN')
	
	def post(self, request, *args, **kwargs):
		order_id = request.POST.get('order_id')
		new_status = request.POST.get('status')
		
		if not order_id or not new_status:
			messages.error(request, 'Data tidak lengkap.')
			return redirect('service_order_queue_staff')
		
		try:
			order = get_object_or_404(ServiceOrder, pk=order_id)
			
			# Validate status transition
			if new_status not in dict(ServiceOrder.STATUS_CHOICES):
				messages.error(request, 'Status tidak valid.')
				return redirect('service_order_queue_staff')
			
			# Use the model's transition method if available
			if hasattr(order, 'transition_to'):
				order.transition_to(new_status, request.user)
			else:
				# Fallback: direct status change
				order.status = new_status
				order.save()
			
			messages.success(
				request,
				f'Order {order.order_code} berhasil diperbarui ke status {order.get_status_display()}.'
			)
		
		except Exception as e:
			messages.error(request, f'Gagal memperbarui status order: {str(e)}')
		
		return redirect('service_order_queue_staff')



class StaffManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Staff and user account management interface."""
	
	template_name = 'dashboard/staff_management.html'
	
	def test_func(self):
		"""Only admin can manage staff."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role == 'ADMIN'
	
	def get_context_data(self, **kwargs):
		from django.contrib.auth import get_user_model
		
		context = super().get_context_data(**kwargs)
		User = get_user_model()
		
		# Get all staff users
		staff_users = User.objects.filter(
			Q(is_staff=True) | Q(guest_profile__role__in=('STAFF', 'ADMIN'))
		).select_related('guest_profile').annotate(
			booking_handled_count=Count('verified_payments')
		).order_by('-is_active', 'date_joined')
		
		# Apply search filter
		search_query = self.request.GET.get('q', '').strip()
		if search_query:
			staff_users = staff_users.filter(
				Q(username__icontains=search_query) |
				Q(email__icontains=search_query) |
				Q(first_name__icontains=search_query) |
				Q(last_name__icontains=search_query)
			)
		
		# Role filter
		role_filter = self.request.GET.get('role', '')
		if role_filter:
			staff_users = staff_users.filter(guest_profile__role=role_filter)
		
		context.update({
			'active_section': 'staff',
			'staff_users': staff_users,
			'search_query': search_query,
			'role_filter': role_filter,
			'role_choices': GuestProfile.ROLE_CHOICES,
			'total_staff': staff_users.count(),
		})
		
		return context


class StaffDetailView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
	"""Detailed view of a staff member."""
	
	template_name = 'dashboard/staff_detail.html'
	
	def test_func(self):
		"""Only admin can view staff details."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role == 'ADMIN'
	
	def get_context_data(self, **kwargs):
		from django.contrib.auth import get_user_model
		
		context = super().get_context_data(**kwargs)
		User = get_user_model()
		
		staff_id = kwargs.get('pk')
		staff_user = get_object_or_404(User, pk=staff_id)
		profile = getattr(staff_user, 'guest_profile', None)
		
		# Get activity statistics
		payments_verified = Payment.objects.filter(
			verified_by=staff_user
		).count()
		
		recent_verifications = Payment.objects.filter(
			verified_by=staff_user
		).select_related('booking', 'booking__user').order_by('-verified_at')[:10]
		
		context.update({
			'active_section': 'staff',
			'staff_user': staff_user,
			'profile': profile,
			'payments_verified': payments_verified,
			'recent_verifications': recent_verifications,
		})
		
		return context


class StaffUpdateRoleView(LoginRequiredMixin, UserPassesTestMixin, View):
	"""Update staff member's role."""
	
	def test_func(self):
		"""Only admin can update staff roles."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role == 'ADMIN'
	
	def post(self, request, *args, **kwargs):
		from django.contrib.auth import get_user_model
		
		User = get_user_model()
		staff_id = request.POST.get('staff_id')
		new_role = request.POST.get('role')
		
		if not staff_id or not new_role:
			messages.error(request, 'Data tidak lengkap.')
			return redirect('staff_management')
		
		if new_role not in dict(GuestProfile.ROLE_CHOICES):
			messages.error(request, 'Role tidak valid.')
			return redirect('staff_management')
		
		try:
			staff_user = get_object_or_404(User, pk=staff_id)
			
			# Prevent self-demotion
			if staff_user.id == request.user.id and new_role != 'ADMIN':
				messages.error(request, 'Anda tidak dapat mengubah role Anda sendiri.')
				return redirect('staff_management')
			
			# Get or create profile
			profile, created = GuestProfile.objects.get_or_create(
				user=staff_user,
				defaults={'role': new_role}
			)
			
			if not created:
				old_role = profile.role
				profile.role = new_role
				profile.save()
				
				# Sync Django's is_staff flag
				if new_role in ('STAFF', 'ADMIN'):
					staff_user.is_staff = True
				else:
					staff_user.is_staff = False
				staff_user.save()
				
				messages.success(
					request,
					f'Role {staff_user.get_full_name() or staff_user.email} '
					f'berhasil diubah dari {old_role} menjadi {new_role}.'
				)
		
		except Exception as e:
			messages.error(request, f'Gagal mengubah role: {str(e)}')
		
		return redirect('staff_management')


class StaffToggleActiveView(LoginRequiredMixin, UserPassesTestMixin, View):
	"""Activate or deactivate staff account."""
	
	def test_func(self):
		"""Only admin can activate/deactivate staff."""
		user = self.request.user
		role = getattr(getattr(user, 'guest_profile', None), 'role', None)
		return user.is_staff or role == 'ADMIN'
	
	def post(self, request, *args, **kwargs):
		from django.contrib.auth import get_user_model
		
		User = get_user_model()
		staff_id = request.POST.get('staff_id')
		
		if not staff_id:
			messages.error(request, 'ID staff tidak valid.')
			return redirect('staff_management')
		
		try:
			staff_user = get_object_or_404(User, pk=staff_id)
			
			# Prevent self-deactivation
			if staff_user.id == request.user.id:
				messages.error(request, 'Anda tidak dapat menonaktifkan akun Anda sendiri.')
				return redirect('staff_management')
			
			# Toggle active status
			staff_user.is_active = not staff_user.is_active
			staff_user.save()
			
			status_text = 'diaktifkan' if staff_user.is_active else 'dinonaktifkan'
			messages.success(
				request,
				f'Akun {staff_user.get_full_name() or staff_user.email} berhasil {status_text}.'
			)
		
		except Exception as e:
			messages.error(request, f'Gagal mengubah status: {str(e)}')
		
		return redirect('staff_management')
