# FILE: accounts/urls.py  -> GANTI ISI
from django.urls import path

from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('me/', views.me, name='me'),

    # user management (admin)
    path('users/', views.users, name='users'),                      # GET list, POST tambah
    path('users/<int:pk>/', views.user_detail, name='user_detail'),  # GET, PUT, DELETE
]