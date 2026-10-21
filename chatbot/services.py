"""Gemini integration for the Nocturn Haven concierge assistant.

The conversational room-service page was retired in favour of the structured
portal ordering flow, so this module now holds only what the assistant
integration needs: the system prompt, a live hotel snapshot used as grounding
context, and the Gemini REST call with its error handling.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    'Kamu adalah Asisten Chat Hotel Nocturn Haven yang ramah dan profesional. '
    'Jawab dalam Bahasa Indonesia yang sopan dan ringkas (maksimal 3-4 kalimat, '
    'kecuali diminta detail). Layanan yang tersedia: Room Service (pesan makanan '
    'dan minuman lewat Portal Tamu), Request Amenities, Request Extra Bed, '
    'Laundry, dan Chat dengan Resepsionis. Fasilitas hotel: Kolam Renang Infinity '
    'Horizon (06:00-22:00), Serenity Spa & Sauna, The Grand Dining & Lounge, '
    'Pusat Kebugaran 24 Jam. Check-in 14:00, check-out 12:00, gratis pembatalan '
    'hingga 48 jam. '
    'ATURAN KETERSEDIAAN KAMAR: "Kondisi kamar hari ini" di bawah adalah data '
    'asli dan terkini — selalu jawab pertanyaan ketersediaan/kesiapan kamar '
    'HANYA dari daftar itu, jangan mengarang. TERSEDIA = bisa dipesan sekarang. '
    'TERPESAN = sedang ditempati/dipesan tamu lain hari ini. Perawatan = tidak '
    'bisa dipakai. Jika tamu menanyakan kesiapan booking miliknya sendiri, '
    'minta kode reservasinya (contoh: NH-0001) lalu cocokkan dengan data '
    'reservasinya — JANGAN menebak. Jika ragu atau di luar kewenanganmu, '
    'arahkan ke resepsionis. Jangan pernah menyebut kamu adalah model AI '
    'generik; kamu adalah Asisten Chat Nocturn Haven.'
)

STATUS_MENAHAN_KAMAR = ('PENDING_PAYMENT', 'CONFIRMED', 'CHECKED_IN')


def hotel_today():
    """Tanggal hari ini di zona waktu hotel (WIB)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        return datetime.now(ZoneInfo('Asia/Jakarta')).date()
    except Exception:  # pragma: no cover - fallback bila data zona tak ada
        from django.utils import timezone
        return timezone.localdate()


def get_hotel_context():
    """Snapshot terkini: kondisi tiap kamar hari ini + info pemesanan.

    Dipakai sebagai konteks Gemini sehingga jawaban ketersediaan /
    kesiapan check-in selalu berdasarkan data database, bukan karangan.
    """
    from rooms.models import Room
    from reservations.models import Booking

    today = hotel_today()
    try:
        rooms = list(Room.objects.select_related('room_type').order_by('number'))
        if not rooms:
            return 'Belum ada data kamar di sistem. Arahkan tamu ke resepsionis.'
        booked = Booking.objects.filter(
            tanggal_check_in__lte=today,
            tanggal_check_out__gt=today,
            status_pesanan__in=STATUS_MENAHAN_KAMAR,
        ).select_related('room')
        booked_until = {b.room_id: b.tanggal_check_out for b in booked}
        lines = []
        free = 0
        for room in rooms[:40]:
            checkout = booked_until.get(room.pk)
            if room.status == 'MAINTENANCE':
                state = 'Perawatan (tidak bisa dipakai)'
            elif room.status == 'DIRTY':
                state = 'TERPESAN (sedang dibersihkan)'
            elif checkout is not None:
                state = f'TERPESAN hari ini (dipesan s.d. {checkout:%d %b %Y})'
            else:
                state = 'TERSEDIA'
                free += 1
            lines.append(
                f'- {room.number} ({room.room_type.name}, '
                f'Rp {room.room_type.price_per_night:,.0f}/malam): {state}'
            )
        header = (
            f'Tanggal hari ini: {today:%d %b %Y} (WIB). '
            f'{free} dari {len(rooms)} kamar TERSEDIA hari ini. '
            'Check-in 14:00, check-out 12:00; early check-in tergantung '
            'ketersediaan — tawarkan menghubungi resepsionis.\n'
            'Kondisi kamar hari ini:'
        )
        return header + '\n' + '\n'.join(lines)
    except Exception:  # pragma: no cover - DB may be empty during setup
        logger.exception('Gagal membaca status kamar untuk konteks chatbot')
    return (
        'Tipe kamar: Kamar Deluxe King Rp 1.800.000, Suite Eksekutif Horizon '
        'Rp 3.200.000, Grand Suite Presidensial Rp 5.500.000 per malam.'
    )


def call_gemini(message, history=None):
    """Call the Gemini generateContent REST endpoint. Returns reply string."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return (
            'Maaf, layanan AI sedang belum dikonfigurasi (GEMINI_API_KEY kosong). '
            'Silakan lanjutkan lewat Portal Tamu atau hubungi resepsionis. '
            'Jika Anda admin, isi GEMINI_API_KEY di environment lalu restart server.'
        )
    model = getattr(settings, 'GEMINI_MODEL', 'gemini-3.8-flash')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    contents = []
    for h in (history or [])[-8:]:
        role = 'model' if h.get('from') == 'bot' else 'user'
        text = str(h.get('text', ''))[:1000]
        if text.strip():
            contents.append({'role': role, 'parts': [{'text': text}]})
    prompt = f'{SYSTEM_PROMPT}\n\nKonteks hotel:\n{get_hotel_context()}\n\nPesan tamu: {message}'
    contents.append({'role': 'user', 'parts': [{'text': prompt}]})
    resp = None
    try:
        for attempt in (1, 2):
            try:
                resp = requests.post(
                    url,
                    params={'key': api_key},
                    json={'contents': contents, 'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 1024}},
                    timeout=20,
                )
                break
            except (requests.Timeout, requests.ConnectionError) as exc:
                logger.warning('Gemini request attempt %s failed: %s', attempt, exc)
                if attempt == 2:
                    return (
                        'Maaf, AI kami tidak merespons tepat waktu. '
                        'Silakan coba lagi sebentar lagi atau hubungi resepsionis.'
                    )
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            texts = [p.get('text', '') for p in parts if p.get('text')]
            if texts:
                return ''.join(texts).strip()
        return 'Maaf, saya belum menemukan jawaban. Bisa diulangi?'
    except requests.RequestException as exc:
        detail = _gemini_error_detail(exc)
        logger.exception('Gemini API error: %s', detail)
        if detail.startswith('404'):
            return (
                'Maaf, model AI yang dikonfigurasi tidak ditemukan oleh Google '
                f'({getattr(settings, "GEMINI_MODEL", "?")}). '
                'Minta admin menjalankan `python manage.py check_gemini` untuk melihat '
                'daftar model yang tersedia, atau hubungi resepsionis.'
            )
        if detail.startswith(('429', '503')) or 'overload' in detail.lower():
            return (
                'Maaf, layanan AI sedang padat-padanya. Coba lagi beberapa saat lagi, '
                'atau hubungi resepsionis.'
            )
        return (
            'Maaf, koneksi ke asisten AI sedang terganggu. '
            'Silakan coba lagi atau hubungi resepsionis.'
        )


def _gemini_error_detail(exc):
    """Extract Google's structured error message, e.g. '404 models/x is not found...'."""
    response = getattr(exc, 'response', None)
    if response is None:
        return str(exc)
    try:
        message = response.json().get('error', {}).get('message', '')
    except ValueError:
        message = response.text[:200]
    return f'{response.status_code} {message}' if message else f'{response.status_code} {exc}'
