# Admin Dashboard URL Structure

## Overview
The admin dashboard URLs follow Django conventions and are organized under `/dashboard/admin-panel/` to avoid conflicts with Django's built-in `/admin/`.

## URL Hierarchy

### Public Routes (No Authentication)
- `/` - Homepage (public site)
- `/rooms/` - Room catalog
- `/facilities/` - Hotel facilities
- `/offers/` - Special offers
- `/about/` - About page
- `/accounts/login/` - Login page
- `/accounts/register/` - Registration page

### Guest Portal (Authentication Required)
- `/dashboard/` - Guest dashboard
- `/reservations/` - Guest booking management
- `/room-service/portal/` - Room service ordering
- `/accounts/profile/` - Guest profile

### Admin Dashboard (Staff/Admin Only)
All admin routes are prefixed with `/dashboard/admin-panel/`

#### Main Admin Dashboard
- `/dashboard/admin-panel/` - Admin overview dashboard
  - View: `AdminDashboardView`
  - URL name: `admin_dashboard`
  - Shows: Real-time metrics, arrivals, departures, payment queue, service orders

#### Reservations Management
- `/dashboard/admin-panel/reservations/` - All reservations list
  - View: `StaffReservationListView`
  - URL name: `staff_reservations`
  - Features: Search, filter, pagination

#### Payment Verification
- `/dashboard/admin-panel/payments/` - Payment verification queue
  - View: `PaymentVerificationView`
  - URL name: `payment_verification`
  - Shows: Pending payments, recent verifications

- `/dashboard/admin-panel/payments/verify/` - Payment verify action (POST)
  - View: `PaymentVerifyActionView`
  - URL name: `payment_verify_action`
  - Actions: Approve/reject payments

#### Reception Desk (Check-In/Check-Out)
- `/dashboard/admin-panel/reception/` - Reception desk interface
  - View: `CheckInOutView`
  - URL name: `reception`
  - Shows: Today's arrivals, departures, current guests

- `/dashboard/admin-panel/reception/checkin/` - Check-in action (POST)
  - View: `CheckInActionView`
  - URL name: `checkin_action`

- `/dashboard/admin-panel/reception/checkout/` - Check-out action (POST)
  - View: `CheckOutActionView`
  - URL name: `checkout_action`

#### Room Management
- `/dashboard/admin-panel/rooms/` - Room inventory management
  - View: `RoomManagementView`
  - URL name: `room_management`
  - Shows: Room types, individual rooms, status

#### Service Orders
- `/dashboard/admin-panel/service-orders/` - Room service order queue
  - View: `ServiceOrderQueueStaffView`
  - URL name: `service_order_queue_staff`
  - Features: Filter by status, service type, search

- `/dashboard/admin-panel/service-orders/update/` - Update order status (POST)
  - View: `ServiceOrderUpdateStatusView`
  - URL name: `service_order_update_status`

#### Guest Management
- `/dashboard/admin-panel/guests/` - Guest directory
  - View: `GuestDirectoryView`
  - URL name: `guest_directory`
  - Features: Search guests, view statistics

- `/dashboard/admin-panel/guests/<int:pk>/` - Guest detail
  - View: `GuestDetailView`
  - URL name: `guest_detail`
  - Shows: Guest profile, booking history

#### Staff Management (Admin Only)
- `/dashboard/admin-panel/staff/` - Staff management
  - View: `StaffManagementView`
  - URL name: `staff_management`
  - Features: View staff, manage roles

- `/dashboard/admin-panel/staff/<int:pk>/` - Staff detail
  - View: `StaffDetailView`
  - URL name: `staff_detail`
  - Shows: Staff profile, verification activity

- `/dashboard/admin-panel/staff/update-role/` - Update staff role (POST)
  - View: `StaffUpdateRoleView`
  - URL name: `staff_update_role`

- `/dashboard/admin-panel/staff/toggle-active/` - Activate/deactivate staff (POST)
  - View: `StaffToggleActiveView`
  - URL name: `staff_toggle_active`

#### Housekeeping
- `/dashboard/housekeeping/` - Housekeeping dashboard
  - View: `HousekeepingView`
  - URL name: `housekeeping`
  - Shows: Room status, cleaning tasks

- `/dashboard/housekeeping/update/` - Update room status (POST)
  - View: `HousekeepingUpdateView`
  - URL name: `housekeeping_update`

#### Reports
- `/dashboard/laporan/` - Reports and analytics
  - View: `ReportView`
  - URL name: `report`
  - Shows: Booking trends, revenue, occupancy

### Django Built-in Admin
- `/admin/` - Django admin interface (preserved)
  - Django's default admin site
  - Used for low-level data management

## Navigation Flow

### For Regular Guests:
1. Login → `/dashboard/` (Guest Dashboard)
2. Access guest features from sidebar
3. Can see staff links in sidebar if they have staff role

### For Staff:
1. Login → `/dashboard/` (Guest Dashboard by default)
2. Click "Dashboard Admin" link → `/dashboard/admin-panel/`
3. Access all admin features from admin sidebar
4. Can return to guest portal anytime

### For Administrators:
1. Login → `/dashboard/` or directly to `/dashboard/admin-panel/`
2. Full access to all admin features
3. Additional staff management capabilities
4. Can access Django admin at `/admin/`

## Permission Requirements

### Guest Portal Routes
- Required: `user.is_authenticated`
- Object-level: Users can only see their own data

### Admin Dashboard Routes
- Required: `user.is_staff` OR `user.guest_profile.role in ('STAFF', 'ADMIN')`
- Enforced in: `UserPassesTestMixin.test_func()`

### Staff Management Routes
- Required: `user.guest_profile.role == 'ADMIN'`
- Only administrators can manage staff

### Post Actions (Check-in, Payment Verify, etc.)
- Required: Staff/Admin role
- CSRF protection enabled
- Confirmation dialogs in UI
- Server-side validation

## URL Name Reference

Use Django's `{% url %}` template tag or `reverse()` function:

```python
# In views
from django.urls import reverse
url = reverse('admin_dashboard')  # /dashboard/admin-panel/

# In templates
{% url 'admin_dashboard' %}
{% url 'staff_reservations' %}
{% url 'payment_verification' %}
{% url 'guest_detail' guest.pk %}
```

## Migration Notes

**Changed URLs:**
- Old: `/dashboard/admin/` 
- New: `/dashboard/admin-panel/`

**Reason:** 
- Avoids confusion with Django's `/admin/`
- Follows Django URL conventions
- More descriptive and clear

**Templates using these URLs:**
- `admin_base.html` - Admin sidebar navigation
- `guest_base.html` - Staff quick links
- All admin dashboard templates
