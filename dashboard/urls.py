from django.urls import path

from .views import (
    GuestDashboardView,
    HousekeepingUpdateView,
    HousekeepingView,
    ReportView,
)


urlpatterns = [
    path('', GuestDashboardView.as_view(), name='guest_dashboard'),
    path('laporan/', ReportView.as_view(), name='report'),
    path('housekeeping/', HousekeepingView.as_view(), name='housekeeping'),
    path('housekeeping/update/', HousekeepingUpdateView.as_view(), name='housekeeping_update'),
]
