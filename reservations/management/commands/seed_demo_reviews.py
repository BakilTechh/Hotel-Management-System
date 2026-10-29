"""Seed demo guest reviews for the public Ulasan Tamu wall."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reservations.models import Booking, Review
from rooms.models import Room

DEMO_PASSWORD = 'nocturn-demo-review'

GUESTS = [
    {
        'username': 'demo_ayu',
        'first_name': 'Ayu',
        'last_name': 'Pramesti',
        'email': 'ayu.demo@nocturnhaven.test',
        'rating': 5,
        'comment': (
            'Kamar bersih, tenang, dan wangi. Sarapannya enak dan staf resepsionis '
            'sangat membantu saat kami minta late checkout.'
        ),
        'room_index': 0,
        'nights': 2,
        'days_ago': 12,
    },
    {
        'username': 'demo_bagas',
        'first_name': 'Bagas',
        'last_name': 'Nugroho',
        'email': 'bagas.demo@nocturnhaven.test',
        'rating': 5,
        'comment': (
            'Pemandangan kota dari kamar luar biasa, terutama saat sore. '
            'Proses check-in cepat dan kamarnya sesuai foto.'
        ),
        'room_index': 2,
        'nights': 1,
        'days_ago': 26,
    },
    {
        'username': 'demo_citra',
        'first_name': 'Citra',
        'last_name': 'Lestari',
        'email': 'citra.demo@nocturnhaven.test',
        'rating': 4,
        'comment': (
            'Tempat tidurnya nyaman dan area kolam renangnya bersih. '
            'Hanya saja lift agak ramai saat jam sarapan.'
        ),
        'room_index': 1,
        'nights': 3,
        'days_ago': 45,
    },
    {
        'username': 'demo_dimas',
        'first_name': 'Dimas',
        'last_name': 'Saputra',
        'email': 'dimas.demo@nocturnhaven.test',
        'rating': 5,
        'comment': (
            'Menginap untuk perjalanan bisnis dan Wi-Fi-nya stabil. '
            'Meja kerja di kamar sangat membantu, sarapan juga lengkap.'
        ),
        'room_index': 3,
        'nights': 2,
        'days_ago': 70,
    },
    {
        'username': 'demo_elena',
        'first_name': 'Elena',
        'last_name': 'Wijaya',
        'email': 'elena.demo@nocturnhaven.test',
        'rating': 4,
        'comment': (
            'Suasana hotel tenang dan cocok untuk beristirahat. '
            'Pelayanan room service cepat, meski pilihan menunya bisa lebih banyak.'
        ),
        'room_index': 4,
        'nights': 2,
        'days_ago': 95,
    },
    {
        'username': 'demo_fajar',
        'first_name': 'Fajar',
        'last_name': 'Ramadhan',
        'email': 'fajar.demo@nocturnhaven.test',
        'rating': 3,
        'comment': (
            'Lokasi strategis dan kamar cukup luas. Pengalaman menginapnya baik, '
            'tetapi saat check-in kamar baru siap beberapa menit setelah jamnya.'
        ),
        'room_index': 0,
        'nights': 1,
        'days_ago': 120,
    },
]


class Command(BaseCommand):
    help = (
        'Seed six checked-out bookings with reviews for the public Ulasan Tamu '
        'wall. Safe to run repeatedly: existing demo reviewers are skipped.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Count the reviews that would be created without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        User = get_user_model()
        rooms = list(Room.objects.select_related('room_type').order_by('number'))
        if not rooms:
            raise CommandError('No rooms found. Seed rooms before demo reviews.')

        created = skipped = 0
        today = date.today()

        with transaction.atomic():
            for spec in GUESTS:
                if Review.objects.filter(guest__username=spec['username']).exists():
                    skipped += 1
                    continue

                if dry_run:
                    created += 1
                    continue

                user, _ = User.objects.get_or_create(
                    username=spec['username'],
                    defaults={
                        'first_name': spec['first_name'],
                        'last_name': spec['last_name'],
                        'email': spec['email'],
                        'password': make_password(DEMO_PASSWORD),
                    },
                )

                room = rooms[spec['room_index'] % len(rooms)]
                check_out = today - timedelta(days=spec['days_ago'])
                check_in = check_out - timedelta(days=spec['nights'])
                nightly = Decimal(str(room.room_type.price_per_night))
                subtotal = nightly * spec['nights']
                tax = (subtotal * Decimal('0.11')).quantize(Decimal('0.01'))

                booking, _ = Booking.objects.get_or_create(
                    user=user,
                    room=room,
                    tanggal_check_in=check_in,
                    tanggal_check_out=check_out,
                    defaults={
                        'jumlah_tamu': min(room.room_type.capacity, 2),
                        'status_pesanan': 'CHECKED_OUT',
                        'total_harga_dasar': subtotal,
                        'pajak_dan_layanan': tax,
                        'total_biaya_akhir': subtotal + tax,
                    },
                )
                _, was_created = Review.objects.get_or_create(
                    booking=booking,
                    defaults={
                        'guest': user,
                        'rating': spec['rating'],
                        'comment': spec['comment'],
                    },
                )
                created += int(was_created)
                skipped += int(not was_created)

            if dry_run:
                transaction.set_rollback(True)

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no rows written.'))
        self.stdout.write(
            self.style.SUCCESS(
                f'Demo reviews ready: {created} created, {skipped} skipped.'
            )
        )
        self.stdout.write(
            f'Review wall now has {Review.objects.count()} reviews.'
        )
