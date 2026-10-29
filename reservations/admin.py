from django.contrib import admin, messages
from django.utils import timezone

from .models import Booking, BookingModification, Payment, PaymentEvent, PromoVoucher, Review
from .services import (
    InvalidTransition,
    complete_refund,
    request_refund,
    verify_payment,
)


@admin.register(PromoVoucher)
class PromoVoucherAdmin(admin.ModelAdmin):
    list_display = (
        'kode_voucher', 'persen_diskon', 'potongan_nominal',
        'minimal_transaksi', 'kuota_penggunaan', 'tanggal_kedaluwarsa',
    )
    search_fields = ('kode_voucher',)
    list_filter = ('tanggal_kedaluwarsa',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_code', 'user', 'room', 'tanggal_check_in',
        'tanggal_check_out', 'payment_status', 'total_biaya_akhir',
        'status_pesanan',
    )
    list_filter = ('status_pesanan', 'payment__status_pembayaran')
    search_fields = (
        'user__username', 'user__email', 'room__number', 'pk',
    )
    ordering = ('-created_at',)
    list_select_related = ('user', 'room', 'room__room_type', 'payment')
    readonly_fields = ('booking_code', 'diskon_voucher', 'voucher_digunakan')
    actions = ('check_in_bookings', 'check_out_bookings')

    @admin.display(description='Kode')
    def booking_code(self, obj):
        return obj.booking_code

    @admin.display(description='Pembayaran')
    def payment_status(self, obj):
        payment = obj.payment_record
        return payment.get_status_pembayaran_display() if payment else 'Belum ada'

    @admin.action(description='Check-in booking terkonfirmasi')
    def check_in_bookings(self, request, queryset):
        checked_in = 0
        for booking in queryset:
            if booking.check_in():
                checked_in += 1
        self.message_user(request, f'{checked_in} booking berhasil check-in.')

    @admin.action(description='Check-out booking yang sedang menginap')
    def check_out_bookings(self, request, queryset):
        checked_out = 0
        for booking in queryset:
            if booking.check_out():
                checked_out += 1
        self.message_user(request, f'{checked_out} booking berhasil check-out.')

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            old_status = (
                Booking.objects.filter(pk=obj.pk)
                .values_list('status_pesanan', flat=True)
                .first()
            )
        if obj.status_pesanan == 'CONFIRMED':
            payment = obj.payment_record
            if payment is None or payment.status_pembayaran != Payment.VERIFIED:
                obj.status_pesanan = old_status or 'PENDING_PAYMENT'
                self.message_user(
                    request,
                    'Booking belum dapat Confirmed sebelum Payment terverifikasi.',
                    level=messages.ERROR,
                )
        super().save_model(request, obj, form, change)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Staff verification desk for manual transfer payments."""

    list_display = (
        'booking', 'amount', 'metode_pembayaran', 'status_pembayaran',
        'verified_by', 'verified_at', 'refund_requested_at',
    )
    list_filter = ('status_pembayaran',)
    search_fields = ('booking__id', 'booking__user__username', 'booking__user__email')
    list_select_related = ('booking', 'booking__user', 'verified_by')
    readonly_fields = (
        'verified_by', 'verified_at', 'refund_requested_at', 'refunded_at',
        'provider_reference', 'failure_reason', 'created_at', 'updated_at',
    )
    actions = (
        'setujui_pembayaran', 'tolak_pembayaran',
        'tandai_refund_diproses', 'selesaikan_refund',
    )

    def _verifikasi(self, request, queryset, disetujui):
        berhasil = 0
        gagal = 0
        for payment in queryset.select_related('booking'):
            try:
                verify_payment(
                    payment,
                    approved=disetujui,
                    actor=request.user,
                    reason='Diputuskan melalui admin panel.',
                )
            except InvalidTransition as exc:
                gagal += 1
                self.message_user(request, f'{payment}: {exc}', level=messages.ERROR)
            else:
                berhasil += 1
        hasil = 'disetujui' if disetujui else 'ditolak'
        if berhasil:
            self.message_user(request, f'{berhasil} pembayaran {hasil}.')
        if gagal and not berhasil:
            self.message_user(
                request, f'{gagal} pembayaran tidak dapat diproses.', level=messages.WARNING,
            )

    @admin.action(description='Setujui pembayaran (booking → Confirmed)')
    def setujui_pembayaran(self, request, queryset):
        self._verifikasi(request, queryset, True)

    @admin.action(description='Tolak pembayaran')
    def tolak_pembayaran(self, request, queryset):
        self._verifikasi(request, queryset, False)

    @admin.action(description='Tandai refund sedang diproses')
    def tandai_refund_diproses(self, request, queryset):
        berhasil = 0
        for payment in queryset:
            try:
                request_refund(
                    payment, actor=request.user, reason='Refund dimulai dari admin panel.',
                )
            except InvalidTransition as exc:
                self.message_user(request, f'{payment}: {exc}', level=messages.ERROR)
            else:
                berhasil += 1
        if berhasil:
            self.message_user(request, f'{berhasil} refund mulai diproses.')

    @admin.action(description='Tandai refund selesai (dana kembali)')
    def selesaikan_refund(self, request, queryset):
        berhasil = 0
        for payment in queryset:
            try:
                complete_refund(
                    payment,
                    actor=request.user,
                    reason='Refund diselesaikan melalui admin panel.',
                )
            except InvalidTransition as exc:
                self.message_user(request, f'{payment}: {exc}', level=messages.ERROR)
            else:
                berhasil += 1
        if berhasil:
            self.message_user(request, f'{berhasil} refund diselesaikan.')


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = (
        'event_id', 'provider', 'event_type', 'payment',
        'processed_at', 'created_at',
    )
    list_filter = ('provider', 'event_type', 'processed_at')
    search_fields = ('event_id', 'payment__booking__user__email')
    readonly_fields = (
        'provider', 'event_id', 'event_type', 'payload', 'payment',
        'processed_at', 'processing_error', 'created_at', 'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('booking', 'guest', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('guest__email', 'booking__id')
    list_select_related = ('booking', 'guest')


@admin.register(BookingModification)
class BookingModificationAdmin(admin.ModelAdmin):
    """Admin interface for booking modifications and change requests."""
    
    list_display = (
        'booking', 'modification_type', 'status', 'change_fee', 
        'price_difference', 'requested_by', 'created_at',
    )
    list_filter = ('status', 'modification_type')
    search_fields = ('booking__id', 'booking__user__username', 'notes')
    list_select_related = ('booking', 'booking__user', 'requested_by', 'approved_by')
    readonly_fields = (
        'created_at', 'updated_at', 'approved_at', 'approved_by',
    )
    actions = ('approve_modifications', 'reject_modifications')
    
    fieldsets = (
        ('Informasi Dasar', {
            'fields': ('booking', 'modification_type', 'status', 'requested_by')
        }),
        ('Nilai Lama', {
            'fields': ('old_check_in', 'old_check_out', 'old_room', 'old_guest_count'),
            'classes': ('collapse',)
        }),
        ('Nilai Baru', {
            'fields': ('new_check_in', 'new_check_out', 'new_room', 'new_guest_count')
        }),
        ('Biaya', {
            'fields': ('change_fee', 'price_difference')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at', 'rejection_reason', 'notes')
        }),
        ('Timestamp', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.action(description='Setujui modifikasi terpilih')
    def approve_modifications(self, request, queryset):
        approved = 0
        for modification in queryset.filter(status='PENDING'):
            modification.status = 'APPROVED'
            modification.approved_by = request.user
            modification.approved_at = timezone.now()
            modification.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
            approved += 1
        
        if approved:
            self.message_user(
                request,
                f'{approved} modifikasi disetujui. Tamu dapat menerapkan perubahan setelah pembayaran tambahan (jika ada).'
            )
    
    @admin.action(description='Tolak modifikasi terpilih')
    def reject_modifications(self, request, queryset):
        rejected = 0
        for modification in queryset.filter(status='PENDING'):
            modification.status = 'REJECTED'
            modification.approved_by = request.user
            modification.approved_at = timezone.now()
            modification.rejection_reason = 'Ditolak melalui admin panel.'
            modification.save(update_fields=[
                'status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'
            ])
            rejected += 1
        
        if rejected:
            self.message_user(request, f'{rejected} modifikasi ditolak.')
