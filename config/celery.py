import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("davron_academy")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.broker_transport_options = {"visibility_timeout": 3600 * 24}

# 17-18-bosqich: eslatmalar, kaskadni kunlik ishga tushirish va vaqtinchalik yozuvlarni tozalash.
# E'tibor bering: haqiqiy qayta urinishlar (retry) beat jadvalida YO'Q — ular
# `renewal_engine.execute_renewal_attempt` ichida `apply_async(countdown=...)` orqali
# o'z-o'zini bir martalik qilib qayta rejalashtiradi (18-bosqich: bir marta ishga tushish kafolati).
app.conf.beat_schedule = {
    "send-renewal-reminders-every-hour": {
        "task": "subscriptions.tasks.send_renewal_reminders",
        "schedule": crontab(minute=0),
    },
    "create-due-renewal-cycles-daily": {
        "task": "subscriptions.tasks.create_due_renewal_cycles",
        "schedule": crontab(hour=0, minute=5),
    },
    "cleanup-expired-pending-checkouts": {
        "task": "subscriptions.tasks.cleanup_expired_pending_checkouts",
        "schedule": crontab(minute="*/30"),
    },
}
