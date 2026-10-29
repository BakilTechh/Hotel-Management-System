# How to Access the Admin Dashboard

## Quick Start

### 1. Start the Server
```bash
cd /home/zak/Work/Hotel-Management-System
source .venv/bin/activate
python manage.py runserver
```

### 2. Login URL
Go to: **http://localhost:8000/accounts/login/**

### 3. Login Behavior

**After logging in, you will be automatically redirected based on your role:**

#### For Staff/Admin Users:
- **Automatically redirected to:** `http://localhost:8000/dashboard/admin-panel/`
- This is the main admin dashboard with all management features

#### For Regular Guests:
- **Automatically redirected to:** `http://localhost:8000/dashboard/`
- This is the guest portal for personal bookings

---

## Creating Admin/Staff Accounts

### Option 1: Using Django Management Command
```bash
python manage.py createsuperuser
```
Follow the prompts:
- Username: (your choice)
- Email: (your email)
- Password: (your password)

This creates an **ADMIN** user who has full access.

### Option 2: Through Existing Admin Account
1. Login as an existing admin
2. Go to Staff Management: `http://localhost:8000/dashboard/admin-panel/staff/`
3. Use the "Staff Management" interface to promote users or change roles

---

## User Roles

### GUEST (Regular Customer)
- Can book rooms
- View their own bookings
- Use room service
- Write reviews
- Access: `/dashboard/` (Guest Portal)

### STAFF (Hotel Staff)
- All GUEST privileges
- Manage reservations
- Verify payments
- Check-in/check-out guests
- Manage room service orders
- View housekeeping status
- Access: `/dashboard/admin-panel/` (Admin Dashboard)

### ADMIN (Administrator)
- All STAFF privileges
- Manage staff accounts
- Assign/change roles
- Full system access
- Access: `/dashboard/admin-panel/` (Admin Dashboard)

---

## What Happened to Django's Built-in Admin?

**Django's `/admin/` URL has been replaced with the custom admin dashboard.**

### Changes Made:
1. **URL `/admin/` now redirects to `/dashboard/admin-panel/`**
2. **Login automatically sends staff to custom admin dashboard**
3. **All admin features migrated to custom dashboard**

### Why This Change?
- **Unified Experience**: One consistent interface for hotel operations
- **Better UX**: Designed specifically for hotel management workflow
- **Role-Based**: Proper guest vs staff separation
- **Branded**: Matches your hotel's design system

### If You Need Django Admin (Emergency Only):
The Django admin is still available but disabled by default. To re-enable:

1. Edit `config/urls.py`
2. Uncomment this line:
   ```python
   path('django-admin/', admin.site.urls),
   ```
3. Access at: `http://localhost:8000/django-admin/`

**Note:** This is only for emergency database access. Use the custom admin dashboard for normal operations.

---

## Complete URL Structure

### Public URLs (No Login Required)
- `/` - Homepage
- `/rooms/` - Room catalog
- `/facilities/` - Hotel facilities
- `/offers/` - Special offers
- `/about/` - About page
- `/accounts/login/` - **LOGIN PAGE** ⭐
- `/accounts/register/` - Registration

### Guest Portal (Login Required)
- `/dashboard/` - Guest dashboard
- `/dashboard/laporan/` - Reports (staff only)
- `/dashboard/housekeeping/` - Housekeeping (staff only)

### Admin Dashboard (Staff/Admin Only)
All under: `/dashboard/admin-panel/`

- `/dashboard/admin-panel/` - **Main admin dashboard** ⭐
- `/dashboard/admin-panel/reservations/` - All reservations
- `/dashboard/admin-panel/payments/` - Payment verification
- `/dashboard/admin-panel/reception/` - Check-in/check-out
- `/dashboard/admin-panel/rooms/` - Room management
- `/dashboard/admin-panel/service-orders/` - Room service orders
- `/dashboard/admin-panel/guests/` - Guest directory
- `/dashboard/admin-panel/staff/` - Staff management (admin only)

---

## Testing Your Setup

### Step-by-Step Test:

1. **Create a superuser:**
   ```bash
   python manage.py createsuperuser
   ```

2. **Start the server:**
   ```bash
   python manage.py runserver
   ```

3. **Open browser and go to:**
   ```
   http://localhost:8000/accounts/login/
   ```

4. **Login with your superuser credentials**

5. **You should automatically land on:**
   ```
   http://localhost:8000/dashboard/admin-panel/
   ```

6. **You should see:**
   - Admin dashboard with real metrics
   - Sidebar navigation with all admin modules
   - Today's arrivals and departures
   - Payment verification queue
   - Service orders
   - Room status overview

### If Something Goes Wrong:

**Problem:** Login doesn't redirect to admin dashboard
- **Check:** Is your user marked as staff? 
- **Fix:** In Django shell:
  ```python
  from django.contrib.auth.models import User
  user = User.objects.get(username='your_username')
  user.is_staff = True
  user.save()
  ```

**Problem:** Get "Permission Denied" on admin pages
- **Check:** Does your user have a GuestProfile with role?
- **Fix:** In Django shell:
  ```python
  from accounts.models import GuestProfile
  from django.contrib.auth.models import User
  user = User.objects.get(username='your_username')
  profile, created = GuestProfile.objects.get_or_create(user=user)
  profile.role = 'ADMIN'
  profile.save()
  ```

**Problem:** Old `/admin/` bookmarks don't work
- **Solution:** They now redirect to `/dashboard/admin-panel/` automatically
- **Update your bookmarks** to the new URL

---

## Navigation Tips

### From Guest Portal to Admin Dashboard:
If you're on the guest portal (`/dashboard/`) and have staff access:
1. Look at the sidebar
2. Click "Dashboard Admin" at the top of the "Jelajahi hotel" section
3. You'll be taken to `/dashboard/admin-panel/`

### From Admin Dashboard to Guest Portal:
If you're on admin dashboard and want guest view:
1. Look at sidebar "Akses lainnya" section
2. Click "Portal Tamu"
3. You'll be taken to `/dashboard/`

### Quick Access Shortcuts:
- **Admin Dashboard:** `/dashboard/admin-panel/`
- **Check-in/out:** `/dashboard/admin-panel/reception/`
- **Payments:** `/dashboard/admin-panel/payments/`
- **Reservations:** `/dashboard/admin-panel/reservations/`

---

## Summary

✅ **Login Page:** `http://localhost:8000/accounts/login/`

✅ **Staff/Admin Redirected To:** `http://localhost:8000/dashboard/admin-panel/`

✅ **Guests Redirected To:** `http://localhost:8000/dashboard/`

✅ **Django's `/admin/` Replaced:** Now redirects to custom admin dashboard

✅ **All admin features:** Available in the custom dashboard

🎯 **You're all set!** Just login and you'll automatically go to the right place based on your role.
