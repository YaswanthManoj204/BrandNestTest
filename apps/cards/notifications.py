import logging
from datetime import datetime
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_plan_expiration_email(recipient_email, recipient_name, plan_name, expires_at, days_left=None, is_enterprise=False, renew_url=None):
    """
    Sends an automated yearly plan expiration warning email to a User's or CEO's Gmail address.
    """
    if not recipient_email:
        return {'success': False, 'error': 'No email address provided'}

    if not renew_url:
        renew_url = "https://brandnest.in/enterprise/checkout/" if is_enterprise else "https://brandnest.in/card/choose-plan/"

    formatted_exp = expires_at.strftime('%d %B %Y') if isinstance(expires_at, datetime) else str(expires_at)
    if days_left is None:
        if isinstance(expires_at, datetime):
            diff = (expires_at - timezone.now()).total_seconds() / 86400
            days_left = max(0, int(diff))
        else:
            days_left = 30

    role_title = "Enterprise CEO" if is_enterprise else "BrandNest Member"
    account_type = "Enterprise Corporate Bundle" if is_enterprise else "Personal Digital Business Card"

    if days_left <= 0:
        time_msg = "has expired"
        urgency = "Action Required: Your BrandNest Plan Has Expired"
    elif days_left == 1:
        time_msg = "expires tomorrow"
        urgency = f"Urgent: Your BrandNest Plan Expires Tomorrow ({formatted_exp})"
    else:
        time_msg = f"is scheduled to expire in {days_left} days on {formatted_exp}"
        urgency = f"Notice: Your BrandNest {plan_name} Expires Soon ({formatted_exp})"

    subject = urgency

    plain_message = f"""Hello {recipient_name or 'Valued Customer'},

This is an automated reminder regarding your BrandNest yearly plan subscription.

Your {plan_name} ({account_type}) {time_msg}.

PLAN DETAILS:
- Plan Tier: {plan_name} (Yearly Renewable)
- Account Type: {role_title}
- Expiration Date: {formatted_exp}
- Status: {'Expired' if days_left <= 0 else f'{days_left} Days Remaining'}

To keep your digital business cards, interactive NFC tap links, QR codes, and team workspace active without interruption, please renew your yearly subscription:

Renew Your Plan: {renew_url}

Thank you for trusting BrandNest for your professional identity.

Warm regards,
BrandNest Subscriptions & Billing Team
support@brandnest.in | https://brandnest.in
"""

    html_message = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 24px; color: #0F172A; }}
    .container {{ max-width: 580px; margin: 0 auto; background: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.04); }}
    .header {{ background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); color: #FFFFFF; padding: 28px 32px; text-align: left; }}
    .brand {{ font-size: 22px; font-weight: 800; letter-spacing: -0.02em; display: flex; align-items: center; gap: 8px; }}
    .brand span {{ color: #0084FF; }}
    .tagline {{ font-size: 13px; color: #94A3B8; margin-top: 4px; }}
    .content {{ padding: 32px; }}
    .greeting {{ font-size: 18px; font-weight: 700; color: #0F172A; margin-bottom: 12px; }}
    .lead-text {{ font-size: 14.5px; line-height: 1.6; color: #334155; margin-bottom: 24px; }}
    .card-box {{ background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; margin-bottom: 28px; }}
    .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #E2E8F0; font-size: 13.5px; }}
    .detail-row:last-child {{ border-bottom: none; }}
    .detail-label {{ color: #64748B; font-weight: 500; }}
    .detail-val {{ color: #0F172A; font-weight: 700; text-align: right; }}
    .badge-warn {{ background: #FEF3C7; color: #B45309; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }}
    .badge-expired {{ background: #FEE2E2; color: #DC2626; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }}
    .btn-renew {{ display: inline-block; background: #0084FF; color: #FFFFFF !important; text-decoration: none; padding: 14px 28px; border-radius: 10px; font-weight: 700; font-size: 15px; box-shadow: 0 4px 14px rgba(0, 132, 255, 0.35); text-align: center; }}
    .footer {{ background: #F1F5F9; padding: 20px 32px; font-size: 12px; color: #64748B; text-align: center; border-top: 1px solid #E2E8F0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">Brand<span>Nest</span></div>
      <div class="tagline">Digital Business Cards & Smart NFC Infrastructure</div>
    </div>
    <div class="content">
      <div class="greeting">Hello {recipient_name or 'Valued Customer'},</div>
      <p class="lead-text">
        This is a friendly notification that your <strong>{plan_name}</strong> {time_msg}.
      </p>

      <div class="card-box">
        <div class="detail-row">
          <span class="detail-label">Subscription Plan:</span>
          <span class="detail-val">{plan_name}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Billing Cycle:</span>
          <span class="detail-val">Yearly Renewable</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Registered Gmail:</span>
          <span class="detail-val">{recipient_email}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Expiration Date:</span>
          <span class="detail-val">{formatted_exp}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Current Status:</span>
          <span class="detail-val">
            <span class="{'badge-expired' if days_left <= 0 else 'badge-warn'}">
              {'Expired' if days_left <= 0 else f'{days_left} Days Left'}
            </span>
          </span>
        </div>
      </div>

      <div style="text-align: center; margin: 32px 0 16px;">
        <a href="{renew_url}" class="btn-renew">Renew Yearly Subscription &rarr;</a>
      </div>
      <p style="font-size: 12px; color: #94A3B8; text-align: center; margin: 0;">
        Fast 1-click renewal. All card configurations, custom links, and lead records are seamlessly maintained.
      </p>
    </div>
    <div class="footer">
      BrandNest Global Technologies &bull; Automated Subscription Alerts<br>
      You received this email because you signed up for BrandNest with {recipient_email}.
    </div>
  </div>
</body>
</html>"""

    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'BrandNest <renewals@brandnest.in>')
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Sent plan expiration notification to {recipient_email} for plan {plan_name}")
        return {'success': True, 'subject': subject, 'recipient': recipient_email}
    except Exception as exc:
        logger.error(f"Failed to send expiration notification to {recipient_email}: {exc}")
        return {'success': False, 'error': str(exc)}


def send_super_admin_nfc_order_notification(card, share_url=None):
    """
    Sends an automated email notification to Super Admin whenever a user pays for and publishes
    a customized physical NFC business card, including complete engraving/design specs and shareable link.
    """
    from django.contrib.auth.models import User

    admin_recipients = set()
    default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'BrandNest <admin@brandnest.io>')
    admin_recipients.add(getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', 'admin@brandnest.io'))
    for u in User.objects.filter(is_staff=True).exclude(email=''):
        admin_recipients.add(u.email)
    admin_recipients = list(admin_recipients)

    nfc = (card.layout_config or {}).get('nfc_card', {})
    client_name = card.owner_name or (card.user.get_full_name() if card.user else '') or card.business_name
    client_email = card.email or (card.user.email if card.user else '') or 'Not provided'
    client_phone = card.phone or 'Not provided'
    if not share_url:
        share_url = card.share_url

    theme_name = nfc.get('theme', 'obsidian_black').replace('_', ' ').title()
    foil_name = nfc.get('foil', 'gold').title()
    card_name = nfc.get('name') or card.owner_name or client_name
    designation = nfc.get('designation') or card.tagline or 'Cardholder'
    company_name = nfc.get('company_name') or card.business_name
    website = nfc.get('website') or card.existing_website or share_url
    status = nfc.get('status', 'Ready for Printing & Dispatch')

    subject = f"🔔 New Physical NFC Card Order: {card.business_name} ({card.card_id})"

    plain_message = f"""SUPER ADMIN ALERT: New Physical NFC Business Card Order Received!

A client has completed payment and submitted their custom physical NFC card design for production and doorstep shipping.

CLIENT DETAILS:
- Client Name: {client_name}
- Email (Gmail): {client_email}
- Phone: {client_phone}
- Business Name: {card.business_name}
- Card ID: {card.card_id}
- Digital Card Live URL: {share_url}

PHYSICAL NFC CARD SPECIFICATIONS (FOR PRINTING & ENGRAVING):
- Physical Finish Theme: {theme_name}
- Foil Finish: {foil_name}
- Front Engraved Name: {card_name}
- Front Designation: {designation}
- Front Pass Tagline: {nfc.get('pass_tagline', 'BrandNest Smart Pass')}
- Front Chip Spec: {nfc.get('chip_spec', 'NTAG216 · 888 BYTES')}
- Back Company Name: {company_name}
- Back Touchpoint Tagline: {nfc.get('back_tagline', 'SMART CONTACTLESS TOUCHPOINT')}
- NFC Chip Target URL (to encode): {website}
- Tap Instruction: {nfc.get('tap_hint', 'Tap against any smartphone to open card')}
- Badge Text: {nfc.get('back_badge', 'Direct NFC Tap')}
- Production Status: {status}

View and print the production artwork sheet or update dispatch status in the Super Admin Console:
https://brandnest.in/enterprise-admin/nfc-orders/
"""

    html_message = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F8FAFC; margin: 0; padding: 20px; color: #0F172A; }}
    .container {{ max-width: 620px; margin: 0 auto; background: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0; overflow: hidden; }}
    .header {{ background: #0F172A; color: #FFFFFF; padding: 24px 30px; }}
    .badge {{ background: #0084FF; color: #FFFFFF; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 999px; text-transform: uppercase; }}
    .content {{ padding: 30px; }}
    .section-title {{ font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin-top: 20px; margin-bottom: 8px; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; }}
    .row {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 13.5px; }}
    .label {{ color: #64748B; }}
    .val {{ font-weight: 700; color: #0F172A; text-align: right; }}
    .btn {{ display: inline-block; background: #0F172A; color: #FFFFFF !important; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: 700; font-size: 14px; margin-top: 20px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">NFC Production Order</span>
      <h2 style="margin: 8px 0 2px; font-size: 20px;">Physical NFC Card Order Received</h2>
      <p style="margin: 0; font-size: 13px; color: #94A3B8;">Client submitted design for physical laser printing and express dispatch.</p>
    </div>
    <div class="content">
      <div class="section-title">Client & Contact Details</div>
      <div class="row"><span class="label">Client Name:</span><span class="val">{client_name}</span></div>
      <div class="row"><span class="label">Contact Email:</span><span class="val">{client_email}</span></div>
      <div class="row"><span class="label">Contact Phone:</span><span class="val">{client_phone}</span></div>
      <div class="row"><span class="label">Business Name:</span><span class="val">{card.business_name}</span></div>
      <div class="row"><span class="label">Card Identifier:</span><span class="val">{card.card_id}</span></div>
      <div class="row"><span class="label">Live Card URL:</span><span class="val"><a href="{share_url}" target="_blank">{share_url}</a></span></div>

      <div class="section-title">NFC Hardware & Engraving Specifications</div>
      <div class="row"><span class="label">Finish Theme:</span><span class="val">{theme_name}</span></div>
      <div class="row"><span class="label">Metallic Foil:</span><span class="val">{foil_name}</span></div>
      <div class="row"><span class="label">Front Name:</span><span class="val">{card_name}</span></div>
      <div class="row"><span class="label">Front Designation:</span><span class="val">{designation}</span></div>
      <div class="row"><span class="label">Front Pass Tagline:</span><span class="val">{nfc.get('pass_tagline', 'BrandNest Smart Pass')}</span></div>
      <div class="row"><span class="label">Chip Spec:</span><span class="val">{nfc.get('chip_spec', 'NTAG216 · 888 BYTES')}</span></div>
      <div class="row"><span class="label">Back Company:</span><span class="val">{company_name}</span></div>
      <div class="row"><span class="label">Laser Website URL:</span><span class="val">{website}</span></div>
      <div class="row"><span class="label">Status:</span><span class="val" style="color:#10B981;">{status}</span></div>

      <div style="text-align: center;">
        <a href="https://brandnest.in/enterprise-admin/nfc-orders/" class="btn">Open Super Admin NFC Console &rarr;</a>
      </div>
    </div>
  </div>
</body>
</html>"""

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=default_from,
            recipient_list=admin_recipients,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Sent Super Admin NFC order alert to {admin_recipients} for card {card.card_id}")
        return {'success': True, 'recipients': admin_recipients}
    except Exception as exc:
        logger.error(f"Failed to send Super Admin NFC order alert: {exc}")
        return {'success': False, 'error': str(exc)}


def get_user_notification_email(card):
    """
    Resolves the user's primary notification email address.
    Prioritizes the authenticated signup/login email (card.user.email) first,
    then the payment receipt email, then the card profile email.
    """
    if card.user and card.user.email and card.user.email.strip():
        return card.user.email.strip()
    receipt_email = (card.layout_config or {}).get('payment_receipt', {}).get('email')
    if receipt_email and str(receipt_email).strip():
        return str(receipt_email).strip()
    if card.email and card.email.strip():
        return card.email.strip()
    return None


def get_user_notification_recipients(card):
    """
    Returns unique recipient email addresses for client notifications,
    guaranteeing that the account login/signup email is always included.
    """
    recipients = []
    primary = get_user_notification_email(card)
    if primary:
        recipients.append(primary)
    if card.email and card.email.strip() and card.email.strip() not in recipients:
        recipients.append(card.email.strip())
    return recipients


def send_user_nfc_order_placed_notification(card, share_url=None):
    """
    Sends an automated 'Order Placed' confirmation email notification to the user's
    login/signup email when they pay for or order a physical contactless NFC card.
    """
    recipients = get_user_notification_recipients(card)
    if not recipients:
        return {'success': False, 'error': 'No client email found'}

    recipient_name = card.owner_name or (card.user.get_full_name() if card.user else '') or card.business_name
    default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'BrandNest Deliveries <orders@brandnest.in>')

    if not share_url:
        share_url = card.share_url

    nfc = (card.layout_config or {}).get('nfc_card', {})
    theme_name = nfc.get('theme', 'obsidian_black').replace('_', ' ').title()
    foil_name = nfc.get('foil', 'gold').title()
    card_name = nfc.get('name') or card.owner_name or recipient_name
    designation = nfc.get('designation') or card.tagline or 'Cardholder'
    company_name = nfc.get('company_name') or card.business_name
    chip_spec = nfc.get('chip_spec', 'NTAG216 · 888 BYTES')
    preview_url = f"https://brandnest.in/card/preview/{card.card_id}/"

    subject = f"🎉 Order Placed: Physical Contactless NFC Card Confirmed ({card.business_name})"

    plain_message = f"""Hello {recipient_name},

Thank you for your order! Your BrandNest Physical Contactless NFC Business Card order has been placed and received by our fulfillment center.

ORDER STATUS: Order Placed (Queued for Printing & Engraving)

CARD & SPECIFICATION DETAILS:
- Cardholder Name: {card_name}
- Designation: {designation}
- Business Name: {company_name}
- Finish Theme: {theme_name}
- Metallic Foil: {foil_name}
- Contactless Chip: {chip_spec}
- Card ID: {card.card_id}
- Digital Card Subdomain / Share URL: {share_url}

FULFILLMENT ROADMAP:
1. [✓] Order Placed - Order details verified and queued for laser production.
2. [ ] Printing & Engraving - Custom high-precision UV printing & chip encoding.
3. [ ] Ready for Dispatch - Multi-angle visual quality & tap verification.
4. [ ] Shipped - Handed over to express courier with doorstep tracking.
5. [ ] Delivered - Arrives at your doorstep ready to tap!

You can preview your 3D card artwork and track order progress anytime at:
{preview_url}

Thank you for choosing BrandNest!

Warm regards,
BrandNest Hardware Fulfillment Team
orders@brandnest.in | https://brandnest.in
"""

    html_message = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F8FAFC; margin: 0; padding: 20px; color: #0F172A; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.06); }}
    .header {{ background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); color: #FFFFFF; padding: 28px 32px; }}
    .content {{ padding: 32px; }}
    .status-badge {{ display: inline-block; background: #DBEAFE; color: #1D4ED8; font-weight: 800; font-size: 13px; padding: 6px 16px; border-radius: 999px; margin-bottom: 16px; }}
    .spec-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: #F8FAFC; border-radius: 10px; overflow: hidden; }}
    .spec-table td {{ padding: 10px 14px; font-size: 13.5px; border-bottom: 1px solid #E2E8F0; }}
    .spec-label {{ color: #64748B; font-weight: 600; width: 40%; }}
    .spec-val {{ color: #0F172A; font-weight: 700; text-align: right; }}
    .timeline {{ margin: 24px 0; padding: 16px 20px; background: #F8FAFC; border-radius: 12px; border: 1px solid #E2E8F0; }}
    .timeline-step {{ margin-bottom: 8px; font-size: 13px; line-height: 1.5; }}
    .timeline-step:last-child {{ margin-bottom: 0; }}
    .step-active {{ font-weight: 800; color: #1D4ED8; }}
    .step-pending {{ color: #94A3B8; }}
    .btn {{ display: inline-block; background: #0084FF; color: #FFFFFF !important; text-decoration: none; padding: 12px 26px; border-radius: 10px; font-weight: 700; font-size: 14px; margin-top: 10px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #38BDF8; margin-bottom: 4px;">Hardware Fulfillment</div>
      <h2 style="margin: 0 0 6px; font-size: 22px;">Physical NFC Card Order Confirmed!</h2>
      <p style="margin: 0; font-size: 13px; color: #94A3B8;">We received your order and queued your custom design for physical laser fabrication.</p>
    </div>
    <div class="content">
      <p>Hello <strong>{recipient_name}</strong>,</p>
      <p>Thank you for ordering your custom contactless physical smart business card! We have received your order details and payment.</p>

      <div class="status-badge">⚡ Status: Order Placed</div>

      <table class="spec-table">
        <tr><td class="spec-label">Cardholder Name</td><td class="spec-val">{card_name}</td></tr>
        <tr><td class="spec-label">Designation / Role</td><td class="spec-val">{designation}</td></tr>
        <tr><td class="spec-label">Business Name</td><td class="spec-val">{company_name}</td></tr>
        <tr><td class="spec-label">Finish Theme</td><td class="spec-val">{theme_name}</td></tr>
        <tr><td class="spec-label">Metallic Foil</td><td class="spec-val">{foil_name}</td></tr>
        <tr><td class="spec-label">Contactless Chip</td><td class="spec-val">{chip_spec}</td></tr>
        <tr><td class="spec-label">Card Identifier</td><td class="spec-val">{card.card_id}</td></tr>
        <tr><td class="spec-label">Digital Card Link</td><td class="spec-val"><a href="{share_url}" target="_blank" style="color:#0084FF;">{share_url}</a></td></tr>
      </table>

      <div class="timeline">
        <div style="font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; margin-bottom: 10px;">Fulfillment Progress:</div>
        <div class="timeline-step step-active">✓ 1. Order Placed (Current)</div>
        <div class="timeline-step step-pending">&bull; 2. Printing &amp; Laser Engraving</div>
        <div class="timeline-step step-pending">&bull; 3. Ready for Dispatch</div>
        <div class="timeline-step step-pending">&bull; 4. Shipped (Express Courier)</div>
        <div class="timeline-step step-pending">&bull; 5. Delivered &amp; Tap Ready</div>
      </div>

      <p style="font-size: 13px; color: #64748B;">You will receive automated email updates as your card moves through production, dispatch, and delivery.</p>

      <div style="text-align: center; margin-top: 24px;">
        <a href="{preview_url}" class="btn">View Live 3D Card Preview &rarr;</a>
      </div>
    </div>
  </div>
</body>
</html>"""

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=default_from,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Sent NFC order placed confirmation to {recipients} for card {card.card_id}")
        return {'success': True, 'recipients': recipients}
    except Exception as exc:
        logger.error(f"Failed to send NFC order placed confirmation to {recipients}: {exc}")
        return {'success': False, 'error': str(exc)}


def send_user_nfc_status_update_notification(card, new_status, tracking_info=None):
    """
    Sends an automated email notification to the user's signup/login email when Super Admin
    updates the NFC card order status (Order Placed, Printing & Engraving, Ready for Dispatch, Shipped, Delivered).
    """
    recipients = get_user_notification_recipients(card)
    if not recipients:
        return {'success': False, 'error': 'No client email found'}

    recipient_name = card.owner_name or (card.user.get_full_name() if card.user else '') or card.business_name
    default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'BrandNest Deliveries <orders@brandnest.in>')

    nfc = (card.layout_config or {}).get('nfc_card', {})
    theme_name = nfc.get('theme', 'obsidian_black').replace('_', ' ').title()
    foil_name = nfc.get('foil', 'gold').title()
    card_name = nfc.get('name') or card.owner_name or recipient_name
    designation = nfc.get('designation') or card.tagline or 'Cardholder'
    company_name = nfc.get('company_name') or card.business_name
    chip_spec = nfc.get('chip_spec', 'NTAG216 · 888 BYTES')
    preview_url = f"https://brandnest.in/card/preview/{card.card_id}/"
    share_url = card.share_url

    norm_status = (new_status or '').strip()
    status_lower = norm_status.lower()

    if 'order placed' in status_lower or 'new order' in status_lower:
        canonical_status = 'Order Placed'
        badge_bg = '#DBEAFE'
        badge_color = '#1D4ED8'
        step_active = 1
        subject = f"Order Placed: Your BrandNest Physical NFC Card is Confirmed ({card.business_name})"
        headline = "Your Physical NFC Card Order is Confirmed & Queued"
        stage_desc = "Your order for a custom physical contactless NFC card has been placed and received by our fulfillment center. It is currently queued for laser production and chip encoding."
    elif 'printing' in status_lower or 'engraving' in status_lower or 'production' in status_lower:
        canonical_status = 'Printing & Engraving'
        badge_bg = '#EDE9FE'
        badge_color = '#6D28D9'
        step_active = 2
        subject = f"Printing & Engraving: Your BrandNest Physical NFC Card is in Production ({card.business_name})"
        headline = "Your Physical Card is Being Printed & Laser Engraved"
        stage_desc = "Your custom physical NFC card is actively on our production line! Our hardware team is precision UV laser-engraving your card design, embedding metallic foil accents, and encoding the high-speed contactless smart chip."
    elif 'ready' in status_lower or 'dispatch' in status_lower or 'packed' in status_lower:
        canonical_status = 'Ready for Dispatch'
        badge_bg = '#E0F2FE'
        badge_color = '#0369A1'
        step_active = 3
        subject = f"Ready for Dispatch: Your BrandNest Physical NFC Card is Packed ({card.business_name})"
        headline = "Quality Verified & Ready for Dispatch"
        stage_desc = "Your physical NFC card has completed laser engraving and passed our multi-angle visual inspection and contactless tap verification tests. It is securely packaged and waiting for courier pickup."
    elif 'shipped' in status_lower or 'transit' in status_lower:
        canonical_status = 'Shipped'
        badge_bg = '#FEF3C7'
        badge_color = '#B45309'
        step_active = 4
        subject = f"🚚 Shipped: Your BrandNest Physical NFC Card is On Its Way! ({card.business_name})"
        headline = "Your NFC Card Has Been Shipped!"
        stage_desc = "Your physical contactless NFC card package has been handed over to our express delivery partner and is en route to your doorstep!"
    elif 'delivered' in status_lower:
        canonical_status = 'Delivered'
        badge_bg = '#DCFCE7'
        badge_color = '#15803D'
        step_active = 5
        subject = f"🎉 Delivered: Your BrandNest Physical NFC Card Has Arrived! ({card.business_name})"
        headline = "Your NFC Card Has Been Delivered!"
        stage_desc = "Your BrandNest physical contactless smart card has arrived! Simply tap your card against the top-back of any iPhone or Android phone to instantly share your digital business card profile."
    else:
        canonical_status = norm_status
        badge_bg = '#F1F5F9'
        badge_color = '#334155'
        step_active = 3
        subject = f"Update on Your BrandNest Physical NFC Card: {norm_status} ({card.business_name})"
        headline = f"Status Update: {norm_status}"
        stage_desc = f"The production status of your BrandNest physical NFC card has been updated to '{norm_status}' by our fulfillment team."

    tracking_text = f"\nCourier / Tracking Details: {tracking_info}\n" if tracking_info else ""
    tracking_html = f"""
      <div style="background:#F1F5F9;border-left:4px solid #0084FF;padding:12px 16px;border-radius:6px;margin:18px 0;font-size:13.5px;">
        <strong style="color:#0F172A;">Courier &amp; Tracking Details:</strong>
        <div style="color:#334155;margin-top:4px;font-family:monospace;font-size:14px;font-weight:700;">{tracking_info}</div>
      </div>
    """ if tracking_info else ""

    def step_class(step_num):
        if step_num < step_active:
            return "✓", "step-done", "#059669"
        elif step_num == step_active:
            return "➤", "step-active", badge_color
        else:
            return "•", "step-pending", "#94A3B8"

    s1_icon, s1_cls, s1_color = step_class(1)
    s2_icon, s2_cls, s2_color = step_class(2)
    s3_icon, s3_cls, s3_color = step_class(3)
    s4_icon, s4_cls, s4_color = step_class(4)
    s5_icon, s5_cls, s5_color = step_class(5)

    plain_message = f"""Hello {recipient_name},

Great news! The fulfillment status of your custom BrandNest Physical NFC Business Card has been updated by our team.

CURRENT STATUS: {canonical_status}
{tracking_text}
{stage_desc}

CARD & ORDER DETAILS:
- Cardholder Name: {card_name}
- Business Name: {company_name}
- Card ID: {card.card_id}
- Finish & Foil: {theme_name} ({foil_name} Foil)
- Chip: {chip_spec}
- Digital Card Subdomain / Share URL: {share_url}

FULFILLMENT STATUS ROADMAP:
1. [{s1_icon}] Order Placed
2. [{s2_icon}] Printing & Engraving
3. [{s3_icon}] Ready for Dispatch
4. [{s4_icon}] Shipped
5. [{s5_icon}] Delivered

You can preview your card and track fulfillment anytime at:
{preview_url}

Thank you for choosing BrandNest!

Warm regards,
BrandNest Hardware Fulfillment Team
orders@brandnest.in | https://brandnest.in
"""

    html_message = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F8FAFC; margin: 0; padding: 20px; color: #0F172A; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #FFFFFF; border-radius: 16px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.06); }}
    .header {{ background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); color: #FFFFFF; padding: 28px 32px; }}
    .content {{ padding: 32px; }}
    .status-badge {{ display: inline-block; background: {badge_bg}; color: {badge_color}; font-weight: 800; font-size: 13.5px; padding: 6px 18px; border-radius: 999px; margin-bottom: 16px; }}
    .spec-table {{ width: 100%; border-collapse: collapse; margin: 18px 0; background: #F8FAFC; border-radius: 10px; overflow: hidden; }}
    .spec-table td {{ padding: 9px 14px; font-size: 13px; border-bottom: 1px solid #E2E8F0; }}
    .spec-label {{ color: #64748B; font-weight: 600; width: 40%; }}
    .spec-val {{ color: #0F172A; font-weight: 700; text-align: right; }}
    .timeline {{ margin: 24px 0; padding: 16px 20px; background: #F8FAFC; border-radius: 12px; border: 1px solid #E2E8F0; }}
    .timeline-step {{ margin-bottom: 8px; font-size: 13px; line-height: 1.5; }}
    .timeline-step:last-child {{ margin-bottom: 0; }}
    .btn {{ display: inline-block; background: #0084FF; color: #FFFFFF !important; text-decoration: none; padding: 12px 26px; border-radius: 10px; font-weight: 700; font-size: 14px; margin-top: 10px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #38BDF8; margin-bottom: 4px;">BrandNest Hardware Fulfillment</div>
      <h2 style="margin: 0 0 6px; font-size: 22px;">{headline}</h2>
      <p style="margin: 0; font-size: 13px; color: #94A3B8;">Physical Contactless NFC Card Order Update</p>
    </div>
    <div class="content">
      <p>Hello <strong>{recipient_name}</strong>,</p>
      <p>The fulfillment status for your custom physical NFC card has been updated:</p>

      <div class="status-badge">✓ Status: {canonical_status}</div>

      <p style="font-size: 14px; color: #334155; line-height: 1.6;">
        {stage_desc}
      </p>

      {tracking_html}

      <table class="spec-table">
        <tr><td class="spec-label">Cardholder Name</td><td class="spec-val">{card_name}</td></tr>
        <tr><td class="spec-label">Business Name</td><td class="spec-val">{company_name}</td></tr>
        <tr><td class="spec-label">Card Identifier</td><td class="spec-val">{card.card_id}</td></tr>
        <tr><td class="spec-label">Finish &amp; Foil</td><td class="spec-val">{theme_name} ({foil_name} Foil)</td></tr>
        <tr><td class="spec-label">NFC Chip</td><td class="spec-val">{chip_spec}</td></tr>
        <tr><td class="spec-label">Digital Card Link</td><td class="spec-val"><a href="{share_url}" target="_blank" style="color:#0084FF;">{share_url}</a></td></tr>
      </table>

      <div class="timeline">
        <div style="font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; margin-bottom: 10px;">Fulfillment Roadmap:</div>
        <div class="timeline-step" style="color: {s1_color}; font-weight: {'800' if step_active == 1 else '600'};">{s1_icon} 1. Order Placed</div>
        <div class="timeline-step" style="color: {s2_color}; font-weight: {'800' if step_active == 2 else '600'};">{s2_icon} 2. Printing &amp; Engraving</div>
        <div class="timeline-step" style="color: {s3_color}; font-weight: {'800' if step_active == 3 else '600'};">{s3_icon} 3. Ready for Dispatch</div>
        <div class="timeline-step" style="color: {s4_color}; font-weight: {'800' if step_active == 4 else '600'};">{s4_icon} 4. Shipped (Courier Dispatch)</div>
        <div class="timeline-step" style="color: {s5_color}; font-weight: {'800' if step_active == 5 else '600'};">{s5_icon} 5. Delivered &amp; Tap Ready</div>
      </div>

      <div style="text-align: center; margin-top: 24px;">
        <a href="{preview_url}" class="btn">View Card &amp; Order Preview &rarr;</a>
      </div>
    </div>
  </div>
</body>
</html>"""

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=default_from,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Sent NFC status update ({canonical_status}) to {recipients} for card {card.card_id}")
        return {'success': True, 'recipients': recipients}
    except Exception as exc:
        logger.error(f"Failed to send NFC status update to {recipients}: {exc}")
        return {'success': False, 'error': str(exc)}


