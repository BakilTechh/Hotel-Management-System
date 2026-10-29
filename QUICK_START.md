# Quick Start Guide - Admin Dashboard

## 🚀 Start the Server

```bash
cd /home/zak/Work/Hotel-Management-System
source .venv/bin/activate
python manage.py runserver
```

---

## 👤 Create Admin User (First Time)

```bash
python manage.py createsuperuser
```

Enter:
- Username: `admin`
- Email: `admin@hotel.com`
- Password: (your password)

---

## 🔐 Login

**URL:** http://localhost:8000/accounts/login/

**Credentials:**
- Email: `admin@hotel.com`
- Password: (the password you set)

**After login, you'll be automatically redirected to:**
http://localhost:8000/dashboard/admin-panel/

---

## 📍 Key URLs

| What | URL |
|------|-----|
| **Login Page** | http://localhost:8000/accounts/login/ |
| **Admin Dashboard** | http://localhost:8000/dashboard/admin-panel/ |
| **Guest Dashboard** | http://localhost:8000/dashboard/ |
| **Public Site** | http://localhost:8000/ |

---

## 🎯 What You'll See After Login

### Admin Dashboard Home
- Room statistics (available, occupied, maintenance)
- Today's check-ins and check-outs
- Pending payment verifications
- Active room service orders
- Recent booking activity

### Sidebar Navigation
- **Dashboard Admin** - Overview
- **Manajemen Reservasi** - All bookings
- **Check-In / Check-Out** - Reception desk
- **Verifikasi Pembayaran** - Payment queue
- **Housekeeping** - Room status
- **Room Service Orders** - Food orders
- **Manajemen Kamar** - Room inventory
- **Direktori Tamu** - Guest list
- **Manajemen Staff** - Staff accounts (admin only)
- **Laporan & Analitik** - Reports

---

## 🔑 Create Additional Staff

### Quick Method (Django Shell):
```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from accounts.models import GuestProfile

# Create staff user
user = User.objects.create_user(
    username='receptionist',
    email='receptionist@hotel.com',
    password='password123',
    first_name='Jane',
    last_name='Doe'
)
user.is_staff = True
user.save()

# Set role
GuestProfile.objects.create(
    user=user,
    role='STAFF',  # or 'ADMIN' for full access
    phone_number='081234567890'
)

print("✅ Staff user created!")
exit()
```

Now they can login at the same URL with:
- Email: `receptionist@hotel.com`
- Password: `password123`

---

## 📊 Common Admin Tasks

### Check-In a Guest
1. Go to: Admin Dashboard → Check-In / Check-Out
2. Find today's arrivals
3. Click "Check-In" button
4. Confirm

### Verify Payment
1. Go to: Admin Dashboard → Verifikasi Pembayaran
2. See pending payments list
3. Click "Lihat Bukti" to view proof
4. Click "Setujui" to approve or "Tolak" to reject

### View All Reservations
1. Go to: Admin Dashboard → Manajemen Reservasi
2. Use filters to search
3. Click any booking code to see details

### Manage Room Service Orders
1. Go to: Admin Dashboard → Room Service Orders
2. See active orders
3. Click "Proses" to start preparing
4. Click "Diantar" when delivered

---

## ⚠️ Important Notes

### Django's Built-in Admin is Replaced
- Old URL `/admin/` now redirects to custom admin dashboard
- No need to use Django's admin interface
- Everything is in the custom dashboard

### Roles Explained
- **GUEST** - Regular customers (can't access admin)
- **STAFF** - Hotel employees (full operational access)
- **ADMIN** - System administrators (can manage staff)

### Security
- Always use strong passwords
- Don't share admin credentials
- Staff can't promote themselves to admin
- All actions are logged with user ID

---

## 🆘 Troubleshooting

### Can't Login?
Check if user exists:
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User
User.objects.filter(email='your@email.com').exists()
```

### User Exists but Can't Access Admin?
Make them staff:
```python
from django.contrib.auth.models import User
user = User.objects.get(email='your@email.com')
user.is_staff = True
user.save()
```

### Forgot Password?
Reset it:
```python
from django.contrib.auth.models import User
user = User.objects.get(email='your@email.com')
user.set_password('newpassword123')
user.save()
```

---

## 📱 Mobile Access

The admin dashboard is responsive and works on mobile devices:
- Sidebar collapses on mobile
- Tables scroll horizontally
- Forms adapt to screen size

---

## ✅ Quick Test Checklist

After setup, verify these work:

- [ ] Can login at `/accounts/login/`
- [ ] Redirects to admin dashboard automatically
- [ ] Can see room statistics
- [ ] Can view all reservations
- [ ] Can access payment verification
- [ ] Can perform check-in/check-out
- [ ] Can view guest directory
- [ ] Can manage staff (if admin)

---

## 🎉 You're Ready!

**Just remember:**
1. Login URL: http://localhost:8000/accounts/login/
2. Admin Dashboard: http://localhost:8000/dashboard/admin-panel/
3. Everything is in the custom dashboard - no need for Django admin!

**Happy hotel managing! 🏨**
