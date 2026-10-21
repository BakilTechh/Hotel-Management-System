from django.contrib import admin

from .models import (
    RoomServiceMenuItem,
    ServiceOrder,
    ServiceOrderItem,
    ServiceOrderStatusLog,
)


@admin.register(RoomServiceMenuItem)
class RoomServiceMenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available', 'sort_order')
    list_filter = ('category', 'is_available')
    list_editable = ('price', 'is_available', 'sort_order')
    search_fields = ('name', 'description')
    ordering = ('category', 'sort_order', 'name')


class ServiceOrderItemInline(admin.TabularInline):
    model = ServiceOrderItem
    extra = 0
    readonly_fields = ('name', 'unit_price', 'quantity')
    can_delete = False


class ServiceOrderStatusLogInline(admin.TabularInline):
    model = ServiceOrderStatusLog
    extra = 0
    readonly_fields = ('status', 'note', 'changed_by', 'created_at')
    can_delete = False


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'service_type', 'booking', 'status',
        'item_count', 'total', 'created_at',
    )
    list_filter = ('service_type', 'status', 'created_at')
    search_fields = (
        'user__username', 'user__email', 'detail', 'special_instructions',
    )
    list_select_related = ('user', 'booking')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ServiceOrderItemInline, ServiceOrderStatusLogInline]
    actions = ('tandai_dikonfirmasi', 'tandai_diantar', 'tandai_dibatalkan')

    @admin.display(description='Item')
    def item_count(self, obj):
        return obj.item_count or '-'

    @admin.display(description='Total')
    def total(self, obj):
        return f'Rp {obj.total:,.0f}'.replace(',', '.') if obj.items.exists() else '-'

    def _set_status(self, request, queryset, status, note):
        updated = 0
        for order in queryset:
            order.status = status
            order.save(update_fields=['status', 'updated_at'])
            ServiceOrderStatusLog.objects.create(
                order=order, status=status, note=note, changed_by=request.user,
            )
            updated += 1
        self.message_user(request, f'{updated} pesanan diperbarui menjadi {status}.')

    @admin.action(description='Tandai pesanan dikonfirmasi')
    def tandai_dikonfirmasi(self, request, queryset):
        self._set_status(request, queryset, 'CONFIRMED', 'Dikonfirmasi oleh staf.')

    @admin.action(description='Tandai pesanan diantar / selesai')
    def tandai_diantar(self, request, queryset):
        self._set_status(request, queryset, 'DELIVERED', 'Pesanan diantar ke kamar.')

    @admin.action(description='Batalkan pesanan')
    def tandai_dibatalkan(self, request, queryset):
        self._set_status(request, queryset, 'CANCELLED', 'Pesanan dibatalkan oleh staf.')


@admin.register(ServiceOrderStatusLog)
class ServiceOrderStatusLogAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'changed_by', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('order', 'status', 'note', 'changed_by', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
