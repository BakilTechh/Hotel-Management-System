import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from .services import _gemini_error_detail, call_gemini


class ChatbotServiceTest(TestCase):
    def test_availability_context_reflects_real_rooms(self):
        from datetime import timedelta

        from django.contrib.auth.models import User
        from rooms.models import Room
        from reservations.models import Booking
        from .services import get_hotel_context, hotel_today

        user = User.objects.create_user('tamu', password='p')
        room = Room.objects.order_by('number').first()
        today = hotel_today()
        Booking.objects.create(
            user=user, room=room,
            tanggal_check_in=today, tanggal_check_out=today + timedelta(days=1),
            jumlah_tamu=1, status_pesanan='CONFIRMED',
        )
        context = get_hotel_context()
        self.assertIn(f'Tanggal hari ini: {today:%d %b %Y}', context)
        self.assertIn(f'- {room.number} (', context)
        self.assertIn('TERPESAN hari ini', context)
        self.assertIn('TERSEDIA', context)
        self.assertIn('Check-in 14:00', context)

    def test_gemini_404_suggests_check_command(self):
        import requests

        fake = requests.Response()
        fake.status_code = 404
        fake._content = json.dumps(
            {'error': {'message': 'models/gemini-2.0-flash is not found for API version v1beta'}}
        ).encode()
        error = requests.HTTPError('404 Client Error', response=fake)
        with mock.patch('chatbot.services.requests.post', side_effect=error):
            with self.settings(GEMINI_API_KEY='AIza-test', GEMINI_MODEL='gemini-2.0-flash'):
                reply = call_gemini('halo')
        self.assertIn('check_gemini', reply)
        self.assertIn('gemini-2.0-flash', reply)

    def test_gemini_error_detail_prefers_api_message(self):
        import requests

        fake = requests.Response()
        fake.status_code = 400
        fake._content = json.dumps({'error': {'message': 'API key not valid.'}}).encode()
        error = requests.HTTPError('400 Client Error', response=fake)
        self.assertEqual(_gemini_error_detail(error), '400 API key not valid.')

    def test_gemini_overloaded_says_try_again(self):
        import requests

        fake = requests.Response()
        fake.status_code = 503
        fake._content = json.dumps(
            {'error': {'message': 'This model is currently experiencing high demand.'}}
        ).encode()
        error = requests.HTTPError('503 Server Error', response=fake)
        with mock.patch('chatbot.services.requests.post', side_effect=error):
            with self.settings(GEMINI_API_KEY='AIza-test'):
                reply = call_gemini('halo')
        self.assertIn('padat', reply)

    def test_gemini_retries_once_on_timeout_then_answers(self):
        import requests

        ok = requests.Response()
        ok.status_code = 200
        ok._content = json.dumps({'candidates': [
            {'content': {'parts': [{'text': 'Kamar tersedia!'}]}}
        ]}).encode()
        with mock.patch(
            'chatbot.services.requests.post',
            side_effect=[requests.ReadTimeout('timed out'), ok],
        ) as post:
            with self.settings(GEMINI_API_KEY='AIza-test'):
                reply = call_gemini('halo')
        self.assertEqual(reply, 'Kamar tersedia!')
        self.assertEqual(post.call_count, 2)

    def test_gemini_timeout_twice_says_slow(self):
        import requests

        with mock.patch(
            'chatbot.services.requests.post',
            side_effect=requests.ReadTimeout('timed out'),
        ) as post:
            with self.settings(GEMINI_API_KEY='AIza-test'):
                reply = call_gemini('halo')
        self.assertIn('tidak merespons tepat waktu', reply)
        self.assertEqual(post.call_count, 2)

    def test_check_gemini_reports_working_model(self):
        import io

        import requests
        from django.core.management import call_command

        def fake_response(status, payload):
            fake = requests.Response()
            fake.status_code = status
            fake._content = json.dumps(payload).encode()
            return fake

        list_payload = {'models': [
            {'name': 'models/gemini-3.8-flash', 'supportedGenerationMethods': ['generateContent']},
            {'name': 'models/gemini-3.5-flash', 'supportedGenerationMethods': ['generateContent']},
        ]}

        def fake_post(url, **kwargs):
            if 'gemini-3.5-flash' in url:
                return fake_response(200, {'candidates': []})
            return fake_response(503, {'error': {'message': 'high demand'}})

        out = io.StringIO()
        with mock.patch(
            'chatbot.management.commands.check_gemini.requests.get',
            return_value=fake_response(200, list_payload),
        ), mock.patch(
            'chatbot.management.commands.check_gemini.requests.post',
            side_effect=fake_post,
        ), mock.patch('chatbot.management.commands.check_gemini.time.sleep'):
            with self.settings(GEMINI_API_KEY='AIza-test', GEMINI_MODEL='gemini-3.8-flash'):
                call_command('check_gemini', stdout=out)
        output = out.getvalue()
        self.assertIn('gemini-3.5-flash: OK', output)
        self.assertIn('gemini-3.5-flash', output.split('these do:')[-1])


class LegacyRoomServiceRouteTest(TestCase):
    """The old conversational room-service page is gone; the portal took over."""

    def test_legacy_route_redirects_to_portal(self):
        response = self.client.get('/room-service/')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, '/room-service/portal/')

    def test_registered_user_follows_redirect_into_portal(self):
        User.objects.create_user('route-guest', password='p')
        self.client.force_login(User.objects.get(username='route-guest'))

        response = self.client.get('/room-service/', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [('/room-service/portal/', 301)])
        self.assertTemplateUsed(response, 'chatbot/room_service_portal.html')

    def test_removed_chat_api_is_not_routed(self):
        User.objects.create_user('api-guest', password='p')
        self.client.force_login(User.objects.get(username='api-guest'))

        response = self.client.post(
            '/room-service/api/chat/',
            data=json.dumps({'message': 'halo'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)


class RoomServicePortalTest(TestCase):
    """Structured room-service ordering from the guest portal."""

    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        from rooms.models import Room
        from reservations.models import Booking

        from .models import RoomServiceMenuItem

        self.user = User.objects.create_user('portal-guest', password='p')
        self.nasi = RoomServiceMenuItem.objects.create(
            name='Nasi Goreng Portal', category='FOOD', price=45000,
        )
        self.teh = RoomServiceMenuItem.objects.create(
            name='Es Teh Portal', category='BEVERAGE', price=15000,
        )
        room = Room.objects.order_by('number').first()
        today = timezone.localdate()
        self.booking = Booking.objects.create(
            user=self.user, room=room,
            tanggal_check_in=today + timedelta(days=3),
            tanggal_check_out=today + timedelta(days=4),
            jumlah_tamu=1, status_pesanan='CONFIRMED',
        )

    def test_portal_requires_login(self):
        response = self.client.get('/room-service/portal/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_guest_without_eligible_stay_sees_gate(self):
        self.client.force_login(self.user)
        self.booking.status_pesanan = 'CANCELLED'
        self.booking.save()

        response = self.client.get('/room-service/portal/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Room service untuk tamu menginap')
        self.assertNotContains(response, 'id="room-service-form"')

    def test_eligible_guest_sees_menu_and_order_form(self):
        self.client.force_login(self.user)

        response = self.client.get('/room-service/portal/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nasi Goreng Portal')
        self.assertContains(response, 'id="room-service-form"')
        self.assertContains(response, f'quantity_{self.nasi.pk}')

    def test_ordering_creates_priced_order_and_status_log(self):
        from decimal import Decimal

        from .models import ServiceOrder, ServiceOrderItem, ServiceOrderStatusLog

        self.client.force_login(self.user)

        response = self.client.post('/room-service/portal/', {
            'booking': self.booking.pk,
            f'quantity_{self.nasi.pk}': 2,
            f'quantity_{self.teh.pk}': 1,
            'special_instructions': 'Tanpa pedas.',
        })

        self.assertRedirects(response, '/room-service/portal/')
        order = ServiceOrder.objects.get(user=self.user)
        self.assertEqual(order.booking, self.booking)
        self.assertEqual(order.status, 'PENDING')
        self.assertEqual(order.special_instructions, 'Tanpa pedas.')
        self.assertEqual(order.items.count(), 2)

        nasi_line = ServiceOrderItem.objects.get(order=order, menu_item=self.nasi)
        self.assertEqual(nasi_line.quantity, 2)
        self.assertEqual(nasi_line.unit_price, Decimal('45000.00'))
        self.assertEqual(order.total, Decimal('105000.00'))
        self.assertTrue(
            ServiceOrderStatusLog.objects.filter(order=order, status='PENDING').exists()
        )

    def test_server_prices_ignore_tampered_client_values(self):
        from .models import ServiceOrder, ServiceOrderItem

        self.client.force_login(self.user)

        self.client.post('/room-service/portal/', {
            'booking': self.booking.pk,
            f'quantity_{self.nasi.pk}': 1,
            'unit_price': '1',
            'amount': '1',
            'total': '1',
        })

        order = ServiceOrder.objects.get(user=self.user)
        line = ServiceOrderItem.objects.get(order=order)
        self.assertEqual(line.unit_price, line.menu_item.price)
        self.assertEqual(order.total, line.menu_item.price)

    def test_order_without_quantities_is_rejected(self):
        from .models import ServiceOrder

        self.client.force_login(self.user)

        response = self.client.post('/room-service/portal/', {
            'booking': self.booking.pk,
            f'quantity_{self.nasi.pk}': 0,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pilih minimal satu menu untuk dipesan.')
        self.assertFalse(ServiceOrder.objects.exists())

    def test_cannot_order_against_another_guests_booking(self):
        from datetime import timedelta

        from django.utils import timezone

        from rooms.models import Room
        from reservations.models import Booking

        from .models import ServiceOrder

        stranger = User.objects.create_user('stranger-guest', password='p')
        room = Room.objects.order_by('number').last()
        today = timezone.localdate()
        stranger_booking = Booking.objects.create(
            user=stranger, room=room,
            tanggal_check_in=today + timedelta(days=3),
            tanggal_check_out=today + timedelta(days=4),
            jumlah_tamu=1, status_pesanan='CONFIRMED',
        )
        self.client.force_login(self.user)

        response = self.client.post('/room-service/portal/', {
            'booking': stranger_booking.pk,
            f'quantity_{self.nasi.pk}': 1,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ServiceOrder.objects.exists())
