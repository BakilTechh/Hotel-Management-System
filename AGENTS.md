# AGENTS.md — Nocturn Haven Hotel Management System

Practical reference for AI coding agents working on this repository.
Read the relevant sections before making changes.

---

## Project Overview

**Nocturn Haven** is a full-featured hotel management system built with Django 6.1.
It covers the complete guest journey: room discovery, reservation, payment verification,
check-in, check-out, review, and in-room dining via a room-service portal with an
AI concierge (Aurelia, powered by Google Gemini).

The application is primarily server-rendered Django templates. A small set of JSON
endpoints powers live polling (order tracking, concierge chat). There is no separate
front-end framework — the design system is custom CSS with vanilla JS.

**Django apps:**
| App | Responsibility |
|---|---|
| `accounts` | Registration, login, logout, role/permission system, guest profile |
| `rooms` | `RoomType`, `Room`, `RoomAvailability` models; room catalog views; review list |
| `reservations` | `Booking`, `Payment`, `PaymentEvent`, `PromoVoucher`, `Review`; the full reservation lifecycle |
| `dashboard` | Public home/facilities/offers pages, guest portal, staff report |
| `chatbot` | Room-service portal: menu, ordering, live tracking, Gemini concierge |
| `core` | Abstract base models (`TimeStampedModel`, `UserRelatedModel`) shared by other apps |
| `guests` | Empty stub — not in `INSTALLED_APPS`, contains no code |
| `config` | Django project settings and root URL configuration |

---

## Repository Structure

```
Hotel-Management-System/
├── manage.py                  # Django management entry point
├── requirements.txt           # Python dependencies
├── .env.example               # Template for local secrets (copy to .env)
├── db.sqlite3                 # SQLite DB (development only, gitignored)
├── config/
│   ├── settings.py            # All settings (reads env vars via python-dotenv)
│   ├── urls.py                # Root URL routing
│   ├── templates/base.html    # Admin area base template
│   └── wsgi.py / asgi.py
├── templates/                 # Project-level templates (public site shell)
│   └── public/
│       ├── base.html          # Public header/footer shell; all public pages extend this
│       ├── _stars.html        # Shared star-rating include
│       └── _review_card.html  # Shared review card include
├── static/                    # Project-level static files
│   ├── css/public-site.css    # Design tokens, components, responsive rules
│   ├── js/site.js             # Lenis scrolling, scroll reveals, mobile nav
│   └── js/vendor/lenis.min.js # Vendored (no CDN dependency)
├── accounts/                  # Auth and user management app
├── rooms/                     # Room catalog app
├── reservations/              # Core booking/payment app
│   ├── models.py              # PromoVoucher, Booking, Payment, PaymentEvent, Review
│   ├── services.py            # Transactional service layer (single gate for state changes)
│   ├── views.py               # CBVs + webhook FBV
│   ├── forms.py               # BookingForm, PaymentForm, ReviewForm
│   └── payment_processors/    # Payment processor integration code
├── dashboard/
│   ├── views.py               # DashboardView, FacilitiesView, OffersView, GuestDashboardView, ReportView
│   ├── templatetags/
│   │   ├── hotel_ui.py        # `rupiah` filter (e.g. 5610000 → 5.610.000)
│   │   └── hotel_admin.py     # `admin_metrics` tag (sidebar queue counts)
│   └── static/dashboard/css/
│       ├── guest-portal.css   # Guest portal shell
│       └── admin-theme.css    # Django admin burgundy/gold theme
├── chatbot/
│   ├── models.py              # RoomServiceMenuItem, ServiceOrder, ServiceOrderItem, ServiceOrderStatusLog
│   ├── services.py            # Gemini concierge: context building, rate limiting, session history
│   ├── menu.py                # available_menu(), build_menu_groups(), menu_stats(), recommended_items()
│   ├── menu_catalogue.py      # Static data: 34 curated menu items with Unsplash imagery
│   └── management/commands/
│       ├── seed_room_service_menu.py  # Idempotent menu seeder
│       └── check_gemini.py    # Verifies GEMINI_API_KEY and lists usable models
└── core/
    └── models.py              # TimeStampedModel, UserRelatedModel (abstract base classes)
```

---

## Setup and Development

### Prerequisites
- Python 3.9+ (3.14 confirmed on the development machine; `zoneinfo` is required)
- The `.venv` virtual environment is already present in the repository root

### First-time setup

```bash
# 1. Activate the virtual environment
source .venv/bin/activate                     # Linux/macOS
# .venv\Scripts\activate                      # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY if you want the AI concierge to work

# 4. Apply all migrations
python manage.py migrate

# 5. Seed the room-service menu (required for the portal to display items)
python manage.py seed_room_service_menu

# 6. (Optional) Seed demo guest reviews for the review wall
python manage.py seed_demo_reviews

# 7. Create a superuser for the Django admin
python manage.py createsuperuser

# 8. Start the development server
python manage.py runserver
```

### Environment variables

Loaded at startup from `.env` by `python-dotenv`. Never commit `.env`; it is gitignored.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | _(empty)_ | Gemini concierge key. Without it the concierge panel shows a fallback message; ordering still works. |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Gemini model name used by the concierge. |
| `GEMINI_TIMEOUT_MS` | `30000` | Per-request timeout in milliseconds. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `700` | Token cap for a concierge reply. |
| `PAYMENT_WEBHOOK_SECRET` | _(empty)_ | HMAC-SHA256 secret for the signed payment gateway webhook. While empty the endpoint returns 503. |
| `PAYMENT_PROOF_MAX_MB` | `5` | Maximum upload size for payment proof images. |

### Running tests

```bash
# Recommended: reuse the test database to avoid slow rebuild on every run
python manage.py test --keepdb

# First run (or after dropping the test DB):
python manage.py test

# Verbosity 2 shows each test name:
python manage.py test --verbosity=2 --keepdb
```

The full suite contains 178 tests and takes longer than 60 seconds to complete.
Run a single app when iterating:

```bash
python manage.py test accounts --keepdb
python manage.py test reservations --keepdb
python manage.py test chatbot --keepdb
```

### System and migration checks

```bash
# Verify Django configuration
python manage.py check

# Confirm no unapplied migration changes exist (exit 1 if migrations are missing)
python manage.py makemigrations --check --dry-run
```

These two commands, plus the full test suite, are the acceptance checks called out in README.md for changes to `Booking`, `Payment`, `Room`, or `Review` logic.

### Troubleshoot the Gemini key

```bash
python manage.py check_gemini
```

This verifies the key through the SDK, lists usable models, and sends a test prompt without opening a browser.

---

## Architecture and Coding Conventions

### Project language

Source code, comments, variable names, and docstrings are written in a mix of English and Bahasa Indonesia. Business-domain strings that are shown to users (form labels, error messages, admin action names) are in Bahasa Indonesia. Keep this convention when adding code.

### Models

- All domain models inherit from `core.models.TimeStampedModel` (adds `created_at`, `updated_at`).
- `Booking`, `Payment`, and `PromoVoucher` inherit from `reservations.models.BaseTransaction`, which extends `TimeStampedModel`.
- Use `db_table` and `db_column` overrides where present — they fix the actual database column names. Do not rename them without a matching migration.
- Monetary amounts are stored as `DecimalField` and rounded through `_money()` in `reservations/models.py` using `ROUND_HALF_UP`. Never use `float` for money.
- Tax rate is `TAX_RATE = Decimal('0.11')` (11%) defined in `reservations/models.py`. Use this constant.
- Database-level constraints (`CheckConstraint`) enforce checkout > checkin and positive guest count. Always run `makemigrations --check --dry-run` after model changes.

### Views

- Most views are class-based (`LoginRequiredMixin`, `CreateView`, `DetailView`, `ListView`).
- A minority of views are function-based, especially JSON API endpoints and the payment webhook.
- Authentication is required on all guest portal and reservation views. Use `LoginRequiredMixin` for CBVs and check `request.user.is_authenticated` for FBVs.
- Staff-only views use `UserPassesTestMixin` or the `role_required` / `staff_required` / `admin_required` decorators defined in `accounts/views.py`.
- Enforce object-level authorization in `get_queryset()` by filtering on `user=self.request.user` for non-staff users.

### URL patterns

- URL names defined in `config/urls.py` and each app's `urls.py` are used throughout the codebase via `reverse()` and `{% url %}`. Check existing names before adding new ones.
- Public pages live under the root. Guest portal pages live under `/dashboard/`. Reservation actions live under `/reservations/`. Room-service lives under `/room-service/`.

### Templates

- Public pages extend `templates/public/base.html`.
- Guest portal pages extend `dashboard/templates/dashboard/guest_base.html`.
- Reservation pages extend their own base in `reservations/templates/`.
- The design system uses CSS custom properties (design tokens) defined in `static/css/public-site.css`. Do not inline styles or introduce a CSS framework.
- Use the `rupiah` template filter (from `dashboard.templatetags.hotel_ui`) for all monetary values in templates: `{{ amount|rupiah }}`.

### Forms

- `BookingForm`, `PaymentForm`, `ReviewForm` live in `reservations/forms.py`.
- Guest registration and login use `AccountRegisterForm` and `AccountLoginForm` from `accounts/forms.py`.
- Server-side validation is the primary guard. Never rely solely on frontend validation.

### State transitions

- **All payment and booking state changes must go through `reservations/services.py`**, not by setting fields directly on the model in views. The service layer uses `select_for_update()` to prevent race conditions.
- Service functions: `submit_payment_proof()`, `verify_payment()`, `request_refund()`, `complete_refund()`, `process_gateway_event()`.
- Booking lifecycle methods (`check_in()`, `check_out()`, `batalkan_pesanan()`) are safe to call from views and admin actions because they internally use `select_for_update()` or delegate to the service layer.

### Transactions

Use `@transaction.atomic` or `with transaction.atomic()` for any operation that changes multiple related rows. Use `select_for_update()` when reading a row before conditionally updating it to prevent race conditions (especially booking availability checks and voucher quota changes).

### Static files

- Project-level CSS/JS lives in `static/`. App-level static files live in `<app>/static/<app>/`.
- `STATICFILES_DIRS = [BASE_DIR / 'static']` is set in settings.
- The Lenis smooth-scroll library is vendored at `static/js/vendor/lenis.min.js` — do not load it from a CDN.

---

## Business Logic and Domain Rules

### Core invariants

These rules are enforced at the model and service layers. Do not write code that bypasses them.

1. **Room availability**: A room can only be booked if `is_active=True`, `status='CLEAN'`, and it has no overlapping `Booking` in `BLOCKING_STATUSES` (`PENDING_PAYMENT`, `CONFIRMED`, `CHECKED_IN`). Use `Booking.available_rooms(check_in, check_out)` — never build your own overlap query.
2. **Guest count**: Cannot exceed the `RoomType.capacity` of the selected room.
3. **Dates**: `check_out` must be strictly after `check_in` (enforced by DB constraint).
4. **Payment record**: Every `Booking` created through the application receives exactly one `Payment` record in `UNPAID` status. Use `booking.ensure_payment()`.
5. **Booking confirmation gate**: A booking moves to `CONFIRMED` only when its payment reaches `VERIFIED`. `Booking.konfirmasi()` enforces this; so does `verify_payment()` in services.
6. **Stay lifecycle sequence**: `PENDING_PAYMENT → CONFIRMED → CHECKED_IN → CHECKED_OUT`. `CANCELLED` is reachable from `PENDING_PAYMENT` and `CONFIRMED` only.
7. **Check-in requires CONFIRMED**. **Check-out requires CHECKED_IN** and marks the room `DIRTY`.
8. **Reviews**: One per booking. Only allowed after `CHECKED_OUT`. `Review.booking` is a `OneToOneField`.
9. **Voucher quota**: Quota is decremented via `PromoVoucher._consume_quota()` inside a `select_for_update()` transaction. Cancellation returns the quota via `_return_quota()`. Never manipulate `kuota_penggunaan` directly.
10. **Payment status flow (manual)**: `UNPAID → PENDING_VERIFICATION → VERIFIED`, with `REJECTED` as a retry path. `VERIFIED → REFUND_PENDING → REFUNDED` after cancellation. Invalid transitions raise `InvalidTransition`.
11. **Cancelling a verified booking** moves its payment to `REFUND_PENDING` (not `REFUNDED`). Staff must explicitly complete the refund.
12. **Payment proof** (`bukti_transfer_url`) is an `ImageField`. Files are streamed through `PaymentProofView`, which restricts access to the booking owner and staff. Never serve proof files directly from `MEDIA_URL`.
13. **Payment webhook**: Must carry a valid HMAC-SHA256 signature in `X-Nocturn-Signature`. Replays are deduplicated via `PaymentEvent.event_id` (unique). Returns 503 when `PAYMENT_WEBHOOK_SECRET` is unset.

### Room-service rules

- Ordering requires an eligible booking: `status_pesanan` in `PENDING_PAYMENT`, `CONFIRMED`, or `CHECKED_IN`, and `check_out >= today`.
- Orders are capped at 15 line items and Rp 3,000,000 total for self-service checkout. Larger orders are routed to reception.
- Menu prices are always copied from the live `RoomServiceMenuItem` records server-side. Client-supplied prices are ignored.
- Order status flow: `INCOMING → PROCESSING → DELIVERED` (delivery) or `INCOMING → PROCESSING → READY` (pickup). `CANCELLED` is available before a final status. Every transition writes to `ServiceOrderStatusLog`.
- Fulfillment types: `DELIVERY` (room delivery) and `PICKUP` (restaurant pickup).
- The concierge (Aurelia) cannot place, modify, or cancel orders. It only provides information and recommendations.

### Pricing calculation

`Booking.hitung_total_biaya()` computes:
- `total_harga_dasar` = `price_per_night × durasi_malam`
- `diskon_voucher` = voucher discount (percent or fixed, capped at base price)
- `pajak_dan_layanan` = 11% of the post-discount subtotal
- `total_biaya_akhir` = post-discount subtotal + tax

Always call `hitung_total_biaya()` before `konsumsi_voucher()` before `ensure_payment()`. This sequence is already established in `BookingCreateView._create_booking()`.

---

## Testing and Quality Assurance

### Test suite

The test suite has 178 tests across five apps. Tests use Django's `TestCase` with the test client and `unittest.mock`. No external libraries (pytest, factory-boy, etc.) are used.

```bash
# Full suite (slow; >90 seconds due to full DB setup each run)
python manage.py test --keepdb

# Single app (faster for iterating)
python manage.py test reservations --keepdb
python manage.py test chatbot --keepdb
```

**Test suite status at the time this file was written**: The full suite ran to completion with `--keepdb` (exit 0). Individual app runs for `accounts`, `rooms`, and `dashboard` completed successfully (17 tests passed). The full 178-test suite also passed but takes over 90 seconds.

### What to test when changing business logic

- **Booking creation**: availability check, pricing, payment record creation
- **Payment state transitions**: valid and invalid transitions, idempotency of approval
- **Cancellation**: voucher quota return, payment status change to REFUND_PENDING
- **Room-service orders**: order caps, price copy from live menu, status transitions, fulfillment routing
- **Access control**: guests can only see their own bookings, staff can see all

### Acceptance checks before merging

These three commands are specified in the README as required before changing `Booking`, `Payment`, `Room`, or `Review` logic:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

---

## Security and Data Integrity

1. **Never commit secrets.** `.env` is gitignored. The `SECRET_KEY` in `settings.py` is the insecure development default — replace it before any deployment. `GEMINI_API_KEY` and `PAYMENT_WEBHOOK_SECRET` must only be set via environment variables.
2. **CSRF**: The project uses `CsrfViewMiddleware`. JSON API endpoints that accept mutations use `@csrf_exempt` intentionally (they rely on session authentication instead). Do not add `@csrf_exempt` to any HTML-form endpoint.
3. **Authentication and authorization**: Always check `request.user.is_authenticated` in FBVs. For object-level authorization, verify `booking.user == request.user` (or use staff check) before any read or mutation. Never expose another guest's booking data.
4. **Payment proof files**: Must be served through `PaymentProofView`. Never add `MEDIA_URL` to `urlpatterns` in production (the settings file already restricts this to `DEBUG=True`).
5. **Webhook signature**: All payment gateway webhooks must be verified via HMAC-SHA256 against `PAYMENT_WEBHOOK_SECRET`. Reject requests with a missing or invalid signature with 401.
6. **State transitions**: Use `select_for_update()` before any conditional update on `Booking`, `Payment`, or `PromoVoucher`. Never update these models with `queryset.update()` for lifecycle transitions.
7. **File uploads**: Proof-of-payment uploads are validated against `PAYMENT_ALLOWED_PROOF_TYPES` (jpeg, png, webp) and capped at `PAYMENT_PROOF_MAX_MB` MB. Apply the same pattern for any new file upload.
8. **Gemini context**: The concierge grounding data is scoped to the signed-in guest only. Never include other guests' bookings, payments, or personal data in the Gemini context.
9. **No raw SQL**: Use the ORM for all database access. If a queryset is used for a conditional update, lock the row first with `select_for_update()`.
10. **User roles**: Roles are stored in `GuestProfile.role` (`GUEST`, `STAFF`, `ADMIN`). Django's `is_staff` and `is_active` flags are kept in sync with `GuestProfile` via `_sync()` in `accounts/views.py`. Do not set `is_staff` directly without updating the profile.

---

## AI Agent Working Rules

1. **Read before writing.** Read the relevant model, view, service, or template before proposing any change. Do not guess at field names, status values, or method signatures.
2. **Understand before rewriting.** Understand the existing implementation before proposing a structural change. Mixed-language comments and variable names (`tanggal_check_in`, `batalkan_pesanan`) are intentional — follow them.
3. **Smallest coherent change.** Solve the specific problem. Do not refactor unrelated code, add new dependencies, or introduce new architecture patterns.
4. **Follow existing conventions.** Use the existing naming style (Indonesian field names on business models, English on infrastructure), the `rupiah` filter for currency, and `TimeStampedModel` for new models.
5. **Never remove existing functionality silently.** If a change removes a feature, state it explicitly and confirm before proceeding.
6. **State transitions belong in services.** Changes to `Booking.status_pesanan` or `Payment.status_pembayaran` must go through `reservations/services.py`. Do not set these fields directly in views.
7. **Migration discipline.** Run `makemigrations --check --dry-run` after any model change. Never edit existing migration files. Write new migrations for every schema change.
8. **Add tests for behavior changes.** Any change to booking, payment, voucher, or room-service logic should include or update a test in the corresponding `tests.py`.
9. **Run checks and report results honestly.** Run `manage.py check`, `makemigrations --check --dry-run`, and the relevant test app(s). Report exactly which tests passed, which failed, and which were not run. Do not claim tests pass unless you actually ran them and saw the result.
10. **Explain important decisions.** Note assumptions (e.g., "I assumed the 11% tax rate applies to the subtotal after discount, consistent with `hitung_total_biaya()`"), limitations, and any required manual steps (e.g., creating a superuser, seeding data).
11. **Do not fabricate.** Never invent function names, field names, status values, or test results. If something is unclear, say so.
12. **Destructive commands require confirmation.** Do not run `migrate --fake`, `flush`, `dbshell DROP TABLE`, `git reset --hard`, `git push --force`, or equivalent without explicit user authorization.

---

## Git and Collaboration

- The repository has no CI/CD configuration (no `.github/` directory).
- There is no enforced commit message convention in the repository.
- Do not commit, push, or rewrite history unless explicitly asked.
- When staging changes, prefer adding specific files (`git add accounts/models.py`) over `git add .` or `git add -A`.
- `.env`, `db.sqlite3`, `media/`, and `__pycache__/` are gitignored. Never commit them.
- The `SECRET_KEY` in `settings.py` is the insecure development default. Do not commit a real secret key.

---

## Key File Reference

| File | Why an agent would read it |
|---|---|
| `reservations/models.py` | All booking, payment, voucher, and review logic |
| `reservations/services.py` | The only correct way to change payment/booking state |
| `rooms/models.py` | Room availability and RoomType pricing |
| `accounts/views.py` | Role system, `role_required` decorator, auth endpoints |
| `chatbot/models.py` | ServiceOrder status flow, menu item model |
| `chatbot/services.py` | Gemini concierge: context building, rate limiting |
| `config/settings.py` | Environment variables, installed apps, database, media, Gemini config |
| `config/urls.py` | All top-level URL names and app includes |
| `README.md` | Setup instructions, main routes, business rules summary |
