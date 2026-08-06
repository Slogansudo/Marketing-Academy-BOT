# Admin panel API (`apps/admin_api`)

Bu — admin panel (masalan alohida React/Vue dashboard) uchun **to'liq CRUD** REST API.
Mini app API'sidan (`apps/api`, Telegram `initData` bilan ishlaydi) mutlaqo mustaqil —
alohida autentifikatsiya, alohida `/api/admin/v1/` prefiksi.

## Autentifikatsiya

Django admin bilan bir xil hisob ishlatiladi (`is_staff=True` bo'lgan foydalanuvchi —
`createsuperuser` bilan yaratilgan yoki Django admin panelda belgilangan xodim).

```
POST /api/admin/v1/auth/login/
Body: {"username": "...", "password": "..."}
-> {"token": "...", "user": {...}}
```

Keyingi barcha so'rovlarda:
```
Authorization: Token <token>
```

Boshqa endpointlar:
- `POST /api/admin/v1/auth/logout/` — tokenni bekor qiladi
- `GET  /api/admin/v1/auth/me/` — joriy admin ma'lumoti

## Umumiy imkoniyatlar (har bir CRUD endpointda)

- **Pagination**: `?page=2&page_size=50` (default 20, max 200). Javob:
  `{"count", "total_pages", "current_page", "page_size", "next", "previous", "results"}`
- **Qidiruv**: `?search=so'z` (har bir endpointning tegishli matn maydonlarida)
- **Filtr**: `?status=active&is_active=true` kabi — har bir endpoint uchun `filterset_fields`
- **Tartiblash**: `?ordering=-created_at`

## Bo'limlar va endpointlar

| Bo'lim | Endpoint | Izoh |
|---|---|---|
| Dashboard | `GET /dashboard/` | Umumiy statistika (foydalanuvchilar, obunalar, to'lovlar, sovg'alar, kontent, e'lonlar) |
| Xodimlar | `/staff-users/` | Admin panelga kiradigan Django userlar (yozish — faqat superuser) |
| Mijozlar | `/users/` | TelegramUser to'liq CRUD + `block/`, `unblock/`, `summary/` action'lari |
| Tariflar | `/subscription-plans/` | SubscriptionPlan CRUD |
| Kartalar | `/payment-cards/` | PaymentCard CRUD (token write-only) |
| Obunalar | `/subscriptions/` | Subscription CRUD + `cancel-auto-renew/`, `reactivate/` |
| To'lovlar | `/payments/` | Payment CRUD |
| Vaqtinchalik to'lov | `/pending-checkouts/` | PendingCheckout CRUD |
| Avto to'lov sozlamalari | `/renewal-settings/`, `/renewal-settings/current/` | Singleton (GET/PATCH) |
| Yangilash sikllari | `/renewal-cycles/` | GET/PATCH (audit) |
| Urinishlar | `/renewal-attempts/` | Faqat GET |
| Eslatmalar jurnali | `/reminder-logs/` | Faqat GET |
| Sovg'a oylari | `/gift-months/` | GiftMonth CRUD |
| Sovg'a progressi | `/gift-progress/` | UserGiftProgress CRUD |
| Sovg'a olinganlar | `/gift-claims/` | UserGiftClaim CRUD |
| Materiallar | `/materials/` | Material CRUD |
| Kontent kategoriyalari | `/content-categories/` | ContentCategory CRUD |
| Kontentlar | `/contents/` | Content CRUD |
| Like'lar | `/content-likes/` | Faqat GET/DELETE |
| Jamiyat kategoriyalari | `/community-categories/` | CommunityCategory CRUD |
| Jamiyat elementlari | `/community-contents/` | CommunityContent CRUD |
| Bot xabarlari | `/bot-messages/` | Faqat GET (matn statik, kod ichida — bazada emas) |
| Bot medialari | `/bot-media/{slug}/` | BotMedia CRUD, `slug` bo'yicha (istalgan bot xabariga biriktiriladi) |
| Bot havolalari | `/bot-links/` | BotLink CRUD |
| E'lonlar | `/broadcasts/` | Broadcast CRUD + `send/`, `recipients/` |
| E'lon qabul qiluvchilari | `/broadcast-recipients/` | Faqat GET |

Barcha `/xxx/` — standart DRF ViewSet: `GET` (list), `POST` (create), `GET /id/` (retrieve),
`PUT`/`PATCH /id/` (update), `DELETE /id/` (delete).

## Misollar

```bash
# Login
curl -X POST https://.../api/admin/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"..."}'

# Dashboard
curl https://.../api/admin/v1/dashboard/ -H "Authorization: Token <token>"

# Faol obunalarni tarif bo'yicha filtrlab, sahifalab olish
curl "https://.../api/admin/v1/subscriptions/?status=active&ordering=-next_payment_date&page_size=50" \
  -H "Authorization: Token <token>"

# Mijozni bloklash
curl -X POST https://.../api/admin/v1/users/123/block/ -H "Authorization: Token <token>"

# E'lonni yuborish
curl -X POST https://.../api/admin/v1/broadcasts/5/send/ -H "Authorization: Token <token>"
```

## Ishga tushirish

`config/settings.py` va `config/urls.py` allaqachon yangilangan. Yangi qadam faqat migratsiya:

```bash
docker compose exec web python manage.py migrate   # authtoken jadvalini yaratadi
docker compose exec web python manage.py createsuperuser   # admin panel uchun hisob
```

`requirements.txt` ga `django-filter` qo'shildi — `docker compose up --build` qayta build qiladi.

## Xavfsizlik eslatmalari

- Bu API `apps.api.authentication.TelegramInitDataAuthentication`dan butunlay mustaqil —
  Telegram mijozlari (`TelegramUser`) bu yerga kira olmaydi, faqat Django xodimlar (`is_staff`).
- `PaymentCard.payme_card_token` — write-only, hech qachon javobda qaytmaydi.
- Xodimlar ro'yxatini (`/staff-users/`) o'zgartirish faqat `is_superuser=True` uchun.
