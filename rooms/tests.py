from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from .models import Room, RoomType


class RoomTypeFeatureTests(TestCase):
	def test_admin_can_create_valid_room_type_data(self):
		room_type = RoomType.objects.create(
			name='Deluxe King',
			description='Kamar dengan tempat tidur king.',
			capacity=2,
			price_per_night=Decimal('1800000.00'),
		)

		self.assertEqual(str(room_type), 'Deluxe King')
		self.assertEqual(room_type.capacity, 2)

	def test_room_type_rejects_non_positive_capacity(self):
		room_type = RoomType(name='Invalid Capacity', capacity=0, price_per_night=Decimal('100000.00'))

		with self.assertRaises(ValidationError):
			room_type.full_clean()

	def test_room_type_rejects_non_positive_price(self):
		room_type = RoomType(name='Invalid Price', capacity=2, price_per_night=Decimal('0.00'))

		with self.assertRaises(ValidationError):
			room_type.full_clean()

	def test_room_type_can_be_updated(self):
		room_type = RoomType.objects.create(name='Standard', capacity=2, price_per_night=Decimal('900000.00'))
		room_type.name = 'Standard Plus'
		room_type.capacity = 3
		room_type.save()

		room_type.refresh_from_db()
		self.assertEqual(room_type.name, 'Standard Plus')
		self.assertEqual(room_type.capacity, 3)

	def test_room_type_in_use_cannot_be_deleted(self):
		room_type = RoomType.objects.create(name='Used Type', capacity=2, price_per_night=Decimal('900000.00'))
		Room.objects.create(room_type=room_type, number='901')

		with self.assertRaises(ProtectedError):
			room_type.delete()


class RoomFeatureTests(TestCase):
	def setUp(self):
		self.room_type = RoomType.objects.create(
			name='Suite', capacity=4, price_per_night=Decimal('2500000.00')
		)

	def test_room_unit_can_be_created_and_updated(self):
		from .models import Room

		room = Room.objects.create(room_type=self.room_type, number='999', status='CLEAN')
		room.status = 'MAINTENANCE'
		room.save()

		room.refresh_from_db()
		self.assertEqual(room.status, 'MAINTENANCE')

	def test_duplicate_room_number_is_rejected(self):
		from .models import Room

		Room.objects.create(room_type=self.room_type, number='999')
		with self.assertRaises(IntegrityError):
			Room.objects.create(room_type=self.room_type, number='999')


class RoomCalendarTest(TestCase):
	def setUp(self):
		from django.contrib.auth.models import User

		from reservations.models import Booking

		self.today = timezone.localdate()
		self.room_type = RoomType.objects.create(
			name='Calendar Suite', capacity=2, price_per_night=Decimal('1200000.00')
		)
		self.room = Room.objects.create(room_type=self.room_type, number='801', status='CLEAN')
		self.guest = User.objects.create_user('calendar-guest', password='p')
		Booking.objects.create(
			user=self.guest,
			room=self.room,
			tanggal_check_in=self.today,
			tanggal_check_out=self.today + timedelta(days=2),
			jumlah_tamu=1,
			status_pesanan='CONFIRMED',
		)

	def test_calendar_marks_dates_blocked_by_active_booking(self):
		response = self.client.get(f'/rooms/{self.room.pk}/')

		self.assertEqual(response.status_code, 200)
		calendar = response.context['calendar']
		self.assertFalse(calendar[0]['available'])
		self.assertEqual(calendar[0]['note'], 'Terisi')
		self.assertTrue(calendar[5]['available'])


class ReviewListPageTest(TestCase):
	def setUp(self):
		from django.contrib.auth.models import User

		from reservations.models import Booking, Review

		self.guest = User.objects.create_user('reviewer', password='p')
		self.room_type = RoomType.objects.create(
			name='Review Suite', capacity=2, price_per_night=Decimal('1000000.00')
		)
		self.room = Room.objects.create(room_type=self.room_type, number='802')
		booking = Booking.objects.create(
			user=self.guest,
			room=self.room,
			tanggal_check_in=date(2026, 1, 1),
			tanggal_check_out=date(2026, 1, 2),
			jumlah_tamu=1,
			status_pesanan='CHECKED_OUT',
		)
		Review.objects.create(booking=booking, guest=self.guest, rating=5, comment='Kamar luar biasa tenang.')

	def test_review_list_shows_guest_reviews(self):
		response = self.client.get('/rooms/ulasan/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Kamar luar biasa tenang.')
		self.assertContains(response, 'reviewer')

	def test_room_detail_shows_reviews(self):
		response = self.client.get(f'/rooms/{self.room.pk}/')

		self.assertContains(response, 'Kamar luar biasa tenang.')
		self.assertEqual(response.context['rating_count'], 1)
