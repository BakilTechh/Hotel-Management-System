from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import GuestProfile


class GuestProfileInline(admin.StackedInline):
    model = GuestProfile
    extra = 0


class ManagedUserAdmin(UserAdmin):
    inlines = [GuestProfileInline]
    list_display = ('username', 'email', 'role', 'status', 'is_active', 'date_joined')
    list_filter = ('guest_profile__role', 'guest_profile__status', 'is_active')
    list_select_related = ('guest_profile',)

    @admin.display(description='Role')
    def role(self, obj):
        if obj.is_superuser:
            return 'ADMIN'
        p = getattr(obj, 'guest_profile', None)
        return p.role if p else '-'

    @admin.display(description='Status')
    def status(self, obj):
        p = getattr(obj, 'guest_profile', None)
        return p.status if p else '-'


admin.site.unregister(User)
admin.site.register(User, ManagedUserAdmin)
