from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from rooms.views import room_detail, RoomListView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('rooms/', include('rooms.urls')),
    path('', RedirectView.as_view(pattern_name='rooms:room_list', permanent=False)),
    path('kamar/', views.room_list, name='room_list'),
]


