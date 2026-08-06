from django.db import models
from users.models import TelegramUser


class Material(models.Model):
    """10-bosqich: 'Materiallar' sahifasi (12-13-rasm). Oddiy jadval: nomi + havola, admin CRUD."""

    title = models.CharField(max_length=255)
    file_link = models.URLField(help_text="Bosilganda mijoz shu havolaga uloqtiriladi")
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]
        verbose_name = "Material"
        verbose_name_plural = "Materiallar"

    def __str__(self):
        return self.title


class ContentCategory(models.Model):
    """
    12-bosqich: 'Jonli efirlar', 'Akademiya FM' kabi kategoriyalar (10, 15-rasm).
    Admin position orqali tartibini o'zgartira oladi.

    Ixtiyoriy ichma-ich tuzilma: bitta kategoriya (masalan 'Kurs') `parent=None` bilan
    yaratiladi va uning ichiga boshqa kategoriyalar ('Aqlni rivojlantirish kurslari' va h.k.)
    `parent=shu kategoriya` qilib qo'shilishi mumkin. Qatlamlar soni CHEKLANMAGAN — admin
    xohlagancha chuqurlikda ichki kategoriya hosil qila oladi (bu admin_api darajasida
    faqat aylanma bog'lanish (kategoriyani o'zining avlodiga ko'chirish)dan himoyalanadi).
    Bitta kategoriya bir vaqtning o'zida HAM ichki kategoriyalarga, HAM to'g'ridan-to'g'ri
    kontentlarga ega bo'la olmaydi — u yoki konteyner (ichki kategoriyalar saqlaydi),
    yoki barg (bevosita Content obyektlarini saqlaydi).
    """

    name = models.CharField(max_length=150)
    cover_image = models.ImageField(upload_to="content_categories/")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children",
        help_text="Agar to'ldirilsa — bu kategoriya boshqa kategoriyaning ICHKI kategoriyasi hisoblanadi",
    )
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]
        verbose_name = "Kontent kategoriyasi"
        verbose_name_plural = "Kontent kategoriyalari"

    def __str__(self):
        return f"{self.parent.name} → {self.name}" if self.parent_id else self.name

    def get_root(self):
        """Nechchi qatlam chuqur bo'lishidan qat'i nazar eng tepadagi (parent=None)
        ajdod kategoriyani qaytaradi. Sirtqi tugunlarga (parent=None) chaqirilsa — o'zini qaytaradi."""
        node = self
        seen_ids = {node.id}
        while node.parent_id is not None:
            node = node.parent
            if node.id in seen_ids:
                break  # noto'g'ri (aylanma) ma'lumotdan himoya, cheksiz sikldan qochish uchun
            seen_ids.add(node.id)
        return node

    def get_ancestor_ids(self):
        """O'zining barcha ajdodlari (parent, parent.parent, ...) id'lari ro'yxati."""
        ids = []
        node = self.parent
        while node is not None and node.id not in ids:
            ids.append(node.id)
            node = node.parent
        return ids


class Content(models.Model):
    """
    12-bosqich: kategoriya ichidagi bitta video/audio (16-17-rasm).
    Mijoz kategoriya rasmini bosganda shu kategoriyaga tegishli kontentlar ro'yhati chiqadi,
    kontentni tanlasa detail (17-rasm) ochiladi.
    """

    class MediaType(models.TextChoices):
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        FILE = "file", "Fayl"

    category = models.ForeignKey(ContentCategory, on_delete=models.CASCADE, related_name="contents")
    title = models.CharField(max_length=255)
    cover_image = models.ImageField(upload_to="content_covers/", blank=True, null=True)
    description = models.TextField(blank=True)
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.VIDEO)
    media_file = models.FileField(upload_to="content_media/", blank=True, null=True)
    media_url = models.URLField(blank=True, null=True, help_text="Agar tashqi (masalan YouTube/CDN) havola bo'lsa")
    published_date = models.DateField()
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "-published_date"]
        verbose_name = "Kontent"
        verbose_name_plural = "Kontentlar"

    def __str__(self):
        return f"{self.category} — {self.title}"


class ContentLike(models.Model):
    """18-rasm: 'Saralangan' — mijoz like bosgan kontentlar shu orqali filterlanadi."""

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="content_likes")
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "content")
        verbose_name = "Kontent like"
        verbose_name_plural = "Kontent likelar"


class CommunityCategory(models.Model):
    """
    13-bosqich: 'Jamiyat' sahifasi (19-rasm) — qoidalar kategoriyalari.
    Agar `external_link` to'ldirilgan bo'lsa, mijoz shu kategoriyani tanlaganda
    ichiga kirmasdan havolaga uloqtiriladi; bo'sh bo'lsa — ichidagi elementlar ro'yhati ko'rsatiladi.
    """

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    external_link = models.URLField(blank=True, null=True)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]
        verbose_name = "Jamiyat kategoriyasi"
        verbose_name_plural = "Jamiyat kategoriyalari"

    def __str__(self):
        return self.name


class CommunityContent(models.Model):
    """Jamiyat kategoriyasi ichidagi bitta qoida/element."""

    category = models.ForeignKey(CommunityCategory, on_delete=models.CASCADE, related_name="items")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="community/", blank=True, null=True)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]
        verbose_name = "Jamiyat elementi"
        verbose_name_plural = "Jamiyat elementlari"

    def __str__(self):
        return f"{self.category} — {self.title}"