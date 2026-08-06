from django.contrib import admin
from .models import BotMedia, BotLink, BotMessageTemplate


@admin.register(BotMessageTemplate)
class BotMessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "group", "is_locked", "updated_at", "updated_by")
    list_filter = ("group", "is_locked")
    search_fields = ("slug", "title", "text")
    readonly_fields = ("default_text", "placeholders", "updated_at", "updated_by")

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BotMedia)
class BotMediaAdmin(admin.ModelAdmin):
    list_display = ("slug", "media_type", "video_shape", "updated_at")
    list_filter = ("media_type",)
    search_fields = ("slug",)


@admin.register(BotLink)
class BotLinkAdmin(admin.ModelAdmin):
    list_display = ("key", "url", "updated_at")