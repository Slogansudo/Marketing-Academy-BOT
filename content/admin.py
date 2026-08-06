from django.contrib import admin
from .models import Material, ContentCategory, Content, ContentLike, CommunityCategory, CommunityContent


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "file_link", "position", "is_active")
    list_editable = ("position", "is_active")
    ordering = ("position",)


@admin.register(ContentCategory)
class ContentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "position", "is_active")
    list_filter = ("parent",)
    list_editable = ("position", "is_active")
    ordering = ("position",)


@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "media_type", "published_date", "position", "is_active")
    list_filter = ("category", "media_type", "is_active")
    list_editable = ("position", "is_active")
    search_fields = ("title", "description")


@admin.register(ContentLike)
class ContentLikeAdmin(admin.ModelAdmin):
    list_display = ("user", "content", "created_at")
    search_fields = ("user__full_name",)


@admin.register(CommunityCategory)
class CommunityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "external_link", "position", "is_active")
    list_editable = ("position", "is_active")
    ordering = ("position",)


@admin.register(CommunityContent)
class CommunityContentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "position", "is_active")
    list_editable = ("position", "is_active")