# Hotel Management System

Hotel Management System berbasis Django.
# Hotel Management System

Hotel Management System berbasis Django.

## Tech Stack

- Python
- Django
- Django Templates
- Bootstrap
- SQLite (development)
- PostgreSQL (production)

## Setup

1. Clone repository
2. Create virtual environment
3. Install dependencies
4. Run migration
5. Run development server

## Core business rules

- Check-out must be later than check-in.
- Guest count cannot exceed the selected Room Type capacity.
- Only active CLEAN rooms can be booked.
- A room cannot have overlapping active bookings.
- Every application-created Booking receives one UNPAID Payment record.
- A Booking becomes CONFIRMED only through verified payment flow.
- Check-in requires CONFIRMED; check-out requires CHECKED_IN.
- Check-out records its time and marks the room DIRTY.
- Review requires CHECKED_OUT and is limited to one per Booking.
- Guests can only access their own Booking data; staff access is Admin-only.

## Main routes

- `/rooms/`: room catalog and date availability search.
- `/reservations/buat/`: create a booking.
- `/reservations/riwayat/`: guest booking history.
- `/room-service/`: authenticated room-service chatbot.
- `/dashboard/laporan/`: staff-only operational report.
- `/admin/`: Room Type, Room, Booking, Payment, Review, and user management.

## Acceptance test

Run these commands before changing Booking, Payment, Room, or Review rules:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check
.\.venv\Scripts\python.exe manage.py test
```

## Room Service Chatbot (Gemini)

- Page: `/room-service/` (requires login), API: `/room-service/api/chat/`
- Set your key before running (never commit it):
  - PowerShell: `$env:GEMINI_API_KEY="..."; $env:GEMINI_MODEL="gemini-3.8-flash"`
  - Optional: `GEMINI_MODEL` defaults to `gemini-2.0-flash`
- Get a key: https://aistudio.google.com/apikey
- Structured orders (food → reservation code → confirm) run server-side
  against your `bookings` table; Gemini is only the fallback for open Q&A.
- Troubleshoot the key/model without opening the browser:
  `python manage.py check_gemini` — verifies the key, lists usable models,
  and sends a test prompt. If the chat says the model was "not found",
  set `$env:GEMINI_MODEL` to one of the listed names.

## Verifikasi Pembayaran (untuk staf)

1. Buat akun admin (sekali saja): `python manage.py createsuperuser`
2. Buka `http://localhost:8000/admin/` dan login sebagai admin.
3. Alur tamu: buat reservasi → "Lanjutkan Pembayaran" → upload bukti
   transfer (status pembayaran menjadi `Menunggu Verifikasi`).
4. Alur staf: Admin → Payments → centang pembayaran → pilih aksi
   "Setujui pembayaran (booking → Confirmed)" → Go. Booking terkait
   otomatis menjadi `Confirmed`; aksi "Tolak pembayaran" menolaknya.