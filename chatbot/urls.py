from django.urls import path
from django.views.generic import RedirectView

from .views import RoomServicePortalView

urlpatterns = [
    # Legacy chat page retired: everything room-service lives in the portal.
    path(
        '',
        RedirectView.as_view(pattern_name='room_service_portal', permanent=True),
    ),
    path('portal/', RoomServicePortalView.as_view(), name='room_service_portal'),
]
