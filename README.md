# Hotel Management System

Hotel Management System berbasis Django untuk **Nocturn Haven**.

## Tech Stack

- Python
- Django
- Django Templates
- Custom CSS design system (no CSS framework) + vanilla JS with vendored Lenis
- SQLite (development)
- PostgreSQL (production)

## Setup

1. Clone repository
2. Create virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Run migration: `python manage.py migrate`
5. Run development server: `python manage.py runserver`

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | _(empty)_ | Room-service chatbot key (https://aistudio.google.com/apikey). |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Chat model name. |
| `PAYMENT_WEBHOOK_SECRET` | _(empty)_ | HMAC-SHA256 secret for the payment gateway webhook. While unset, the webhook endpoint answers `503`. |
| `PAYMENT_PROOF_MAX_MB` | `5` | Maximum upload size for bank-transfer proof images. |

Never commit keys or secrets. Configure them in your shell or deployment platform.

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
- Payment status flows one way: `UNPAID → PENDING_VERIFICATION → VERIFIED`, with
  `REJECTED` retries and `VERIFIED → REFUND_PENDING → REFUNDED` after a
  cancelled booking.
- Cancelling a verified booking returns the voucher quota and moves the payment
  to `REFUND_PENDING`.
- Room service ordering requires an active or upcoming (not cancelled) stay.

## Main routes

- `/`: public home page.
- `/rooms/`: room catalog and date availability search.
- `/rooms/ulasan/`: review listing.
- `/reservations/buat/`: create a booking.
- `/reservations/riwayat/`: guest booking history.
- `/reservations/<id>/bayar/`: upload payment proof.
- `/reservations/payments/<id>/proof/`: authenticated proof download (owner or staff).
- `/reservations/payments/webhook/`: signed payment-gateway webhook.
- `/reservations/resepsionis/`: reception desk (staff).
- `/dashboard/`: guest portal dashboard.
- `/dashboard/laporan/`: staff-only operational report.
- `/accounts/profile/`: guest profile and preferences.
- `/accounts/password/`: password change.
- `/room-service/`: permanent redirect (301) to the room-service portal.
- `/room-service/portal/`: room-service ordering portal (guest portal).
- `/admin/`: Room Type, Room, Booking, Payment, Review, and user management.

## Ulasan tamu (reviews)

- `/rooms/ulasan/`: public review wall — average score, five-star distribution
  bars, per-star filter chips (`?rating=5…1`) and the verified-review cards.
- `/reservations/<booking_id>/review/`: star form for a `CHECKED_OUT` booking
  the guest owns (one review per booking).
- Guests with a checked-out, not-yet-reviewed booking get a nudge card on the
  wall that links straight to the form.
- Reviews show the guest's full name with the username as fallback, plus
  initials for the avatar.

## Front-end & design system

Public pages share one shell and one stylesheet, so the site, the guest portal
and the admin look like one hotel:

- `templates/public/base.html`: header (Home · Room & Suites · Facilities ·
  Offers · Ulasan Tamu · Portal Tamu · About Us), guest profile chip, message
  region, footer, and the deferred script tags. `templates/public/_stars.html`
  and `_review_card.html` are shared includes.
- `static/css/public-site.css`: design tokens (burgundy `#710000`, gold
  `#b68b35`, warm canvas `#f7f4f0`, Playfair Display + DM Sans), buttons,
  cards, filters, calendar, auth screens and the responsive rules.
- `dashboard/static/dashboard/css/guest-portal.css`: guest portal shell;
  `dashboard/static/dashboard/css/admin-theme.css`: Django admin theme.
- `static/js/site.js`: Lenis smooth scrolling, scroll reveals, pointer tilt and
  the mobile navigation; `static/js/admin-motion.js` brings the same motion to
  the admin. `static/js/vendor/lenis.min.js` is vendored (no CDN).
- Motion is opt-out: with `prefers-reduced-motion: reduce` (or without the
  Lenis file) the pages fall back to plain document flow and every
  `[data-reveal]` element stays visible.
- Webfonts load asynchronously (`media="print"` swap), so a slow or blocked
  font host can never delay rendering or the deferred scripts.
- `dashboard/templatetags/hotel_ui.py` provides the `rupiah` filter used for
  every amount in the guest-facing templates (`5610000` → `5.610.000`).

## Guest portal

A branded portal with a sidebar shell for logged-in guests:

- **Dashboard** (`/dashboard/`): upcoming stay, payment status, quick actions.
- **Profile** (`/accounts/profile/`): personal info, contact details, and
  account preferences; password change at `/accounts/password/`.
- **Booking history**: reservations with room, dates, price breakdown, and
  payment status (Pending / Paid / Failed / Refunded group).
- **Room service** (`/room-service/portal/`): menu by category, search and
  filters, quantity inputs with a live order total, and order history for
  guests with an eligible stay.

Payment proofs are never served from `MEDIA_URL`; they are streamed through
`PaymentProofView`, which allows only the booking owner and staff.

## Payment webhook

Set `PAYMENT_WEBHOOK_SECRET`, then point the gateway at
`/reservations/payments/webhook/`. Requests must carry an HMAC-SHA256 signature
over the raw body in the `X-Nocturn-Signature` header (`sha256=` prefix
accepted). The JSON payload requires `event_id`, `type`, `booking_id`, and
`amount` for `payment.paid` events. Replays are idempotent through the
`PaymentEvent` ledger: `401` on a bad signature, `409` on an invalid state
transition, `503` while the secret is unset, and `duplicate` on replay.

## Verifikasi Pembayaran (untuk staf)

1. Buat akun admin (sekali saja): `python manage.py createsuperuser`
2. Buka `http://localhost:8000/admin/` dan login sebagai admin. Tampilan admin
   memakai tema burgundy/gold yang sama dengan portal tamu.
3. Alur tamu: buat reservasi → "Lanjutkan Pembayaran" → upload bukti
   transfer (status pembayaran menjadi `Menunggu Verifikasi`).
4. Alur staf: Admin → Payments → centang pembayaran → pilih aksi
   "Setujui pembayaran (booking → Confirmed)" → Go. Booking terkait
   otomatis menjadi `Confirmed`; aksi "Tolak pembayaran" menolaknya.

## Concierge assistant (Gemini)

- The conversational room-service page has been retired: everything
  room-service lives in the structured portal at `/room-service/portal/`
  (menu, quantities, live total, order history).
- What remains is the assistant layer in `chatbot/services.py`: the system
  prompt, a live hotel snapshot used as grounding context, and the Gemini REST
  call with its error handling.
- Set the key before running (never commit it):
  - PowerShell: `$env:GEMINI_API_KEY="..."; $env:GEMINI_MODEL="gemini-3.8-flash"`
  - Bash: `export GEMINI_API_KEY="..."; export GEMINI_MODEL="gemini-3.8-flash"`
- Get a key: https://aistudio.google.com/apikey
- Troubleshoot the key/model without opening the browser:
  `python manage.py check_gemini` — verifies the key, lists usable models,
  and sends a test prompt. If the assistant says the model was "not found",
  set the model to one of the listed names.
- In the guest portal, "Hubungi Concierge" opens a mailto draft to the hotel
  inbox, so guests always have a working channel even without an API key.

## Acceptance test

Run these commands before changing Booking, Payment, Room, or Review rules:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```
