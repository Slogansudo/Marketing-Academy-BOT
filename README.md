# Davronbek Turdiev Akademiyasi — Backend

Stack: **Django + DRF (admin panel/API) + aiogram3 (Telegram bot) + Celery/Celery-Beat (background/cron) + PostgreSQL + Redis**

## Arxitektura g'oyasi

- **Django** — yagona "manba haqiqati": barcha modellar, admin panel (to'liq CRUD), REST API (mini app uchun).
- **aiogram** — Telegram botning o'zi. Webhook orqali ishlaydi (`apps/bot/views.py`), Django ORM'ga to'g'ridan-to'g'ri ulanadi (Django 5 async ORM: `aget`, `acreate`, `afirst`...).
- **Celery + Celery-Beat** — "background task cron job": avto to'lovlarni yechish, muddati o'tganlarni faolsizlantirish, eslatmalar, e'lon (broadcast) yuborish.
- **Mini app (React, alohida repo)** — faqat Telegram WebApp `initData` orqali autentifikatsiya qilib, `apps/api` dagi REST endpointlardan foydalanadi.

## Loyihaning 16 bosqichi qayerda amalga oshirilgan

| # | Talab (qisqacha) | Rasm | Kod |
|---|---|---|---|
| 1 | `/start`, ism va telefon so'rash | 3-rasm | `apps/bot/handlers/registration.py`, `apps/users/models.py` |
| 2 | Telefon qabul qilingach video+matn, "Akademiyaga qo'shilish" | 3-rasm | `registration.py:_finish_phone_step`, `apps/cms/bot_texts.py` (statik matn), `apps/cms/models.py:BotMedia` (media) |
| 3 | Tariflar (1/3 oy), narx dinamik | 4-rasm | `apps/bot/handlers/subscription.py:_render_tariff_text`, `apps/subscriptions/models.py:SubscriptionPlan` |
| 4 | To'lov usuli tanlash, narx dinamik, oferta havolasi | 5-rasm | `subscription.py:on_select_plan`, `apps/cms/models.py:BotLink` |
| 5 | Uzcard/Humo → Payme sahifa, kod tasdiqlash, botga qaytish; Chet eldan → Tribute | 1,2,6,7,8-rasm | `subscription.py:on_payment_method`, `apps/subscriptions/services/payme_client.py`, `tribute_client.py`, `apps/subscriptions/webhooks.py` |
| 6 | 1 oylik — har oy, 3 oylik — har 3 oyda avto to'lov | — | `apps/subscriptions/services/subscription_service.py` (`next_payment_date` hisoblash), `apps/subscriptions/tasks.py:charge_due_subscriptions` |
| 7 | To'lovdan keyin botga qaytib `/start` (avto), 4ta tugmali menyu | 9-rasm | `registration.py:cmd_start` (`start=paid` deep-link), `apps/bot/keyboards.py:main_menu_keyboard` |
| 8 | Yopiq kanalga qo'shilish (admin o'zgartira oladi) | 9-rasm | `apps/cms/models.py:BotLink(key=PRIVATE_CHANNEL)` |
| 9 | Shaxsiy kabinet (mini app), 12+ oylik sovg'a zinapoyasi, streak reset logikasi | 10, 11-rasm | `apps/gifts/models.py`, `apps/api/views.py:SubscriptionStatusView, GiftTrackView, GiftClaimView`, `apps/subscriptions/tasks.py:expire_overdue_subscriptions` |
| 10 | Materiallar sahifasi (jadval: nomi+havola) | 12, 13-rasm | `apps/content/models.py:Material`, `apps/api/views.py:MaterialListView` |
| 11 | Umumiy chat (faqat havola) | 14-rasm | `apps/cms/models.py:BotLink(key=COMMUNITY_CHAT)` |
| 12 | Kontent kategoriyalari + kontentlar + like/saralangan | 15,16,17,18-rasm | `apps/content/models.py:ContentCategory, Content, ContentLike`, `apps/api/views.py` (Content*) |
| 13 | Jamiyat: kategoriya (havola bo'lsa tashqariga, bo'lmasa ichkariga) | 19-rasm | `apps/content/models.py:CommunityCategory, CommunityContent`, `apps/api/views.py:CommunityContentListView` |
| 14 | Yordam tugmasi (havola, admin boshqaradi) | 9-rasm | `apps/cms/models.py:BotLink(key=HELP)` |
| 15 | Obuna holati, avto to'lovni bekor qilish, kartani almashtirish | 9-rasm (tugma) | `apps/bot/handlers/subscription_status.py`, `apps/subscriptions/services/subscription_service.py:cancel_auto_renew, replace_primary_card` |
| 16 | Admin panel to'liq CRUD + global/segment broadcast | — | `apps/*/admin.py`, `apps/broadcast/models.py`, `apps/broadcast/tasks.py` |
| 17 | 3/2/1 kunlik eslatmalar + SMS, to'lov kunidagi bosqichma-bosqich qayta urinish kaskadi (24/24/18/6 soat), karta muddati o'tgani, yakuniy bekor qilish | (yangi, screenshot yo'q) | `apps/subscriptions/models.py:RenewalSettings, SubscriptionRenewalCycle, RenewalAttempt, PaymentReminderLog`, `apps/subscriptions/services/renewal_engine.py`, `apps/subscriptions/tasks.py`, `apps/bot/services/renewal_notifier.py`, `apps/bot/handlers/renewal.py` |
| 18 | **Bir marta pul yechish kafolati** (double-charge himoyasi) | — | `renewal_engine.py` — DB `select_for_update()` "claim" fazasi + `expected_attempt_number` orqali eskirgan (stale) chaqiruvlarni avtomatik tashlab ketish. Pastda alohida bo'lim qarang. |

## 17-18-bosqich: avto to'lov kaskadi va "bir marta yechish" kafolati

`apps/subscriptions/services/renewal_engine.py` — loyihaning eng nozik qismi. Har bir billing
davri uchun bitta `SubscriptionRenewalCycle` yozuvi bor, va u orqali quyidagi kaskad boshqariladi:

```
To'lov kuni -> 1-urinish
  ✅ muvaffaqiyatli -> tugadi
  ❌ mablag' yetarli emas -> xabar (Davom etish) -> 24 soat kutish (yoki mijoz bossa darhol)
       -> 2-urinish -> muvaffaqiyatsiz bo'lsa -> xabar (48 soat) -> 24 soat kutish
       -> 3-urinish -> muvaffaqiyatsiz bo'lsa -> xabar (24 soat) -> 18 soat kutish
       -> 4-urinish -> muvaffaqiyatsiz bo'lsa -> xabar (6 soat)  -> 6 soat kutish
       -> 5-urinish -> muvaffaqiyatsiz bo'lsa -> OBUNA TO'XTATILADI (kanal/chatdan chiqarish,
                                                   daraja "boshlovchi"ga tushadi)
  💳 karta muddati o'tgan -> 'Kartani almashtirish' -> Payme karta yangilash -> qaytadan urinish
       (bossa darhol, bosmasa 24 soatdan keyin avtomatik)
```

Har bir bosqichdagi kutish vaqti (24/24/18/6 soat) va eslatma kunlari (3/2/1)
**admin panelda** (`RenewalSettings`, Django admin — singleton) o'zgartiriladi, kodga tegmasdan.

**"Bir marta pul yechilsin" qoidasi (18-bosqich) qanday kafolatlanadi:**

1. Har bir urinish DB darajasidagi qulf (`select_for_update`) bilan "claim" qilinadi — parallel
   ishga tushgan ikkita chaqiruv (masalan rejalashtirilgan avto-retry va mijozning "Davom etish"
   tugmasini bosishi bir vaqtga to'g'ri kelib qolsa) orasidan faqat BITTASI haqiqiy to'lovga o'tadi.
2. Rejalashtirilgan har bir kelajakdagi urinish `expected_attempt_number` bilan chaqiriladi;
   agar shu payt kelib cycle allaqachon boshqa yo'l bilan ilgarilab ketgan bo'lsa (masalan mijoz
   oldinroq tugmani bosgan bo'lsa), bu eskirgan chaqiruv hech narsa qilmay chiqib ketadi.
3. `cycle.status` SUCCEEDED yoki CANCELLED bo'lsa — keyingi HAR QANDAY chaqiruv (eski task,
   qayta bosilgan tugma, ikkilangan webhook) darhol to'xtaydi.
4. Payme tomonga yuboriladigan `order_id` har bir urinish uchun noyob (`renewal-{cycle_id}-{attempt}`)
   — bu Payme darajasida ham qo'shimcha dublikat himoyasi beradi.

Bu mantiq `python manage.py test` orqali emas, balki loyiha yozilishi jarayonida real Django
ORM + SQLite ustida qo'lda simulyatsiya qilinib tekshirildi: (a) muvaffaqiyatli 1-urinishdan keyin
eskirgan/qayta chaqiruvlar hech qanday qo'shimcha `Payment` yaratmasligi, (b) muvaffaqiyatsiz
1-urinishdan keyin to'g'ri kutish vaqti bilan qayta navbatga qo'yilishi va mijoz "Davom etish"
bosgach aynan bitta muvaffaqiyatli `Payment` bilan yakunlanishi — ikkalasi ham tasdiqlandi.

## Ishga tushirish (dev)

```bash
cp .env.example .env   # va qiymatlarni to'ldiring (bot token, Payme/Tribute kalitlari)
docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_bot_links
docker compose exec web python manage.py set_webhook https://your-domain.uz
```

## Muhim eslatmalar / keyingi qadamlar (prod uchun)

- `apps/subscriptions/services/payme_client.py` va `webhooks.py` dagi `TODO(prod)` belgilangan joylarda **haqiqiy Payme Merchant API** (Cards + Receipts, JSON-RPC, Basic auth) chaqiruvlari yozilishi kerak — bu yerda struktura va oqim to'liq tayyor, faqat HTTP so'rovning o'zi merchant kalitlari qo'lga kelgach ulanadi.
- Tribute tomoni asosan webhook-driven — `TRIBUTE_WEBHOOK_SECRET` bilan imzo tekshiriladi (`webhooks.py:TributeWebhookView`).
- Kanal-dan chiqarib yuborish (`expire_overdue_subscriptions`) da Telegram `banChatMember`/`unbanChatMember` chaqiruvi qo'shilishi kerak.
- `apps/broadcast/tasks.py` (kodni qisqartirish uchun bu yerda ko'rsatilmadi, lekin `admin.py` ichida `send_broadcast_task.delay(...)` chaqirilgan) — segmentlash (`Broadcast.target_type`) bo'yicha `TelegramUser` ro'yxatini yig'ib, har biriga Celery orqali xabar yuboradi, rate-limitga tushmaslik uchun orasida kichik delay bilan.








python -m venv venv    
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

python manage.py seed_bot_links

python manage.py runserver 8000

##################################################
docker-compose up -d --force-recreate redis

python manage.py runbot_polling  

python -m celery -A config worker -l info --pool=solo