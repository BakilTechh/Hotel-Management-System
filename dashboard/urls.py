from django.urls import path

from .views import (
    AdminDashboardView,
    CheckInActionView,
    CheckInOutView,
    CheckOutActionView,
    GuestDashboardView,
    GuestDetailView,
    GuestDirectoryView,
    HousekeepingUpdateView,
    HousekeepingView,
    PaymentVerificationView,
    PaymentVerifyActionView,
    ReportView,
    RoomManagementView,
    ServiceOrderQueueStaffView,
    ServiceOrderUpdateStatusView,
    StaffDetailView,
    StaffManagementView,
    StaffReservationListView,
    StaffToggleActiveView,
    StaffUpdateRoleView,
)


urlpatterns = [
    # Guest portal
    path('', GuestDashboardView.as_view(), name='guest_dashboard'),
    
    # Admin dashboard
    path('admin-panel/', AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # Reservations management
    path('admin-panel/reservations/', StaffReservationListView.as_view(), name='staff_reservations'),
    
    # Payment verification
    path('admin-panel/payments/', PaymentVerificationView.as_view(), name='payment_verification'),
    path('admin-panel/payments/verify/', PaymentVerifyActionView.as_view(), name='payment_verify_action'),
    
    # Check-in/Check-out
    path('admin-panel/reception/', CheckInOutView.as_view(), name='reception'),
    path('admin-panel/reception/checkin/', CheckInActionView.as_view(), name='checkin_action'),
    path('admin-panel/reception/checkout/', CheckOutActionView.as_view(), name='checkout_action'),
    
    # Room management
    path('admin-panel/rooms/', RoomManagementView.as_view(), name='room_management'),
    
    # Service orders
    path('admin-panel/service-orders/', ServiceOrderQueueStaffView.as_view(), name='service_order_queue_staff'),
    path('admin-panel/service-orders/update/', ServiceOrderUpdateStatusView.as_view(), name='service_order_update_status'),
    
    # Guest directory
    path('admin-panel/guests/', GuestDirectoryView.as_view(), name='guest_directory'),
    path('admin-panel/guests/<int:pk>/', GuestDetailView.as_view(), name='guest_detail'),
    
    # Staff management
    path('admin-panel/staff/', StaffManagementView.as_view(), name='staff_management'),
    path('admin-panel/staff/<int:pk>/', StaffDetailView.as_view(), name='staff_detail'),
    path('admin-panel/staff/update-role/', StaffUpdateRoleView.as_view(), name='staff_update_role'),
    path('admin-panel/staff/toggle-active/', StaffToggleActiveView.as_view(), name='staff_toggle_active'),
    
    # Housekeeping
    path('housekeeping/', HousekeepingView.as_view(), name='housekeeping'),
    path('housekeeping/update/', HousekeepingUpdateView.as_view(), name='housekeeping_update'),
    
    # Reports
    path('laporan/', ReportView.as_view(), name='report'),
]
