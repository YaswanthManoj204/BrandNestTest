from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.cards.models import UserPlan, EnterpriseCompany
from apps.cards.notifications import send_plan_expiration_email


class Command(BaseCommand):
    help = 'Scans Personal and Enterprise yearly plans and sends expiration reminder emails to user/CEO Gmail.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Send notification if expiring within this number of days (default: 30)')
        parser.add_argument('--force', action='store_true', help='Force send even if already sent recently')

    def handle(self, *args, **options):
        threshold_days = options['days']
        force = options['force']
        now = timezone.now()
        horizon = now + timedelta(days=threshold_days)

        sent_count = 0

        self.stdout.write(self.style.NOTICE(f"Scanning plans expiring on or before {horizon.strftime('%Y-%m-%d')}..."))

        # 1. Personal Plans
        personal_plans = UserPlan.objects.filter(
            plan_type='personal',
            user__isnull=False
        )
        for plan in personal_plans:
            exp = plan.effective_expires_at
            if not exp or exp > horizon:
                continue

            # Don't re-notify if notified within the last 7 days unless forced
            if not force and plan.last_notification_sent_at and (now - plan.last_notification_sent_at).days < 7:
                continue

            recipient_email = plan.user.email
            if not recipient_email:
                continue

            user_name = plan.user.get_full_name() or plan.user.username
            days_left = plan.days_remaining
            res = send_plan_expiration_email(
                recipient_email=recipient_email,
                recipient_name=user_name,
                plan_name=plan.plan_name or 'Personal Pro Digital (Yearly)',
                expires_at=exp,
                days_left=days_left,
                is_enterprise=False,
            )
            if res.get('success'):
                plan.last_notification_sent_at = now
                plan.save(update_fields=['last_notification_sent_at'])
                sent_count += 1
                self.stdout.write(self.style.SUCCESS(f"[Personal] Sent notification to {recipient_email} (expires in {days_left}d)"))

        # 2. Enterprise Plans (CEOs and EnterpriseCompany)
        ent_ceos = UserPlan.objects.filter(
            plan_type='enterprise',
            is_ceo=True,
            user__isnull=False
        )
        for plan in ent_ceos:
            exp = plan.effective_expires_at
            if not exp or exp > horizon:
                continue

            if not force and plan.last_notification_sent_at and (now - plan.last_notification_sent_at).days < 7:
                continue

            recipient_email = plan.company_email or plan.user.email
            if not recipient_email:
                continue

            ceo_name = plan.company_head_name or plan.user.get_full_name() or plan.user.username
            days_left = plan.days_remaining
            res = send_plan_expiration_email(
                recipient_email=recipient_email,
                recipient_name=ceo_name,
                plan_name=plan.plan_name or 'Enterprise Corporate Bundle (Yearly)',
                expires_at=exp,
                days_left=days_left,
                is_enterprise=True,
            )
            if res.get('success'):
                plan.last_notification_sent_at = now
                plan.save(update_fields=['last_notification_sent_at'])
                sent_count += 1
                self.stdout.write(self.style.SUCCESS(f"[Enterprise CEO] Sent notification to {recipient_email} (expires in {days_left}d)"))

        self.stdout.write(self.style.SUCCESS(f"Completed! Total expiration reminder emails sent: {sent_count}"))

