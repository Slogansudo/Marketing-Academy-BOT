from django.contrib import admin
from .models import Broadcast, BroadcastRecipient


class BroadcastRecipientInline(admin.TabularInline):
    model = BroadcastRecipient
    extra = 0
    readonly_fields = ("user", "is_sent", "error", "sent_at")
    can_delete = False
    max_num = 0


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ("title", "target_type", "status", "total_recipients", "sent_count", "failed_count", "created_at")
    list_filter = ("target_type", "status")
    readonly_fields = ("status", "total_recipients", "sent_count", "failed_count", "sent_at")
    inlines = [BroadcastRecipientInline]
    actions = ["queue_broadcast"]

    @admin.action(description="Tanlangan e'lonlarni yuborish uchun navbatga qo'yish")
    def queue_broadcast(self, request, queryset):
        from broadcast.tasks import send_broadcast_task
        for broadcast in queryset.filter(status=Broadcast.Status.DRAFT):
            broadcast.status = Broadcast.Status.QUEUED
            broadcast.save(update_fields=["status"])
            send_broadcast_task.delay(broadcast.id)
