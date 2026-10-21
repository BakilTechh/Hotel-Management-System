from datetime import timedelta

from django.db.models import Avg, Count
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date

from reservations.models import Booking, Review
from .models import Room, RoomType


def _room_card(room):
    price = f'{room.room_type.price_per_night:,.0f}'.replace(',', '.')
    return {
        'id': room.pk,
        'name': f'Kamar {room.number}',
        'label': f'Lantai {room.floor}',
        'price': price,
        'total': price,
        'size': 'Informasi ukuran tersedia di resepsionis',
        'bed': 'Tempat tidur sesuai Room Type',
        'capacity': f'Maks {room.room_type.capacity} Tamu',
        'view': 'Pemandangan hotel',
        'badge': 'Tersedia' if room.status == 'CLEAN' else room.get_status_display(),
        'image': 'https://images.unsplash.com/photo-1566665797739-1674de7a421a?auto=format&fit=crop&w=1200&q=85',
        'features': ['Wi-Fi', 'Layanan kamar'],
    }


def room_list(request):
    room_types = RoomType.objects.all()
    rooms = Room.objects.filter(is_active=True).select_related('room_type')

    selected_type = request.GET.get('type')
    if selected_type:
        rooms = rooms.filter(room_type_id=selected_type)

    selected_status = request.GET.get('status')
    if selected_status:
        rooms = rooms.filter(status=selected_status)

    guests = request.GET.get('guests', '')
    if guests.isdigit():
        rooms = rooms.filter(room_type__capacity__gte=int(guests))

    check_in_raw = request.GET.get('check_in', '')
    check_out_raw = request.GET.get('check_out', '')
    check_in = parse_date(check_in_raw) if check_in_raw else None
    check_out = parse_date(check_out_raw) if check_out_raw else None

    availability_error = ''
    availability_checked = bool(check_in and check_out)
    if availability_checked:
        if check_out <= check_in:
            availability_error = 'Tanggal check-out harus setelah check-in.'
            rooms = rooms.none()
        else:
            available_ids = Booking.available_rooms(check_in, check_out).values('pk')
            rooms = rooms.filter(pk__in=available_ids)

    rooms = rooms.exclude(status='MAINTENANCE')
    room_cards = [_room_card(room) for room in rooms]

    context = {
        'rooms': room_cards,
        'room_count': len(room_cards),
        'availability_checked': availability_checked,
        'availability_error': availability_error,
        'room_types': room_types,
        'selected_type': selected_type,
        'selected_status': selected_status,
        'check_in': check_in_raw,
        'check_out': check_out_raw,
        'guests': guests,
    }
    return render(request, 'rooms/room_list.html', context)


def room_detail(request, pk):
    room = get_object_or_404(
        Room.objects.select_related('room_type'), pk=pk, is_active=True
    )

    today = timezone.localdate()
    end = today + timedelta(days=14)
    blocked = {
        a.date: a
        for a in room.availabilities.filter(
            date__gte=today, date__lt=end, is_available=False
        )
    }

    blocking_statuses = ['PENDING_PAYMENT', 'CONFIRMED', 'CHECKED_IN']
    booked_dates = set()
    for check_in, check_out in room.bookings.filter(
        status_pesanan__in=blocking_statuses,
        tanggal_check_out__gt=today,
        tanggal_check_in__lt=end,
    ).values_list('tanggal_check_in', 'tanggal_check_out'):
        cursor = max(check_in, today)
        while cursor < check_out and cursor < end:
            booked_dates.add(cursor)
            cursor += timedelta(days=1)

    calendar = []
    for i in range(14):
        d = today + timedelta(days=i)
        entry = blocked.get(d)
        is_booked = d in booked_dates
        calendar.append({
            'date': d,
            'available': entry is None and not is_booked,
            'note': entry.note if entry else ('Terisi' if is_booked else ''),
        })

    reviews = list(
        Review.objects.filter(booking__room=room)
        .select_related('guest')
        .order_by('-created_at')
    )
    rating_summary = Review.objects.filter(booking__room=room).aggregate(
        average=Avg('rating'), count=Count('id')
    )

    return render(request, 'rooms/room_detail.html', {
        'room': _room_card(room),
        'calendar': calendar,
        'reviews': reviews,
        'rating_average': rating_summary['average'],
        'rating_count': rating_summary['count'],
    })


def review_list(request):
    """Daftar ulasan tamu untuk semua kamar (halaman "Ulasan Tamu")."""
    reviews = (
        Review.objects.select_related('guest', 'booking__room')
        .order_by('-created_at')
    )
    summary = reviews.aggregate(average=Avg('rating'), count=Count('id'))
    return render(request, 'rooms/review_list.html', {
        'reviews': reviews,
        'rating_average': summary['average'],
        'rating_count': summary['count'],
    })
