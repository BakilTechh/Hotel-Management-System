# How to Login as Admin and Staff

## Quick Answer

1. **Login URL:** http://localhost:8000/accounts/login/
2. **After login:** Staff/Admin automatically go to http://localhost:8000/dashboard/admin-panel/

---

## Method 1: Create Superuser (Easiest for Admin)

### Step 1: Open Terminal
```bash
cd /home/zak/Work/Hotel-Management-System
source .venv/bin/activate
```

### Step 2: Create Superuser
```bash
python manage.py createsuperuser
```

### Step 3: Follow the Prompts
```
Username: admin
Email address: admin@nocturnhaven.test
Password: (type your password)
Password (again): (type your password again)
```

### Step 4: Login
1. Start server: `python manage.py runserver`
2. Go to: http://localhost:8000/accounts/login/
3. Login with:
   - Email: `admin@nocturnhaven.test`
   - Password: (the password you set)
4. You'll automatically be redirected to admin dashboard!

---

## Method 2: Create Staff User via Django Shell

### Step 1: Open Django Shell
```bash
python manage.py shell
```

### Step 2: Create Staff User
```python
from django.contrib.auth.models import User
from accounts.models import GuestProfile

# Create the user
user = User.objects.create_user(
    username='staff1',
    email='staff@nocturnhaven.test',
    password='password123',
    first_name='John',
    last_name='Doe'
)

# Mark as staff
user.is_staff = True
user.is_active = True
user.save()

# Create profile with STAFF role
profile = GuestProfile.objects.create(
    user=user,
    role='STAFF',
    status='ACTIVE',
    phone_number='081234567890'
)

print(f"✅ Staff user created: {user.email}")
```

### Step 3: Exit Shell
```python
exit()
```

### Step 4: Login
1. Go to: http://localhost:8000/accounts/login/
2. Login with:
   - Email: `staff@nocturnhaven.test`
   - Password: `password123`

---

## Method 3: Promote Existing Guest to Staff

If you already have a guest account and want to make it staff:

### Step 1: Open Django Shell
```bash
python manage.py shell
```

### Step 2: Promote User
```python
from django.contrib.auth.models import User
from accounts.models import GuestProfile

# Find the user by email
user = User.objects.get(email='guest@example.com')

# Make them staff
user.is_staff = True
user.save()

# Update their profile role
profile = user.guest_profile
profile.role = 'ADMIN'  # or 'STAFF'
profile.save()

print(f"✅ User promoted to {profile.role}")
```

### Step 3: Exit and Login
```python
exit()
```

Now that user can login and access the admin dashboard!

---

## Quick Script: Create Multiple Staff Users

Save this as `create_staff.py` in your project root:

```python
# create_staff.py
from django.contrib.auth.models import User
from accounts.models import GuestProfile

staff_users = [
    {
        'username': 'receptionist1',
        'email': 'receptionist@nocturnhaven.test',
        'password': 'password123',
        'first_name': 'Jane',
        'last_name': 'Smith',
        'role': 'STAFF',
        'phone': '081234567891'
    },
    {
        'username': 'manager',
        'email': 'manager@nocturnhaven.test',
        'password': 'password123',
        'first_name': 'Mike',
        'last_name': 'Johnson',
        'role': 'ADMIN',
        'phone': '081234567892'
    },
]

for staff_data in staff_users:
    # Check if user already exists
    if User.objects.filter(email=staff_data['email']).exists():
        print(f"⚠️  User {staff_data['email']} already exists, skipping...")
        continue
    
    # Create user
    user = User.objects.create_user(
        username=staff_data['username'],
        email=staff_data['email'],
        password=staff_data['password'],
        first_name=staff_data['first_name'],
        last_name=staff_data['last_name']
    )
    user.is_staff = True
    user.is_active = True
    user.save()
    
    # Create profile
    profile = GuestProfile.objects.create(
        user=user,
        role=staff_data['role'],
        status='ACTIVE',
        phone_number=staff_data['phone']
    )
    
    print(f"✅ Created {staff_data['role']}: {user.email} (password: {staff_data['password']})")

print("\n🎉 All staff users created!")
```

### Run the Script:
```bash
python manage.py shell < create_staff.py
```

---

## Understanding Roles

### GUEST
- Regular hotel customers
- Can only see their own bookings
- Access: `/dashboard/` (Guest Portal)
- **Login redirects to:** `/dashboard/`

### STAFF
- Hotel employees (receptionists, housekeeping, etc.)
- Can manage reservations, payments, check-in/out
- Can view all bookings and guests
- Access: `/dashboard/admin-panel/` (Admin Dashboard)
- **Login redirects to:** `/dashboard/admin-panel/`

### ADMIN
- System administrators
- All STAFF privileges PLUS:
  - Manage staff accounts
  - Assign/change roles
  - Full system access
- Access: `/dashboard/admin-panel/` (Admin Dashboard)
- **Login redirects to:** `/dashboard/admin-panel/`

---

## Testing Your Login

### Test Admin Login:
```bash
# 1. Create superuser
python manage.py createsuperuser

# 2. Start server
python manage.py runserver

# 3. Open browser
# Go to: http://localhost:8000/accounts/login/

# 4. Login with superuser credentials

# 5. You should see the admin dashboard with:
# - Room statistics
# - Today's arrivals/departures
# - Payment verification queue
# - Service orders
# - Sidebar navigation
```

### Test Staff Login:
```bash
# Use the staff account created above
# Email: staff@nocturnhaven.test
# Password: password123

# Should redirect to admin dashboard
# Can access all operational features
# Cannot manage other staff (only admins can)
```

### Test Guest Login:
```bash
# Register a new guest account at:
# http://localhost:8000/accounts/register/

# Login with guest credentials
# Should redirect to guest dashboard
# Can only see own bookings
```

---

## Troubleshooting

### Problem: "User does not exist"
**Solution:** Make sure you created the user first using one of the methods above.

### Problem: Login successful but no admin access
**Check:**
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User
user = User.objects.get(email='your@email.com')
print(f"is_staff: {user.is_staff}")
print(f"is_active: {user.is_active}")
if hasattr(user, 'guest_profile'):
    print(f"role: {user.guest_profile.role}")
else:
    print("No profile found!")
```

**Fix:**
```python
# Make user staff
user.is_staff = True
user.save()

# Create/update profile
from accounts.models import GuestProfile
profile, created = GuestProfile.objects.get_or_create(user=user)
profile.role = 'ADMIN'
profile.save()
```

### Problem: Get redirected to wrong page
**Fix:** Clear your browser cache and cookies, then login again.

### Problem: Forgot password
**Reset via Django shell:**
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User
user = User.objects.get(email='your@email.com')
user.set_password('newpassword123')
user.save()
print("✅ Password reset!")
```

---

## Default Test Accounts (After Running Script)

After running the `create_staff.py` script above, you'll have:

| Role | Email | Password | Access |
|------|-------|----------|--------|
| Admin | manager@nocturnhaven.test | password123 | Full admin dashboard |
| Staff | receptionist@nocturnhaven.test | password123 | Admin dashboard (no staff management) |
| Staff | staff@nocturnhaven.test | password123 | Admin dashboard (no staff management) |

**⚠️ IMPORTANT:** Change these passwords in production!

---

## Summary

### To Create Admin:
```bash
python manage.py createsuperuser
```

### To Create Staff:
```python
# In Django shell
from django.contrib.auth.models import User
from accounts.models import GuestProfile

user = User.objects.create_user(
    username='staff1',
    email='staff@hotel.com',
    password='password123'
)
user.is_staff = True
user.save()

GuestProfile.objects.create(user=user, role='STAFF')
```

### To Login:
1. Go to: **http://localhost:8000/accounts/login/**
2. Enter email and password
3. **Staff/Admin → Auto-redirect to admin dashboard**
4. **Guests → Auto-redirect to guest portal**

✅ **Done!**
