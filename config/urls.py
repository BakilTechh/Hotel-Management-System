"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
"""
URL configuration for config project.
"""
from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dashboard.views import DashboardView, FacilitiesView, OffersView, AboutView
from rooms.views import room_detail, room_list, review_list


def health_check(request):
    """Endpoint ringan untuk monitor/uptime checker. Selalu 200 OK."""
    return JsonResponse({'status': 'ok'})


def admin_redirect(request):
    """Redirect old admin URL to new custom admin dashboard."""
    return redirect('admin_dashboard', permanent=True)


urlpatterns = [
    path('', DashboardView.as_view(), name='home'),
    path('facilities/', FacilitiesView.as_view(), name='facilities'),
    path('offers/', OffersView.as_view(), name='offers'),
    path('about/', AboutView.as_view(), name='about'),
    path('health/', health_check, name='health'),
    # Redirect /admin/ to custom admin dashboard
    path('admin/', admin_redirect, name='admin_redirect'),
    # Keep Django admin available at a different URL for emergencies (optional)
    # path('django-admin/', admin.site.urls),  # Uncomment if you need Django admin
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('rooms/', room_list, name='room_list'),
    path('rooms/ulasan/', review_list, name='review_list'),
    path('rooms/<int:pk>/', room_detail, name='room_detail'),
    path('reservations/', include('reservations.urls')),
    path('room-service/', include('chatbot.urls')),
]

#Supaya foto bukti transfer pembayaran bisa dibuka saat testing lokal
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)