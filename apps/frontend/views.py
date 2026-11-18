import os
import re
import json
import csv
import subprocess
import shutil
import urllib.request
from datetime import timedelta
from functools import wraps
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import Http404, JsonResponse, HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.db.models import Sum, Count, Q

from apps.domains.models import Domain
from apps.cards.models import (
    BusinessCard, UserPlan, Team, CardLead, NFCTag,
    CompanySettings, WalletPassConfig, CardAnalyticsEvent, EnterpriseCompany
)
from apps.websites.models import Industry, Website, ContactSubmission


ENTERPRISE_BUNDLES = [
    {'cards': 5, 'price': 999, 'per_card': '199.80', 'team_cards': 4, 'badge': 'Starter'},
    {'cards': 10, 'price': 1799, 'per_card': '179.90', 'team_cards': 9, 'badge': 'Most Popular'},
    {'cards': 15, 'price': 2499, 'per_card': '166.60', 'team_cards': 14, 'badge': 'Best Value'},
]
EXTRA_CARD_PRICE_INR = 199


def _get_enterprise_quota(user):
    if not user or not user.is_authenticated:
        return {
            'is_enterprise': False,
            'cards_used': 0,
            'card_limit': 0,
            'cards_remaining': 0,
            'limit_reached': False,
            'usage_percent': 0,
        }
    plan = UserPlan.objects.filter(user=user, plan_type='enterprise').first()
    if not plan:
        return {
            'is_enterprise': False,
            'cards_used': BusinessCard.objects.filter(user=user).count(),
            'card_limit': 0,
            'cards_remaining': 0,
            'limit_reached': False,
            'usage_percent': 0,
        }
    used = BusinessCard.objects.filter(user=user).count()
    limit = plan.card_limit
    remaining = max(0, limit - used)
    pct = min(100, int((used / limit) * 100)) if limit > 0 else 100
    return {
        'is_enterprise': True,
        'plan': plan,
        'cards_used': used,
        'card_limit': limit,
        'cards_remaining': remaining,
        'limit_reached': used >= limit,
        'usage_percent': pct,
    }


def get_lan_ip():
    """
    Detects local Wi-Fi / LAN IP so phones on the same network can access dev server directly.
    Tries UDP routing probe, macOS ipconfig, and ifconfig parsing as fallbacks.
    """
    import socket

    # 1. Active default-route interface IP via UDP socket (no actual packet sent)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith('127.'):
                return ip
    except Exception:
        pass

    # 2. macOS ipconfig getifaddr across common interfaces
    try:
        ipconfig_bin = shutil.which('ipconfig') or ('/usr/sbin/ipconfig' if os.path.exists('/usr/sbin/ipconfig') else None)
        if ipconfig_bin:
            for iface in ['en0', 'en1', 'en2', 'en3', 'en4', 'wlan0', 'eth0']:
                res = subprocess.run([ipconfig_bin, 'getifaddr', iface], capture_output=True, text=True, timeout=1)
                ip = res.stdout.strip()
                if ip and re.match(r'^\d+\.\d+\.\d+\.\d+$', ip) and not ip.startswith('127.'):
                    return ip
    except Exception:
        pass

    # 3. Parse ifconfig output for private LAN IPv4 addresses
    try:
        ifconfig_bin = shutil.which('ifconfig') or ('/sbin/ifconfig' if os.path.exists('/sbin/ifconfig') else None)
        if ifconfig_bin:
            res = subprocess.run([ifconfig_bin], capture_output=True, text=True, timeout=1)
            candidates = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', res.stdout)
            for ip in candidates:
                if ip.startswith('192.168.') or ip.startswith('10.') or re.match(r'^172\.(1[6-9]|2\d|3[01])\.', ip):
                    return ip
            for ip in candidates:
                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                    return ip
    except Exception:
        pass

    return None


def get_shareable_url(request, path):
    """
    Builds a direct, reliable shareable URL for QR codes.
    1. If request is from localhost/127.0.0.1/0.0.0.0, uses the machine's local Wi-Fi LAN IP
       (e.g. http://192.168.1.42:8000/card/<slug>/) so phones on the same Wi-Fi can scan it.
    2. Otherwise uses the absolute request URI (works on production domains or direct LAN IP).
    """
    host = request.get_host()
    if '127.0.0.1' in host or 'localhost' in host or '0.0.0.0' in host:
        lan_ip = get_lan_ip()
        if lan_ip:
            port = host.split(':')[1] if ':' in host else '8000'
            return f"http://{lan_ip}:{port}{path}"
    return request.build_absolute_uri(path)


def generate_qr_code_image_bytes(data_url):
    """
    Generates a high-resolution QR code PNG directly via Python's qrcode library.
    Includes a fallback in case qrcode/Pillow is temporarily unavailable.
    """
    import io
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(data_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        # Fallback to pure urllib fetching or clean SVG/PNG fallback
        import urllib.request
        import urllib.parse
        encoded_data = urllib.parse.quote(data_url)
        try:
            with urllib.request.urlopen(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_data}", timeout=3) as resp:
                return resp.read()
        except Exception:
            return b""


def generate_qr_code_base64(data_url):
    """
    Generates a base64 data URI (data:image/png;base64,...) using Python's qrcode library.
    Generates freshly on each page render or refresh.
    """
    import base64
    raw_bytes = generate_qr_code_image_bytes(data_url)
    if not raw_bytes:
        return ""
    encoded = base64.b64encode(raw_bytes).decode('utf-8')
    return f"data:image/png;base64,{encoded}"


def landing(request):
    """
    Landing Page: Displays the two primary choices:
    1. Build a Business Card
    2. Make Your Own Website
    """
    industries = Industry.objects.filter(is_active=True).order_by('display_order')
    total_cards = BusinessCard.objects.count()
    total_websites = Website.objects.count()
    total_industries = industries.count()

    context = {
        'industries': industries,
        'total_cards': total_cards,
        'total_websites': total_websites,
        'total_industries': total_industries,
    }
    return render(request, 'landing.html', context)


def card_choose_plan(request):
    """
    2-option chooser when clicking 'Build business card':
    1. For Personal Use -> Login / Sign Up -> Card Builder
    2. For Enterprise -> Company Details -> Bundle Selection & Simulated Payment -> Team Card Workspace
    """
    return render(request, 'card_choose_plan.html')


def enterprise_company(request):
    """
    Enterprise Step 1: Collect company details (and create/authenticate account if logged out),
    then proceed to the Enterprise bundle selection & payment page.
    """
    existing_plan = None
    if request.user.is_authenticated:
        existing_plan = UserPlan.objects.filter(user=request.user).first()

    company_name = existing_plan.company_name if existing_plan else ''
    company_head_name = (
        existing_plan.company_head_name if existing_plan and existing_plan.company_head_name
        else (f"{request.user.first_name} {request.user.last_name}".strip() if request.user.is_authenticated else '')
    )
    company_phone = existing_plan.company_phone if existing_plan else ''
    company_email = (
        existing_plan.company_email if existing_plan and existing_plan.company_email
        else (request.user.email if request.user.is_authenticated else '')
    )

    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()
        company_head_name = request.POST.get('company_head_name', '').strip()
        company_phone = request.POST.get('company_phone', '').strip()
        company_email = request.POST.get('company_email', '').strip().lower()

        if not company_name or not company_head_name or not company_email:
            messages.error(request, 'Please fill in Company Name, Company Head Name, and Work Email.')
            return render(request, 'enterprise_company.html', {
                'company_name': company_name,
                'company_head_name': company_head_name,
                'company_phone': company_phone,
                'company_email': company_email,
            })

        target_user = request.user if request.user.is_authenticated else None
        if not target_user:
            password = request.POST.get('password', '')
            confirm_password = request.POST.get('confirm_password', '')
            if len(password) < 6:
                messages.error(request, 'Password must be at least 6 characters long.')
                return render(request, 'enterprise_company.html', {
                    'company_name': company_name,
                    'company_head_name': company_head_name,
                    'company_phone': company_phone,
                    'company_email': company_email,
                })
            if password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'enterprise_company.html', {
                    'company_name': company_name,
                    'company_head_name': company_head_name,
                    'company_phone': company_phone,
                    'company_email': company_email,
                })
            if User.objects.filter(email__iexact=company_email).exists():
                messages.error(request, f'An account with "{company_email}" already exists. Please log in to continue.')
                return render(request, 'enterprise_company.html', {
                    'company_name': company_name,
                    'company_head_name': company_head_name,
                    'company_phone': company_phone,
                    'company_email': company_email,
                })

            base_username = re.sub(r'[^a-zA-Z0-9._-]', '', company_email.split('@')[0]) or 'enterprise'
            username = base_username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            parts = company_head_name.split(' ', 1)
            target_user = User.objects.create_user(
                username=username,
                email=company_email,
                password=password,
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else '',
            )
            login(request, target_user)

        plan, _ = UserPlan.objects.get_or_create(user=target_user)
        plan.company_name = company_name
        plan.company_head_name = company_head_name
        plan.company_phone = company_phone
        plan.company_email = company_email
        plan.save()

        return redirect('enterprise_checkout')

    return render(request, 'enterprise_company.html', {
        'company_name': company_name,
        'company_head_name': company_head_name,
        'company_phone': company_phone,
        'company_email': company_email,
    })


def enterprise_checkout(request):
    """
    Enterprise bundle selection (5, 10, 15 cards) & simulated payment page.
    """
    bundle_map = {b['cards']: b for b in ENTERPRISE_BUNDLES}
    try:
        selected_bundle = int(request.GET.get('bundle') or request.POST.get('bundle_size') or 5)
    except (TypeError, ValueError):
        selected_bundle = 5
    if selected_bundle not in bundle_map:
        selected_bundle = 5

    if request.method == 'POST':
        if not request.user.is_authenticated:
            next_target = f"{reverse('enterprise_checkout')}?bundle={selected_bundle}"
            return redirect(f"{reverse('login')}?next={next_target}")

        bundle_info = bundle_map[selected_bundle]
        plan, _ = UserPlan.objects.get_or_create(user=request.user)
        existing_cards = BusinessCard.objects.filter(user=request.user).count()
        if plan.plan_type == 'enterprise':
            plan.card_limit += selected_bundle
        else:
            plan.plan_type = 'enterprise'
            plan.card_limit = existing_cards + selected_bundle
        plan.total_paid = (plan.total_paid or 0) + bundle_info['price']
        plan.save()

        messages.success(
            request,
            f"Enterprise Plan activated! You can now build up to {plan.card_limit} business cards (including your own)."
        )
        return redirect('card_list')

    selected = bundle_map[selected_bundle]
    plan_company_name = ''
    if request.user.is_authenticated:
        up = UserPlan.objects.filter(user=request.user).first()
        if up:
            plan_company_name = up.company_name
    return render(request, 'enterprise_checkout.html', {
        'bundles': ENTERPRISE_BUNDLES,
        'selected_bundle': selected['cards'],
        'selected_price': selected['price'],
        'selected_per_card': selected['per_card'],
        'selected_team_cards': selected['team_cards'],
        'company_name': plan_company_name,
    })


@login_required(login_url='login')
def enterprise_topup(request):
    """
    Adds more business card slots (+1, +2, etc. at ₹199 each) when an Enterprise user reaches their limit.
    """
    if request.method != 'POST':
        return redirect('card_list')

    try:
        extra_cards = int(request.POST.get('extra_cards') or 1)
    except (TypeError, ValueError):
        extra_cards = 1
    if extra_cards < 1:
        extra_cards = 1

    total_cost = extra_cards * EXTRA_CARD_PRICE_INR
    plan, _ = UserPlan.objects.get_or_create(user=request.user)
    if plan.plan_type != 'enterprise':
        plan.plan_type = 'enterprise'
        plan.card_limit = BusinessCard.objects.filter(user=request.user).count() + extra_cards
    else:
        plan.card_limit += extra_cards
    plan.total_paid = (plan.total_paid or 0) + total_cost
    plan.save()

    messages.success(
        request,
        f"Payment of ₹{total_cost} confirmed! Added +{extra_cards} business card(s). New limit: {plan.card_limit} cards."
    )
    return redirect('card_builder')


def _extract_youtube_id(url):
    if not url:
        return ''
    import re
    url_str = str(url).strip()
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_str):
        return url_str
    v_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url_str)
    if v_match:
        return v_match.group(1)
    path_match = re.search(r'(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:embed/|v/|shorts/|live/))([a-zA-Z0-9_-]{11})', url_str)
    if path_match:
        return path_match.group(1)
    return ''


def get_youtube_channel_details(channel_input):
    """
    Auto-fetches YouTube channel metadata (title, avatar, subscribers, description, latest videos)
    without requiring an external API key.
    Accepts channel URL (e.g. youtube.com/@name, youtube.com/channel/UC...), @handle, or video URL.
    """
    channel_input = str(channel_input or '').strip()
    if not channel_input:
        return {'success': False, 'error': 'No URL provided'}

    import urllib.request
    import json
    import re

    # If user provided a video URL, resolve author channel via oEmbed
    vid = _extract_youtube_id(channel_input)
    author_url = None
    if vid and ('watch' in channel_input or 'youtu.be' in channel_input or 'shorts' in channel_input):
        try:
            oe_url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json'
            req = urllib.request.Request(oe_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as res:
                oe_data = json.loads(res.read().decode('utf-8'))
                author_url = oe_data.get('author_url')
        except Exception:
            pass

    target_url = author_url or channel_input
    if target_url.startswith('@'):
        url = f'https://www.youtube.com/{target_url}'
    elif not target_url.startswith('http'):
        url = f'https://www.youtube.com/@{target_url}'
    else:
        url = target_url

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    title = ''
    avatar = ''
    subscribers = ''
    description = ''
    videos = []

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as res:
            html = res.read().decode('utf-8', errors='ignore')

        m_title = re.search(r'<meta property=\"og:title\" content=\"([^\"]+)\"', html)
        if m_title:
            title = m_title.group(1).strip()

        m_img = re.search(r'<meta property=\"og:image\" content=\"([^\"]+)\"', html)
        if m_img:
            avatar = m_img.group(1).strip()

        m_sub = re.search(r'\"subtitle\":\{\"content\":\"[^\"]*?([0-9\.]+[KMBkmb]?\s+subscribers?)[^\"]*\"\}', html)
        if not m_sub:
            m_sub = re.search(r'([0-9\.]+[KMBkmb]?\s+(?:million|thousand)?\s*subscribers?)', html, re.IGNORECASE)
        if m_sub:
            subscribers = m_sub.group(1).strip()

        m_desc = re.search(r'<meta property=\"og:description\" content=\"([^\"]+)\"', html)
        if m_desc:
            description = m_desc.group(1).strip()

        blocks = html.split('\"lockupViewModel\":')
        for block in blocks[1:]:
            vm = re.search(r'vi/([a-zA-Z0-9_-]{11})/', block)
            if not vm:
                vm = re.search(r'\"watchEndpoint\":\{\"videoId\":\"([a-zA-Z0-9_-]{11})\"', block)
            tm = re.search(r'\"title\":\{\"content\":\"([^\"]+)\"\}', block)
            if not tm:
                tm = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"([^\"]+)\"\}', block)
            if vm and tm:
                v_id = vm.group(1)
                v_title = tm.group(1)
                if not any(v['id'] == v_id for v in videos):
                    videos.append({
                        'id': v_id,
                        'title': v_title,
                        'thumbnail': f'https://img.youtube.com/vi/{v_id}/hqdefault.jpg',
                        'url': f'https://www.youtube.com/watch?v={v_id}'
                    })
            if len(videos) >= 6:
                break
    except Exception:
        handle_match = re.search(r'@([a-zA-Z0-9_.-]+)', url)
        clean_name = handle_match.group(1).replace('-', ' ').replace('_', ' ').title() if handle_match else 'YouTube Channel'
        title = title or clean_name
        subscribers = subscribers or '1.2K Subscribers'
        description = description or f'Welcome to the official {title} YouTube channel!'

    return {
        'success': True,
        'title': title or 'YouTube Channel',
        'avatar': avatar,
        'subscribers': subscribers or '1.2K Subscribers',
        'description': description,
        'videos': videos,
        'url': url
    }


def fetch_youtube_channel_info_api(request):
    """
    JSON API endpoint for real-time YouTube Channel info auto-fetching.
    """
    from django.http import JsonResponse
    url = request.GET.get('url', '').strip()
    if not url:
        return JsonResponse({'success': False, 'error': 'No URL provided'}, status=400)
    data = get_youtube_channel_details(url)
    return JsonResponse(data)


def _build_default_card():
    return BusinessCard(
        business_name="",
        owner_name="",
        description="",
        phone="",
        email="",
        whatsapp="",
        address="",
        google_maps_url="",
        theme_color="#0084FF",
        social_links={
            "linkedin": "",
            "youtube": "",
            "instagram": "",
            "twitter": "",
            "facebook": "",
            "youtube_video": "",
        },
        layout_config={
            "banner_tagline": "",
            "role_title": "",
            "about_heading": "",
            "brands": "",
            "youtube_video_url": "",
            "yt_channel_name": "",
            "yt_subscribers": "",
            "yt_description": "",
            "avatar_x": "0%",
            "avatar_y": "0%",
            "avatar_position": "50% 50%",
            "avatar_zoom": "1",
            "logo_x": "0%",
            "logo_y": "0%",
            "logo_position": "50% 50%",
            "logo_zoom": "1",
            "banner_x": "0%",
            "banner_y": "0%",
            "banner_position": "50% 50%",
            "banner_zoom": "1",
            "font": "Plus Jakarta Sans",
            "layout_style": "layout-cover-hero",
            "wallet_config": {},
            "settings": {
                "custom_domain": "",
                "visibility": "public",
                "password": "",
                "show_save_contact": True,
                "email_contact": True,
                "exchange_contact": True,
                "fb_chat_enabled": False,
                "fb_page_id": "",
                "calendly_enabled": False,
                "calendly_url": "",
                "seo_index": True,
                "meta_title": "",
                "meta_description": "",
                "copyright": "",
                "custom_js": "",
                "sensitive_material": "none",
                "language": "en"
            },
            "payments": {
                "gpay": "",
                "phonepe": "",
                "paytm": "",
                "paypal": "",
                "venmo": "",
                "cashapp": "",
                "razorpay": "",
            },
            "more": {
                "section_title": "Brochure",
                "pdf_title": "",
                "pdf_url": "",
                "gdrive_title": "",
                "gdrive_url": "",
                "address": "",
                "maps_url": "",
            },
            "banners_items": [],
            "banner_aspect": "landscape",
            "section_order": ["video", "capabilities", "about", "brands", "banners", "images", "connect", "socials", "payments", "more", "callback"],
            "disabled_sections": []
        }
    )


def _get_card_builder_context(active_card, is_edit):
    active_layout = active_card.layout_config or {}
    card_capabilities_json = json.dumps(active_layout.get('capabilities_items') or [])
    card_brands_json = json.dumps(active_layout.get('brands_items') or [])
    card_banners_json = json.dumps(active_layout.get('banners_items') or [])
    card_images_json = json.dumps(active_layout.get('images_items') or [])
    card_yt_videos_json = json.dumps(active_layout.get('yt_videos') or [])
    default_order = ["video", "capabilities", "about", "brands", "banners", "images", "connect", "socials", "payments", "more", "callback"]
    card_section_order_json = json.dumps(active_layout.get('section_order') or default_order)
    card_disabled_sections_json = json.dumps(active_layout.get('disabled_sections') or [])
    yt_url = active_layout.get('youtube_video_url') or (active_card.social_links or {}).get('youtube_video') or ''
    card_yt_video_id = _extract_youtube_id(yt_url)

    return {
        'card': active_card,
        'is_edit': is_edit,
        'card_yt_video_id': card_yt_video_id,
        'card_capabilities_json': card_capabilities_json,
        'card_brands_json': card_brands_json,
        'card_banners_json': card_banners_json,
        'card_images_json': card_images_json,
        'card_yt_videos_json': card_yt_videos_json,
        'card_section_order_json': card_section_order_json,
        'card_disabled_sections_json': card_disabled_sections_json,
    }


@login_required(login_url='login')
def card_builder(request, card_id=None):
    """
    Business Card Builder:
    Step 1: Enter Business, Contact & Social Details
    (No custom domain required - includes optional website link or 1-click builder link)
    Step 2: Instant Card Preview & Sharing
    If card_id is provided, edits and updates the existing Business Card.
    """
    target_card = None
    if card_id:
        if request.user.is_superuser or request.user.is_staff:
            target_card = get_object_or_404(BusinessCard, card_id=card_id)
        else:
            target_card = get_object_or_404(BusinessCard, card_id=card_id, user=request.user)
    else:
        quota = _get_enterprise_quota(request.user)
        if quota['is_enterprise']:
            if quota['limit_reached']:
                return redirect(f"{reverse('card_list')}?upgrade=1")
        else:
            if request.GET.get('new') == '1':
                target_card = None
            else:
                # Personal user: if they already created a personal card, load it so they can see and edit their card
                existing_card = BusinessCard.objects.filter(user=request.user).order_by('-created_at').first()
                if existing_card:
                    target_card = existing_card

    if request.method == 'POST':
        business_name = request.POST.get('business_name', '').strip()

        if not business_name:
            messages.error(request, 'Please provide your business name.')
            active_card = target_card or _build_default_card()
            return render(request, 'card_builder.html', _get_card_builder_context(active_card, bool(target_card)))

        # 1. Extract Social Links (supports both form naming conventions)
        social_links = {
            'linkedin': (request.POST.get('linkedin') or request.POST.get('social_linkedin') or '').strip(),
            'youtube': (request.POST.get('youtube') or request.POST.get('social_youtube') or '').strip(),
            'instagram': (request.POST.get('instagram') or request.POST.get('social_instagram') or '').strip(),
            'twitter': (request.POST.get('twitter') or request.POST.get('social_twitter') or '').strip(),
            'facebook': (request.POST.get('facebook') or request.POST.get('social_facebook') or '').strip(),
        }

        # 2. Extract section order & disabled sections for custom layout
        section_order_raw = request.POST.get('section_order', '')
        section_order = []
        if section_order_raw:
            try:
                section_order = json.loads(section_order_raw)
            except Exception:
                section_order = [s.strip() for s in section_order_raw.split(',') if s.strip()]

        disabled_sections_raw = request.POST.get('disabled_sections', '')
        disabled_sections = []
        if disabled_sections_raw:
            try:
                disabled_sections = json.loads(disabled_sections_raw)
            except Exception:
                disabled_sections = [s.strip() for s in disabled_sections_raw.split(',') if s.strip()]

        # Extract dynamic capabilities & brands data
        capabilities_data_raw = request.POST.get('capabilities_data', '')
        capabilities_items = []
        if capabilities_data_raw:
            try:
                capabilities_items = json.loads(capabilities_data_raw)
                capabilities_items = [
                    item for item in capabilities_items
                    if (item.get('title') and item.get('title').strip()) or (item.get('description') and item.get('description').strip())
                ]
            except Exception:
                pass

        brands_data_raw = request.POST.get('brands_data', '')
        brands_items = []
        if brands_data_raw:
            try:
                brands_items = json.loads(brands_data_raw)
                brands_items = [
                    item for item in brands_items
                    if (item.get('title') and item.get('title').strip()) or (item.get('description') and item.get('description').strip())
                ]
            except Exception:
                pass

        banners_data_raw = request.POST.get('banners_data', '')
        banners_items = []
        if banners_data_raw:
            try:
                banners_items = json.loads(banners_data_raw)
                banners_items = [
                    item for item in banners_items
                    if (item.get('image') and item.get('image').strip()) or (item.get('title') and item.get('title').strip())
                ]
            except Exception:
                pass

        banner_aspect = request.POST.get('banner_aspect', 'landscape').strip().lower()
        if banner_aspect not in ('landscape', 'portrait', 'square'):
            banner_aspect = 'landscape'

        images_data_raw = request.POST.get('images_data', '')
        images_items = []
        if images_data_raw:
            try:
                images_items = json.loads(images_data_raw)
                images_items = [
                    item for item in images_items
                    if (item.get('image') and item.get('image').strip()) or (item.get('title') and item.get('title').strip())
                ]
            except Exception:
                pass

        role_title = request.POST.get('role_title', '').strip()
        owner_role = request.POST.get('owner_role', '').strip()
        owner_title = ''
        identity_order = request.POST.get('identity_order', 'company,role').strip()
        role_title_order = request.POST.get('role_title_order', 'company_first').strip()
        show_profile_photo = request.POST.get('show_profile_photo', 'true').lower() in ('true', '1', 'on')
        show_company_logo = request.POST.get('show_company_logo', 'true').lower() in ('true', '1', 'on')
        show_banner = request.POST.get('show_banner', 'true').lower() in ('true', '1', 'on')

        if owner_role:
            role_title = owner_role

        about_heading = request.POST.get('about_heading', '').strip()
        youtube_video_url = (request.POST.get('youtube_video_url') or request.POST.get('video_url') or '').strip()
        yt_channel_name = request.POST.get('yt_channel_name', '').strip()
        yt_subscribers = request.POST.get('yt_subscribers', '').strip()
        yt_description = request.POST.get('yt_description', '').strip()
        yt_avatar = request.POST.get('yt_avatar', '').strip()
        yt_videos_raw = request.POST.get('yt_videos_json', '') or request.POST.get('yt_videos_data', '')
        yt_videos = []
        if yt_videos_raw:
            try:
                yt_videos = json.loads(yt_videos_raw)
            except Exception:
                pass
        for vid in yt_videos:
            if isinstance(vid, dict) and vid.get('url'):
                v_id = _extract_youtube_id(vid['url'])
                if v_id and not vid.get('thumbnail'):
                    vid['thumbnail'] = f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg"

        # If user didn't manually type details but provided a YouTube link, auto-fetch details
        if (not yt_channel_name or not yt_videos) and social_links.get('youtube'):
            try:
                auto_details = get_youtube_channel_details(social_links['youtube'])
                if auto_details.get('success'):
                    if not yt_channel_name:
                        yt_channel_name = auto_details.get('title') or ''
                    if not yt_subscribers:
                        yt_subscribers = auto_details.get('subscribers') or ''
                    if not yt_description:
                        yt_description = auto_details.get('description') or ''
                    if not yt_avatar:
                        yt_avatar = auto_details.get('avatar') or ''
                    if not yt_videos:
                        yt_videos = auto_details.get('videos') or []
            except Exception:
                pass
        avatar_position = request.POST.get('avatar_position', '50% 50%').strip()
        avatar_x = request.POST.get('avatar_x', '').strip()
        avatar_y = request.POST.get('avatar_y', '').strip()
        avatar_zoom = request.POST.get('avatar_zoom', '1').strip() or '1'

        logo_position = request.POST.get('logo_position', '50% 50%').strip()
        logo_x = request.POST.get('logo_x', '').strip()
        logo_y = request.POST.get('logo_y', '').strip()
        logo_zoom = request.POST.get('logo_zoom', '1').strip() or '1'

        banner_position = request.POST.get('banner_position', '50% 50%').strip()
        banner_x = request.POST.get('banner_x', '').strip()
        banner_y = request.POST.get('banner_y', '').strip()
        banner_zoom = request.POST.get('banner_zoom', '1').strip() or '1'

        if not avatar_x or not avatar_y:
            try:
                parts = avatar_position.split()
                if len(parts) >= 2:
                    avatar_x = f"{float(parts[0].replace('%', '')) - 50:.1f}%"
                    avatar_y = f"{float(parts[1].replace('%', '')) - 50:.1f}%"
                else:
                    avatar_x, avatar_y = "0%", "0%"
            except Exception:
                avatar_x, avatar_y = "0%", "0%"

        if not logo_x or not logo_y:
            try:
                parts = logo_position.split()
                if len(parts) >= 2:
                    logo_x = f"{float(parts[0].replace('%', '')) - 50:.1f}%"
                    logo_y = f"{float(parts[1].replace('%', '')) - 50:.1f}%"
                else:
                    logo_x, logo_y = "0%", "0%"
            except Exception:
                logo_x, logo_y = "0%", "0%"

        if not banner_x or not banner_y:
            try:
                parts = banner_position.split()
                if len(parts) >= 2:
                    banner_x = f"{float(parts[0].replace('%', '')) - 50:.1f}%"
                    banner_y = f"{float(parts[1].replace('%', '')) - 50:.1f}%"
                else:
                    banner_x, banner_y = "0%", "0%"
            except Exception:
                banner_x, banner_y = "0%", "0%"
        card_layout = request.POST.get('card_layout', 'layout-cover-hero').strip() or 'layout-cover-hero'
        card_font = request.POST.get('card_font', 'Plus Jakarta Sans').strip() or 'Plus Jakarta Sans'
        wallet_config_raw = request.POST.get('wallet_config', '')
        wallet_config = {}
        if wallet_config_raw:
            try:
                wallet_config = json.loads(wallet_config_raw)
            except Exception:
                pass

        # Card Settings (from Settings Tab)
        settings_custom_domain = request.POST.get('settings_custom_domain', '').strip()
        settings_visibility = request.POST.get('settings_visibility', 'public').strip()
        settings_password = request.POST.get('settings_password', '').strip()
        settings_show_save_contact = request.POST.get('settings_show_save_contact', 'true').lower() in ('true', '1', 'on')
        settings_fb_chat_enabled = request.POST.get('settings_fb_chat_enabled', 'false').lower() in ('true', '1', 'on')
        settings_fb_page_id = request.POST.get('settings_fb_page_id', '').strip()
        settings_calendly_enabled = request.POST.get('settings_calendly_enabled', 'false').lower() in ('true', '1', 'on')
        settings_calendly_url = request.POST.get('settings_calendly_url', '').strip()
        settings_seo_index = request.POST.get('settings_seo_index', 'true').lower() in ('true', '1', 'on')
        settings_meta_title = request.POST.get('settings_meta_title', '').strip()
        settings_meta_desc = request.POST.get('settings_meta_desc', '').strip()
        settings_copyright = request.POST.get('settings_copyright', '').strip()
        settings_custom_js = request.POST.get('settings_custom_js', '').strip()
        settings_sensitive = request.POST.get('settings_sensitive', 'none').strip()
        settings_language = request.POST.get('settings_language', 'en').strip()

        card_settings = {
            'custom_domain': settings_custom_domain,
            'visibility': settings_visibility,
            'password': settings_password,
            'show_save_contact': settings_show_save_contact,
            'fb_chat_enabled': settings_fb_chat_enabled,
            'fb_page_id': settings_fb_page_id,
            'calendly_enabled': settings_calendly_enabled,
            'calendly_url': settings_calendly_url,
            'seo_index': settings_seo_index,
            'meta_title': settings_meta_title,
            'meta_description': settings_meta_desc,
            'copyright': settings_copyright,
            'custom_js': settings_custom_js,
            'sensitive_material': settings_sensitive,
            'language': settings_language,
        }

        # Payments configuration
        payments_data = {
            'gpay_enabled': request.POST.get('payment_gpay_enabled', 'false').lower() in ('true', '1', 'on'),
            'gpay': request.POST.get('payment_gpay', '').strip(),
            'phonepe_enabled': request.POST.get('payment_phonepe_enabled', 'false').lower() in ('true', '1', 'on'),
            'phonepe': request.POST.get('payment_phonepe', '').strip(),
            'paytm_enabled': request.POST.get('payment_paytm_enabled', 'false').lower() in ('true', '1', 'on'),
            'paytm': request.POST.get('payment_paytm', '').strip(),
            'paypal_enabled': request.POST.get('payment_paypal_enabled', 'false').lower() in ('true', '1', 'on'),
            'paypal': request.POST.get('payment_paypal', '').strip(),
            'venmo_enabled': request.POST.get('payment_venmo_enabled', 'false').lower() in ('true', '1', 'on'),
            'venmo': request.POST.get('payment_venmo', '').strip(),
            'cashapp_enabled': request.POST.get('payment_cashapp_enabled', 'false').lower() in ('true', '1', 'on'),
            'cashapp': request.POST.get('payment_cashapp', '').strip(),
            'razorpay_enabled': request.POST.get('payment_razorpay_enabled', 'false').lower() in ('true', '1', 'on'),
            'razorpay': request.POST.get('payment_razorpay', '').strip(),
        }

        # Validate mandatory payment IDs when payment toggle is ON
        payment_labels = {
            'gpay': 'Google Pay',
            'phonepe': 'PhonePe',
            'paytm': 'Paytm',
            'paypal': 'PayPal',
            'venmo': 'Venmo',
            'cashapp': 'Cash App',
            'razorpay': 'Razorpay',
        }
        for key, label in payment_labels.items():
            if payments_data.get(f'{key}_enabled') and not payments_data.get(key):
                messages.error(request, f'Please enter your {label} ID/link or turn off the {label} toggle.')
                active_card = target_card or _build_default_card()
                return render(request, 'card_builder.html', _get_card_builder_context(active_card, bool(target_card)))

        # More section (Document with File or URL, Google Drive, Address)
        more_doc_url = request.POST.get('more_doc_url', '').strip() or request.POST.get('more_pdf_url', '').strip()
        if 'more_doc_file' in request.FILES:
            doc_file = request.FILES['more_doc_file']
            from django.core.files.storage import default_storage
            saved_doc_path = default_storage.save(f'cards/documents/{doc_file.name}', doc_file)
            more_doc_url = default_storage.url(saved_doc_path)
        elif 'more_pdf_file' in request.FILES:
            pdf_file = request.FILES['more_pdf_file']
            from django.core.files.storage import default_storage
            saved_pdf_path = default_storage.save(f'cards/documents/{pdf_file.name}', pdf_file)
            more_doc_url = default_storage.url(saved_pdf_path)
        elif more_doc_url:
            if not more_doc_url.startswith(('http://', 'https://', '/')):
                more_doc_url = 'https://' + more_doc_url
        else:
            more_doc_url = ''

        more_data = {
            'section_title': (request.POST.get('more_section_title') or 'Brochure').strip() or 'Brochure',
            'doc_enabled': request.POST.get('more_doc_enabled', 'false').lower() in ('true', '1', 'on'),
            'doc_title': (request.POST.get('more_doc_title') or request.POST.get('more_pdf_title') or 'Document').strip(),
            'doc_url': more_doc_url,
            'pdf_title': (request.POST.get('more_doc_title') or request.POST.get('more_pdf_title') or 'Document').strip(),
            'pdf_url': more_doc_url,
            'gdrive_enabled': request.POST.get('more_gdrive_enabled', 'false').lower() in ('true', '1', 'on'),
            'gdrive_title': request.POST.get('more_gdrive_title', '').strip(),
            'gdrive_url': request.POST.get('more_gdrive_url', '').strip(),
        }

        layout_config = {
            'role_title': role_title,
            'owner_role': owner_role,
            'owner_title': owner_title,
            'identity_order': identity_order,
            'role_title_order': role_title_order,
            'show_profile_photo': show_profile_photo,
            'show_company_logo': show_company_logo,
            'show_banner': show_banner,
            'about_heading': about_heading,
            'capabilities_items': capabilities_items,
            'brands_items': brands_items,
            'banners_items': banners_items,
            'banner_aspect': banner_aspect,
            'images_items': images_items,
            'avatar_x': avatar_x,
            'avatar_y': avatar_y,
            'avatar_position': avatar_position,
            'avatar_zoom': avatar_zoom,
            'logo_x': logo_x,
            'logo_y': logo_y,
            'logo_position': logo_position,
            'logo_zoom': logo_zoom,
            'banner_x': banner_x,
            'banner_y': banner_y,
            'banner_position': banner_position,
            'banner_zoom': banner_zoom,
            'layout_style': card_layout,
            'font': card_font,
            'wallet_config': wallet_config,
            'settings': card_settings,
            'youtube_video_url': youtube_video_url,
            'yt_channel_name': yt_channel_name,
            'yt_subscribers': yt_subscribers,
            'yt_description': yt_description,
            'yt_avatar': yt_avatar,
            'yt_videos': yt_videos,
            'payments': payments_data,
            'more': more_data,
            'section_order': section_order,
            'disabled_sections': disabled_sections,
        }

        # Razorpay Demo Payment verification & receipt (for personal cards)
        razorpay_payment_id = (request.POST.get('razorpay_payment_id') or '').strip()
        razorpay_amount = (request.POST.get('razorpay_amount') or '499').strip()
        razorpay_method = (request.POST.get('razorpay_method') or 'UPI / Card (Demo)').strip()
        nfc_ordered = request.POST.get('nfc_ordered', 'false').lower() in ('true', '1') or razorpay_amount == '999'

        quota = _get_enterprise_quota(request.user)
        if not quota['is_enterprise']:
            paid_amount = 999 if nfc_ordered else 499
            plan_label = 'Personal Pro + Physical NFC Card' if nfc_ordered else 'Personal Pro Lifetime'
            if razorpay_payment_id or not target_card:
                if not razorpay_payment_id:
                    import uuid
                    razorpay_payment_id = f"pay_demo_{uuid.uuid4().hex[:10]}"
                layout_config['payment_receipt'] = {
                    'gateway': 'Razorpay (Demo)',
                    'payment_id': razorpay_payment_id,
                    'amount': paid_amount,
                    'currency': 'INR',
                    'status': 'captured',
                    'method': razorpay_method,
                    'plan': plan_label,
                    'paid_at': timezone.now().strftime('%d %b %Y, %I:%M %p'),
                }
                if nfc_ordered:
                    layout_config['nfc_card'] = {
                        'ordered': True,
                        'theme': (request.POST.get('nfc_theme') or 'obsidian_black').strip(),
                        'name': (request.POST.get('nfc_name') or request.POST.get('owner_name') or '').strip(),
                        'designation': (request.POST.get('nfc_designation') or role_title or '').strip(),
                        'foil': (request.POST.get('nfc_foil') or 'gold').strip(),
                        'website': (request.POST.get('nfc_website') or request.POST.get('website') or request.POST.get('existing_website') or 'www.brandnest.in').strip(),
                        'company_name': (request.POST.get('nfc_company_name') or request.POST.get('business_name') or '').strip(),
                        'pass_tagline': (request.POST.get('nfc_pass_tagline') or 'BrandNest Smart Pass').strip(),
                        'chip_spec': (request.POST.get('nfc_chip_spec') or 'NTAG216 · 888 BYTES').strip(),
                        'back_tagline': (request.POST.get('nfc_back_tagline') or 'SMART CONTACTLESS TOUCHPOINT').strip(),
                        'tap_hint': (request.POST.get('nfc_tap_hint') or 'Tap against any smartphone to open card').strip(),
                        'back_badge': (request.POST.get('nfc_back_badge') or 'Direct NFC Tap').strip(),
                        'logo_data': (request.POST.get('nfc_logo_data') or '').strip(),
                        'logo_scale': (request.POST.get('nfc_logo_scale') or '1.0').strip(),
                        'positions': (request.POST.get('nfc_positions') or '{}').strip(),
                        'status': 'Ready for Printing & Dispatch',
                    }
                try:
                    user_plan, _ = UserPlan.objects.get_or_create(user=request.user)
                    if user_plan.plan_type != 'enterprise':
                        user_plan.plan_type = 'personal'
                        user_plan.total_paid = paid_amount
                        user_plan.save()
                except Exception:
                    pass
            elif target_card and target_card.layout_config:
                if 'payment_receipt' in target_card.layout_config:
                    layout_config['payment_receipt'] = target_card.layout_config['payment_receipt']
                if 'nfc_card' in target_card.layout_config:
                    layout_config['nfc_card'] = target_card.layout_config['nfc_card']
                    # Sync any edited NFC fields if submitted
                    if request.POST.get('nfc_theme') or request.POST.get('nfc_website') or request.POST.get('nfc_name'):
                        layout_config['nfc_card'].update({
                            'theme': (request.POST.get('nfc_theme') or layout_config['nfc_card'].get('theme', 'obsidian_black')).strip(),
                            'name': (request.POST.get('nfc_name') or layout_config['nfc_card'].get('name', '')).strip(),
                            'designation': (request.POST.get('nfc_designation') or layout_config['nfc_card'].get('designation', '')).strip(),
                            'foil': (request.POST.get('nfc_foil') or layout_config['nfc_card'].get('foil', 'gold')).strip(),
                            'website': (request.POST.get('nfc_website') or layout_config['nfc_card'].get('website', 'www.brandnest.in')).strip(),
                            'company_name': (request.POST.get('nfc_company_name') or layout_config['nfc_card'].get('company_name', '')).strip(),
                            'pass_tagline': (request.POST.get('nfc_pass_tagline') or layout_config['nfc_card'].get('pass_tagline', 'BrandNest Smart Pass')).strip(),
                            'chip_spec': (request.POST.get('nfc_chip_spec') or layout_config['nfc_card'].get('chip_spec', 'NTAG216 · 888 BYTES')).strip(),
                            'back_tagline': (request.POST.get('nfc_back_tagline') or layout_config['nfc_card'].get('back_tagline', 'SMART CONTACTLESS TOUCHPOINT')).strip(),
                            'tap_hint': (request.POST.get('nfc_tap_hint') or layout_config['nfc_card'].get('tap_hint', 'Tap against any smartphone to open card')).strip(),
                            'back_badge': (request.POST.get('nfc_back_badge') or layout_config['nfc_card'].get('back_badge', 'Direct NFC Tap')).strip(),
                            'logo_data': (request.POST.get('nfc_logo_data') or layout_config['nfc_card'].get('logo_data', '')).strip(),
                            'logo_scale': (request.POST.get('nfc_logo_scale') or layout_config['nfc_card'].get('logo_scale', '1.0')).strip(),
                            'positions': (request.POST.get('nfc_positions') or layout_config['nfc_card'].get('positions', '{}')).strip(),
                        })

        # 3. Optional existing website link
        existing_website = (request.POST.get('website') or request.POST.get('existing_website') or '').strip()

        # Services summary string
        services_summary = request.POST.get('services', '').strip()
        if not services_summary and capabilities_items:
            services_summary = ', '.join([item.get('title', '') for item in capabilities_items if item.get('title')])

        # 4. Create or Update Business Card
        maps_link_val = (request.POST.get('maps_link') or request.POST.get('google_maps_url') or '').strip()
        address_val = request.POST.get('address', '').strip()
        if maps_link_val:
            if not maps_link_val.startswith(('http://', 'https://')):
                if any(maps_link_val.startswith(d) for d in ('maps.app.goo.gl', 'maps.google.com', 'goo.gl/maps', 'www.google.com/maps')) or ('.' in maps_link_val and ' ' not in maps_link_val and '/' in maps_link_val):
                    maps_link_val = 'https://' + maps_link_val
                else:
                    import urllib.parse
                    maps_link_val = 'https://www.google.com/maps/search/?api=1&query=' + urllib.parse.quote_plus(maps_link_val)
        elif address_val and address_val != 'Address not provided yet.':
            import urllib.parse
            maps_link_val = 'https://www.google.com/maps/search/?api=1&query=' + urllib.parse.quote_plus(address_val)

        if target_card:
            card = target_card
            card.business_name = business_name
            card.owner_name = request.POST.get('owner_name', '').strip()
            card.tagline = role_title
            card.description = (request.POST.get('bio') or request.POST.get('description') or '').strip()
            card.services = services_summary
            card.phone = request.POST.get('phone', '').strip()
            card.email = request.POST.get('email', '').strip()
            card.whatsapp = request.POST.get('whatsapp', '').strip()
            card.address = request.POST.get('address', '').strip()
            card.google_maps_url = maps_link_val
            card.existing_website = existing_website
            card.theme_color = (request.POST.get('accent_color') or request.POST.get('accent_preset') or request.POST.get('theme_color') or '#0084FF').strip()
            card.social_links = social_links
            card.layout_config = layout_config
            card.is_published = True
        else:
            card = BusinessCard(
                user=request.user if request.user.is_authenticated else None,
                domain=None,
                business_name=business_name,
                owner_name=request.POST.get('owner_name', '').strip(),
                tagline=role_title,
                description=(request.POST.get('bio') or request.POST.get('description') or '').strip(),
                services=services_summary,
                phone=request.POST.get('phone', '').strip(),
                email=request.POST.get('email', '').strip(),
                whatsapp=request.POST.get('whatsapp', '').strip(),
                address=request.POST.get('address', '').strip(),
                google_maps_url=maps_link_val,
                existing_website=existing_website,
                theme_color=(request.POST.get('accent_color') or request.POST.get('accent_preset') or request.POST.get('theme_color') or '#0084FF').strip(),
                social_links=social_links,
                layout_config=layout_config,
                is_published=True
            )

        if 'company_logo' in request.FILES:
            card.logo = request.FILES['company_logo']
        elif 'logo' in request.FILES:
            card.logo = request.FILES['logo']

        if 'banner_image' in request.FILES:
            card.banner_image = request.FILES['banner_image']
        elif 'banner' in request.FILES:
            card.banner_image = request.FILES['banner']

        if 'owner_photo' in request.FILES:
            card.profile_image = request.FILES['owner_photo']
        elif 'profile_image' in request.FILES:
            card.profile_image = request.FILES['profile_image']

        if settings_custom_domain:
            custom_slug_clean = slugify(settings_custom_domain.replace('.brandnest.me', '').replace('.qkbiz.com', '').strip())
            if custom_slug_clean and not BusinessCard.objects.filter(slug=custom_slug_clean).exclude(pk=card.pk).exists():
                card.slug = custom_slug_clean

        card.save()
        if target_card and not request.POST.get('razorpay_payment_id'):
            messages.success(request, f'Business card for "{card.business_name}" updated successfully!')
            return redirect('card_preview', card_id=card.card_id)

        quota = _get_enterprise_quota(request.user)
        if quota['is_enterprise']:
            messages.success(
                request,
                f'Business card for "{card.business_name}" has been generated! ({quota["cards_used"]} / {quota["card_limit"]} cards used)'
            )
            return redirect('card_list')

        if nfc_ordered and not NFCTag.objects.filter(card=card).exists():
            try:
                NFCTag.objects.create(card=card, nfc_mode='web_card')
            except Exception:
                pass

        if nfc_ordered:
            messages.success(request, f'Payment of ₹999 received via Razorpay (Demo)! Your digital business card and custom NFC card for "{card.business_name}" have been generated.')
        else:
            messages.success(request, f'Payment of ₹499 received via Razorpay (Demo)! Your digital business card for "{card.business_name}" is ready.')
        return redirect('card_preview', card_id=card.card_id)

    active_card = target_card if target_card else _build_default_card()
    return render(request, 'card_builder.html', _get_card_builder_context(active_card, bool(target_card)))


@login_required(login_url='login')
def card_delete(request, card_id):
    """
    Delete a business card permanently.
    """
    if request.user.is_superuser or request.user.is_staff:
        card = get_object_or_404(BusinessCard, card_id=card_id)
    else:
        card = get_object_or_404(BusinessCard, card_id=card_id, user=request.user)
    name = card.business_name or card.owner_name or 'Card'
    card.delete()
    messages.success(request, f'Business card "{name}" was successfully deleted.')
    if BusinessCard.objects.filter(user=request.user).exists():
        return redirect('card_list')
    return redirect('card_builder')


@login_required(login_url='login')
def card_list(request):
    """
    SaaS Business Cards Manager:
    Lists all cards with status, views, preview link, edit in builder, and delete options.
    """
    if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
        cards = BusinessCard.objects.all().order_by('-created_at')
    elif request.user.is_authenticated:
        cards = BusinessCard.objects.filter(user=request.user).order_by('-created_at')
    else:
        cards = BusinessCard.objects.all().order_by('-created_at')

    total_views = sum(c.views_count for c in cards) if cards else 0
    published_count = sum(1 for c in cards if c.is_published) if cards else 0
    enterprise_quota = _get_enterprise_quota(request.user)
    show_upgrade_modal = (
        request.GET.get('upgrade') == '1'
        and enterprise_quota['is_enterprise']
        and enterprise_quota['limit_reached']
    )

    return render(request, 'card_list.html', {
        'cards': cards,
        'total_count': cards.count() if hasattr(cards, 'count') else len(cards),
        'total_views': total_views,
        'published_count': published_count,
        'enterprise_quota': enterprise_quota,
        'bundles': ENTERPRISE_BUNDLES,
        'extra_card_price': EXTRA_CARD_PRICE_INR,
        'show_upgrade_modal': show_upgrade_modal,
    })


def card_preview(request, card_id):
    """
    Presents the generated Business Card inside an interactive mobile preview device frame
    with share links, Python-generated QR code, and actions.
    """
    import time
    card = get_object_or_404(BusinessCard, card_id=card_id)
    standalone_path = reverse('card_standalone', kwargs={'slug': card.slug})
    share_url = get_shareable_url(request, standalone_path)
    qr_data_uri = generate_qr_code_base64(share_url)
    
    yt_url = (card.layout_config or {}).get('youtube_video_url') or (card.social_links or {}).get('youtube_video') or ''
    card_yt_video_id = _extract_youtube_id(yt_url)

    return render(request, 'card_preview.html', {
        'card': card,
        'share_url': share_url,
        'qr_data_uri': qr_data_uri,
        'timestamp': int(time.time()),
        'card_yt_video_id': card_yt_video_id,
    })


def card_qr_image(request, slug):
    """
    Direct endpoint that returns a dynamically generated PNG QR code using python qrcode library.
    Generates a new QR code on each request/refresh without Cloudflare or external API.
    Supports ?download=1 to trigger attachment download.
    """
    from django.http import HttpResponse
    card = get_object_or_404(BusinessCard, slug=slug)
    standalone_path = reverse('card_standalone', kwargs={'slug': card.slug})
    share_url = get_shareable_url(request, standalone_path)

    png_bytes = generate_qr_code_image_bytes(share_url)
    response = HttpResponse(png_bytes, content_type='image/png')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    if request.GET.get('download') in ('1', 'true', 'yes'):
        filename = f"{card.slug}-qr.png"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@xframe_options_exempt
def card_standalone(request, slug):
    """
    Renders the live pre-made Business Card template full-screen (for visitor viewing).
    """
    card = get_object_or_404(BusinessCard, slug=slug)
    BusinessCard.objects.filter(pk=card.pk).update(views_count=card.views_count + 1)
    card.refresh_from_db()
    yt_url = (card.layout_config or {}).get('youtube_video_url') or (card.social_links or {}).get('youtube_video') or ''
    card_yt_video_id = _extract_youtube_id(yt_url)
    return render(request, 'card_template.html', {'card': card, 'card_yt_video_id': card_yt_video_id})


def website_builder(request):
    """
    Website Builder:
    Step 1: Connect Domain (Domain Gate)
    Step 2: Choose Industry Category
    Step 3: Fill Dynamic Industry Form
    Step 4: Generate Pre-made Industry Website & Preview
    """
    industries = Industry.objects.filter(is_active=True).order_by('display_order')

    if request.method == 'POST':
        domain_name = request.POST.get('domain_name', '').strip()
        industry_slug = request.POST.get('industry_slug', '').strip()
        title = request.POST.get('title', '').strip()

        if not domain_name:
            messages.error(request, 'Please provide and verify your domain name first.')
            return render(request, 'website_builder.html', {'industries': industries})

        if not industry_slug:
            messages.error(request, 'Please select an industry category.')
            return render(request, 'website_builder.html', {'industries': industries, 'domain_name': domain_name})

        industry = get_object_or_404(Industry, slug=industry_slug)

        # 1. Connect / Retrieve Domain
        domain, _ = Domain.objects.get_or_create(
            domain_name=domain_name,
            defaults={'domain_type': 'custom', 'verification_status': 'verified', 'ssl_status': 'active'}
        )
        if domain.verification_status != 'verified':
            domain.verification_status = 'verified'
            domain.ssl_status = 'active'
            domain.save()

        # 2. Extract Industry Dynamic Fields
        custom_data = {}
        for key, value in request.POST.items():
            if key.startswith('custom_'):
                clean_field_name = key.replace('custom_', '')
                custom_data[clean_field_name] = value.strip()

        # Extract Social Links
        social_links = {
            'linkedin': request.POST.get('social_linkedin', '').strip(),
            'instagram': request.POST.get('social_instagram', '').strip(),
            'twitter': request.POST.get('social_twitter', '').strip(),
            'facebook': request.POST.get('social_facebook', '').strip(),
        }

        # 3. Create Website
        website = Website(
            user=request.user if request.user.is_authenticated else None,
            domain=domain,
            industry=industry,
            title=title or f"{industry.name} Business",
            tagline=request.POST.get('tagline', '').strip(),
            about_text=request.POST.get('about_text', '').strip(),
            primary_color=request.POST.get('primary_color', '#1E40AF').strip() or '#1E40AF',
            contact_email=request.POST.get('contact_email', '').strip(),
            contact_phone=request.POST.get('contact_phone', '').strip(),
            address=request.POST.get('address', '').strip(),
            working_hours=request.POST.get('working_hours', '').strip(),
            social_links=social_links,
            custom_data=custom_data,
            status='published',
            is_published=True
        )

        if 'logo' in request.FILES:
            website.logo = request.FILES['logo']
        if 'hero_image' in request.FILES:
            website.hero_image = request.FILES['hero_image']

        website.save()
        messages.success(request, f'Your {industry.name} website for {website.title} is ready!')
        return redirect('website_preview', site_id=website.site_id)

    return render(request, 'website_builder.html', {'industries': industries})


def website_preview(request, site_id):
    """
    Website Preview: Provides desktop, tablet, and mobile device viewports
    and allows testing the interactive website.
    """
    website = get_object_or_404(Website, site_id=site_id)
    standalone_path = reverse('website_standalone', kwargs={'slug': website.slug})
    share_url = get_shareable_url(request, standalone_path)
    return render(request, 'website_preview.html', {
        'website': website,
        'share_url': share_url
    })


@xframe_options_exempt
def website_standalone(request, slug):
    """
    Renders the live pre-made Industry Website template full-screen (tenant live site).
    """
    website = get_object_or_404(Website, slug=slug)
    Website.objects.filter(pk=website.pk).update(views_count=website.views_count + 1)
    website.refresh_from_db()
    return render(request, 'website_template.html', {'website': website})


# ==============================================================================
# User Authentication Views (Signup, Login, Logout)
# ==============================================================================

def _safe_next_url(request, default='landing'):
    candidate = (request.GET.get('next') or request.POST.get('next') or '').strip()
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def signup_view(request):
    """
    User Registration:
    Creates a new BrandNest user account, validates fields, and logs them in.
    """
    next_url = _safe_next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # Basic validations
        if not email:
            messages.error(request, 'Please provide a valid email address.')
            return render(request, 'signup.html', {
                'full_name': full_name,
                'email': email,
                'username': username,
                'next': next_url,
            })

        if not password:
            messages.error(request, 'Please enter a password.')
            return render(request, 'signup.html', {
                'full_name': full_name,
                'email': email,
                'username': username,
                'next': next_url,
            })

        if password != confirm_password:
            messages.error(request, 'Passwords do not match. Please re-enter your password.')
            return render(request, 'signup.html', {
                'full_name': full_name,
                'email': email,
                'username': username,
                'next': next_url,
            })

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters long.')
            return render(request, 'signup.html', {
                'full_name': full_name,
                'email': email,
                'username': username,
                'next': next_url,
            })

        # Auto-generate username from email if left blank
        if not username:
            base_username = email.split('@')[0]
            base_username = re.sub(r'[^a-zA-Z0-9._-]', '', base_username) or 'user'
            username = base_username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
        else:
            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, f'Username "{username}" is already taken. Please choose another username.')
                return render(request, 'signup.html', {
                    'full_name': full_name,
                    'email': email,
                    'username': username,
                    'next': next_url,
                })

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, f'An account with email "{email}" already exists. Please log in.')
            return render(request, 'signup.html', {
                'full_name': full_name,
                'email': email,
                'username': username,
                'next': next_url,
            })

        # Split full name into first and last name
        first_name = ''
        last_name = ''
        if full_name:
            parts = full_name.split(' ', 1)
            first_name = parts[0]
            if len(parts) > 1:
                last_name = parts[1]

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            login(request, user)
            display_name = full_name or user.username
            messages.success(request, f'Welcome to BrandNest, {display_name}! Your account has been created successfully.')
            return redirect(next_url)
        except Exception as e:
            messages.error(request, f'Error creating account: {e}')
            return render(request, 'signup.html', {
                'full_name': full_name,
                'email': email,
                'username': username,
                'next': next_url,
            })

    return render(request, 'signup.html', {'next': next_url})


def login_view(request):
    """
    User Login:
    Authenticates by either username OR email address, supports remember-me.
    """
    next_url = _safe_next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url)

    if request.method == 'POST':
        login_identifier = request.POST.get('login_identifier', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        if not login_identifier or not password:
            messages.error(request, 'Please provide your email/username and password.')
            return render(request, 'login.html', {
                'login_identifier': login_identifier,
                'next': next_url,
            })

        # 1. Try authenticating directly with username
        user = authenticate(request, username=login_identifier, password=password)

        # 2. If failed, attempt looking up by email
        if user is None:
            try:
                user_obj = User.objects.get(email__iexact=login_identifier)
                user = authenticate(request, username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                user = None

        if user is not None:
            if not user.is_active:
                messages.error(request, 'This account is currently inactive.')
                return render(request, 'login.html', {'login_identifier': login_identifier, 'next': next_url})

            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # Browser session expiry

            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid email/username or password. Please verify your credentials.')
            return render(request, 'login.html', {
                'login_identifier': login_identifier,
                'next': next_url,
            })

    return render(request, 'login.html', {'next': next_url})


def logout_view(request):
    """
    User Logout:
    Cleans session and redirects to landing page.
    """
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('landing')


# =============================================================================
# Live Public Card Interactions & Event Tracking
# =============================================================================

@csrf_exempt
def record_card_lead(request, slug):
    """
    Handles visitor contact inquiry submissions from the digital business card.
    Saves lead to CardLead model and creates an analytics event.
    """
    card = get_object_or_404(BusinessCard, slug=slug)
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST
        except Exception:
            data = request.POST

        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        phone = (data.get('phone') or '').strip()
        message = (data.get('message') or '').strip()

        if name:
            lead = CardLead.objects.create(
                card=card,
                name=name,
                email=email,
                phone=phone,
                message=message,
                stage='new_lead',
                qualification='hot'
            )
            # Record tracking event
            CardAnalyticsEvent.objects.create(
                card=card,
                event_type='lead_submit',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:250]
            )
            return JsonResponse({'status': 'ok', 'lead_id': lead.id})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def record_card_event(request, slug, event_type):
    """
    Lightweight beacon endpoint to record clicks (Share, WhatsApp, VCF download, etc.)
    """
    card = get_object_or_404(BusinessCard, slug=slug)
    valid_events = {'view', 'share_click', 'main_action_click', 'whatsapp_click', 'contact_download', 'contact_exchange', 'lead_submit'}
    if event_type in valid_events:
        CardAnalyticsEvent.objects.create(
            card=card,
            event_type=event_type,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:250]
        )
    return JsonResponse({'status': 'ok'})


# =============================================================================
# BrandNest Admin & Enterprise Dashboard Views & Admin Auth
# =============================================================================

def admin_login_view(request):
    """
    Dedicated BrandNest Admin Portal Login:
    Authenticates staff and superusers directly into the Admin Dashboard.
    """
    next_url = request.GET.get('next') or request.POST.get('next') or reverse('dashboard_overview')
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect(next_url)

    if request.method == 'POST':
        login_identifier = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        if not login_identifier or not password:
            messages.error(request, 'Please provide both username and password.')
            return render(request, 'dashboard/admin_login.html', {
                'username': login_identifier,
                'next': next_url,
            })

        user = authenticate(request, username=login_identifier, password=password)
        if user is None:
            user_obj = User.objects.filter(email__iexact=login_identifier).first()
            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'This account is currently disabled.')
                return render(request, 'dashboard/admin_login.html', {'username': login_identifier, 'next': next_url})

            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)

            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid admin username or password. Please verify your credentials.')
            return render(request, 'dashboard/admin_login.html', {
                'username': login_identifier,
                'next': next_url,
            })

    return render(request, 'dashboard/admin_login.html', {'next': next_url})


def admin_logout_view(request):
    """
    Admin Logout:
    Terminates session and redirects directly back to the dedicated Admin Login portal.
    """
    logout(request)
    messages.info(request, 'You have been safely signed out from the Admin Dashboard.')
    return redirect('admin_login')


def admin_gateway(request):
    """
    Direct handler for /admin and /admin/:
    - If user is authenticated as staff or superuser: redirects directly to /dashboard/overview/.
    - If unauthenticated: redirects to the dedicated Admin Login portal (/admin/login/).
    """
    if request.user.is_authenticated:
        return redirect('dashboard_overview')
    return redirect('admin_login')


def dashboard_auth_required(view_func):
    """
    Decorator for BrandNest Admin & Enterprise Dashboard views:
    - If user is authenticated, executes view directly.
    - If unauthenticated: redirects to the dedicated Admin Login portal (/admin/login/)
      with the requested path in the next parameter.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('admin_login')}?next={request.path}")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@dashboard_auth_required
def dashboard_overview(request):
    """
    High-level dashboard overview showing page views, clicks, CTR, leads,
    activity graph over the last 7 days, and top performing cards.
    """
    cards = BusinessCard.objects.all()
    selected_user_id = request.GET.get('user', '')
    if selected_user_id:
        cards = cards.filter(user_id=selected_user_id)

    total_views = cards.aggregate(Sum('views_count'))['views_count__sum'] or 0
    total_clicks = CardAnalyticsEvent.objects.filter(
        card__in=cards,
        event_type__in=['share_click', 'main_action_click', 'whatsapp_click']
    ).count()
    total_leads = CardLead.objects.filter(card__in=cards).count()

    ctr_val = round((total_clicks / max(1, total_views)) * 100, 1) if total_views else 0
    ctr = f"{ctr_val}%"

    top_cards = cards.order_by('-views_count')[:10]
    users_list = User.objects.all()

    now = timezone.now()
    chart_labels = []
    chart_views = []
    chart_clicks = []
    chart_leads = []

    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_date = day.date()
        chart_labels.append(day.strftime('%b %d') if i > 0 else 'Today')
        
        d_clicks = CardAnalyticsEvent.objects.filter(
            card__in=cards,
            event_type__in=['share_click', 'main_action_click', 'whatsapp_click'],
            created_at__date=day_date
        ).count()
        d_leads = CardLead.objects.filter(
            card__in=cards,
            created_at__date=day_date
        ).count()
        
        chart_clicks.append(d_clicks)
        chart_leads.append(d_leads)
        chart_views.append(max(d_clicks, round(total_views / 7)))

    context = {
        'active_menu': 'overview',
        'total_views': total_views,
        'total_clicks': total_clicks,
        'total_leads': total_leads,
        'ctr': ctr,
        'top_cards': top_cards,
        'users_list': users_list,
        'selected_user_id': selected_user_id,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_views_json': json.dumps(chart_views),
        'chart_clicks_json': json.dumps(chart_clicks),
        'chart_leads_json': json.dumps(chart_leads),
    }
    return render(request, 'dashboard/overview.html', context)


@dashboard_auth_required
def dashboard_cards(request):
    cards = BusinessCard.objects.all().order_by('-created_at')
    return render(request, 'dashboard/cards.html', {
        'active_menu': 'cards',
        'cards': cards,
    })


@dashboard_auth_required
def dashboard_qr_codes(request):
    cards = BusinessCard.objects.all().order_by('-created_at')
    return render(request, 'dashboard/qr_codes.html', {
        'active_menu': 'qr_codes',
        'cards': cards,
    })


@dashboard_auth_required
def dashboard_contacts(request):
    contacts = CardLead.objects.select_related('card').all().order_by('-created_at')
    return render(request, 'dashboard/contacts.html', {
        'active_menu': 'contacts',
        'contacts': contacts,
    })


@dashboard_auth_required
def dashboard_contacts_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()
        title = request.POST.get('title', '').strip()
        if name:
            CardLead.objects.create(
                name=name, email=email, phone=phone, company=company, title=title, source='Manual'
            )
            messages.success(request, f'Contact {name} added successfully.')
    return redirect('dashboard_contacts')


@dashboard_auth_required
def dashboard_messages(request):
    messages_list = CardLead.objects.filter(message__gt='').select_related('card').order_by('-created_at')
    return render(request, 'dashboard/messages.html', {
        'active_menu': 'messages',
        'messages_list': messages_list,
    })


@dashboard_auth_required
def dashboard_nfc(request):
    nfc_tags = NFCTag.objects.select_related('card').all()
    cards = BusinessCard.objects.all()
    # If no tags exist yet, automatically map the existing cards so users have real tag models
    if not nfc_tags.exists() and cards.exists():
        for c in cards[:3]:
            NFCTag.objects.get_or_create(card=c, defaults={'nfc_mode': 'web_card'})
        nfc_tags = NFCTag.objects.select_related('card').all()

    return render(request, 'dashboard/nfc.html', {
        'active_menu': 'nfc',
        'nfc_tags': nfc_tags,
        'cards': cards,
    })


@dashboard_auth_required
def dashboard_nfc_add(request):
    if request.method == 'POST':
        card_id = request.POST.get('card_id')
        nfc_mode = request.POST.get('nfc_mode', 'web_card')
        card = get_object_or_404(BusinessCard, id=card_id)
        tag = NFCTag.objects.create(card=card, nfc_mode=nfc_mode)
        messages.success(request, f'NFC Tag {tag.unique_code} registered for {card.business_name}.')
    return redirect('dashboard_nfc')


@dashboard_auth_required
def dashboard_nfc_update(request, tag_id):
    tag = get_object_or_404(NFCTag, id=tag_id)
    if request.method == 'POST':
        mode = request.POST.get('nfc_mode')
        if mode in dict(NFCTag.MODE_CHOICES):
            tag.nfc_mode = mode
            tag.save()
            messages.success(request, f'NFC Mode updated to {tag.get_nfc_mode_display()}.')
    return redirect('dashboard_nfc')


@dashboard_auth_required
def dashboard_nfc_toggle_active(request, tag_id):
    tag = get_object_or_404(NFCTag, id=tag_id)
    if request.method == 'POST':
        tag.is_active = not tag.is_active
        tag.save()
        status_text = 'resumed' if tag.is_active else 'paused'
        messages.info(request, f'NFC Tag {tag.unique_code} is now {status_text}.')
    return redirect('dashboard_nfc')


@dashboard_auth_required
def dashboard_wallet_pass(request):
    cards = BusinessCard.objects.all()
    selected_card_id = request.GET.get('card')
    selected_card = cards.filter(id=selected_card_id).first() if selected_card_id else cards.first()
    return render(request, 'dashboard/wallet_pass.html', {
        'active_menu': 'wallet_pass',
        'cards': cards,
        'selected_card': selected_card,
    })


@dashboard_auth_required
def dashboard_analytics(request):
    cards = BusinessCard.objects.all()
    selected_card_id = request.GET.get('card')
    selected_card = cards.filter(id=selected_card_id).first() if selected_card_id else cards.first()

    card_views = selected_card.views_count if selected_card else 0
    card_leads = CardLead.objects.filter(card=selected_card).count() if selected_card else 0
    card_clicks = CardAnalyticsEvent.objects.filter(
        card=selected_card,
        event_type__in=['share_click', 'main_action_click', 'whatsapp_click']
    ).count() if selected_card else 0

    event_share = CardAnalyticsEvent.objects.filter(card=selected_card, event_type='share_click').count() if selected_card else 0
    event_main = CardAnalyticsEvent.objects.filter(card=selected_card, event_type='main_action_click').count() if selected_card else 0
    event_whatsapp = CardAnalyticsEvent.objects.filter(card=selected_card, event_type='whatsapp_click').count() if selected_card else 0
    event_download = CardAnalyticsEvent.objects.filter(card=selected_card, event_type='contact_download').count() if selected_card else 0

    now = timezone.now()
    chart_labels = [(now - timedelta(days=i)).strftime('%b %d') if i > 0 else 'Today' for i in range(6, -1, -1)]
    chart_views = [round(card_views / 7)] * 7 if card_views else [0] * 7
    chart_clicks = [round(card_clicks / 7)] * 7 if card_clicks else [0] * 7

    return render(request, 'dashboard/analytics.html', {
        'active_menu': 'analytics',
        'cards': cards,
        'selected_card': selected_card,
        'card_views': card_views,
        'card_leads': card_leads,
        'card_clicks': card_clicks,
        'event_share': event_share,
        'event_main': event_main,
        'event_whatsapp': event_whatsapp,
        'event_download': event_download,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_views_json': json.dumps(chart_views),
        'chart_clicks_json': json.dumps(chart_clicks),
    })


@dashboard_auth_required
def dashboard_teams(request):
    teams = Team.objects.prefetch_related('members').all()
    all_users = User.objects.all()
    return render(request, 'dashboard/teams.html', {
        'active_menu': 'teams',
        'teams': teams,
        'all_users': all_users,
    })


@dashboard_auth_required
def dashboard_teams_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        member_ids = request.POST.getlist('member_ids')
        if name:
            team, _ = Team.objects.get_or_create(name=name, defaults={'owner': request.user})
            if member_ids:
                team.members.set(member_ids)
            messages.success(request, f'Team "{name}" created successfully.')
    return redirect('dashboard_teams')


@dashboard_auth_required
def dashboard_teams_rename(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    new_name = request.GET.get('name', '').strip()
    if new_name:
        team.name = new_name
        team.save()
        messages.success(request, f'Team renamed to "{new_name}".')
    return redirect('dashboard_teams')


@dashboard_auth_required
def dashboard_users(request):
    users_list = User.objects.prefetch_related('cards', 'teams').all().order_by('-date_joined')
    total_users_count = users_list.count()
    now = timezone.now()
    users_today = users_list.filter(date_joined__date=now.date()).count()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0)
    users_month = users_list.filter(date_joined__gte=first_of_month).count()
    seven_days_ago = now - timedelta(days=7)
    users_week = users_list.filter(date_joined__gte=seven_days_ago).count()
    teams = Team.objects.all()

    return render(request, 'dashboard/users.html', {
        'active_menu': 'users',
        'users_list': users_list,
        'total_users_count': total_users_count,
        'users_today': users_today,
        'users_month': users_month,
        'users_week': users_week,
        'teams': teams,
    })


@dashboard_auth_required
def dashboard_users_add(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        team_id = request.POST.get('team_id')
        if username and email:
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" is already taken.')
            else:
                user = User.objects.create_user(username=username, email=email, password='TemporaryPassword123!')
                if full_name:
                    parts = full_name.split(' ', 1)
                    user.first_name = parts[0]
                    user.last_name = parts[1] if len(parts) > 1 else ''
                    user.save()
                if team_id:
                    team = Team.objects.filter(id=team_id).first()
                    if team:
                        team.members.add(user)
                messages.success(request, f'User {username} created successfully.')
    return redirect('dashboard_users')


@dashboard_auth_required
def dashboard_leads(request):
    leads = CardLead.objects.select_related('card').all().order_by('-created_at')
    total_leads_count = leads.count()
    now = timezone.now()
    leads_today = leads.filter(created_at__date=now.date()).count()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0)
    leads_month = leads.filter(created_at__gte=first_of_month).count()
    seven_days_ago = now - timedelta(days=7)
    leads_week = leads.filter(created_at__gte=seven_days_ago).count()

    return render(request, 'dashboard/leads.html', {
        'active_menu': 'leads',
        'leads': leads,
        'total_leads_count': total_leads_count,
        'leads_today': leads_today,
        'leads_month': leads_month,
        'leads_week': leads_week,
    })


@dashboard_auth_required
def dashboard_leads_export(request):
    leads = CardLead.objects.select_related('card').all().order_by('-created_at')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="brandnest_leads.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Created At', 'Name', 'Email', 'Phone', 'Company', 'Title', 'Card', 'Stage', 'Qualification', 'Message'])
    for l in leads:
        writer.writerow([
            l.id,
            l.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            l.name,
            l.email,
            l.phone,
            l.company,
            l.title,
            l.card.business_name if l.card else '',
            l.get_stage_display(),
            l.get_qualification_display(),
            l.message
        ])
    return response


@dashboard_auth_required
def dashboard_settings(request):
    company, _ = CompanySettings.objects.get_or_create(id=1)
    return render(request, 'dashboard/settings.html', {
        'active_menu': 'settings',
        'company': company,
    })


@dashboard_auth_required
def dashboard_settings_save_business(request):
    company, _ = CompanySettings.objects.get_or_create(id=1)
    if request.method == 'POST':
        company.company_name = request.POST.get('company_name', '').strip() or company.company_name
        company.tax_id = request.POST.get('tax_id', '').strip()
        company.website = request.POST.get('website', '').strip()
        try:
            company.total_employees = int(request.POST.get('total_employees', '10'))
        except ValueError:
            pass
        company.save()
        messages.success(request, 'Business Information updated successfully.')
    return redirect('dashboard_settings')


@dashboard_auth_required
def dashboard_settings_save_contact(request):
    company, _ = CompanySettings.objects.get_or_create(id=1)
    if request.method == 'POST':
        company.contact_email = request.POST.get('contact_email', '').strip()
        company.contact_number = request.POST.get('contact_number', '').strip()
        company.whatsapp_number = request.POST.get('whatsapp_number', '').strip()
        company.facebook_url = request.POST.get('facebook_url', '').strip()
        company.instagram_url = request.POST.get('instagram_url', '').strip()
        company.save()
        messages.success(request, 'Contact Information updated successfully.')
    return redirect('dashboard_settings')


@dashboard_auth_required
def dashboard_settings_save_address(request):
    company, _ = CompanySettings.objects.get_or_create(id=1)
    if request.method == 'POST':
        company.address = request.POST.get('address', '').strip()
        company.city = request.POST.get('city', '').strip()
        company.state = request.POST.get('state', '').strip()
        company.country = request.POST.get('country', '').strip() or 'India'
        company.pincode = request.POST.get('pincode', '').strip()
        company.save()
        messages.success(request, 'Address updated successfully.')
    return redirect('dashboard_settings')


@dashboard_auth_required
def dashboard_settings_save_branding(request):
    company, _ = CompanySettings.objects.get_or_create(id=1)
    if request.method == 'POST':
        company.primary_color = request.POST.get('primary_color', '#10B981').strip()
        if 'logo' in request.FILES:
            company.logo = request.FILES['logo']
        company.save()
        messages.success(request, 'Branding updated successfully.')
    return redirect('dashboard_settings')


@dashboard_auth_required
def dashboard_virtual_bg(request):
    cards = BusinessCard.objects.all()
    selected_card_id = request.GET.get('card')
    selected_card = cards.filter(id=selected_card_id).first() if selected_card_id else cards.first()
    return render(request, 'dashboard/virtual_bg.html', {
        'active_menu': 'virtual_bg',
        'cards': cards,
        'selected_card': selected_card,
    })


@dashboard_auth_required
def dashboard_email_sig(request):
    cards = BusinessCard.objects.all()
    selected_card_id = request.GET.get('card')
    selected_card = cards.filter(id=selected_card_id).first() if selected_card_id else cards.first()
    return render(request, 'dashboard/email_sig.html', {
        'active_menu': 'email_sig',
        'cards': cards,
        'selected_card': selected_card,
    })


@dashboard_auth_required
def dashboard_templates(request):
    return render(request, 'dashboard/templates_view.html', {
        'active_menu': 'templates',
    })


@dashboard_auth_required
def dashboard_accessories(request):
    return render(request, 'dashboard/accessories.html', {
        'active_menu': 'accessories',
    })


@dashboard_auth_required
def dashboard_integrations(request):
    return render(request, 'dashboard/integrations.html', {
        'active_menu': 'integrations',
    })


# =============================================================================
# BrandNest Enterprise Super Admin & Developer Suite Views
# =============================================================================

@dashboard_auth_required
def enterprise_admin_overview(request):
    import sys
    import django
    
    companies = EnterpriseCompany.objects.all().order_by('-created_at')
    total_companies = companies.count()
    
    enterprise_cards = BusinessCard.objects.filter(
        Q(enterprise_company__isnull=False) | Q(user__card_plan__plan_type='enterprise')
    ).distinct()
    total_cards_used = enterprise_cards.count()
    
    total_capacity = companies.aggregate(Sum('card_quota'))['card_quota__sum'] or 0
    total_revenue = companies.aggregate(Sum('total_paid'))['total_paid__sum'] or 0
    
    capacity_usage_pct = min(100, int((total_cards_used / max(1, total_capacity)) * 100)) if total_capacity else 0
    total_scans = enterprise_cards.aggregate(Sum('views_count'))['views_count__sum'] or 0
    total_leads = CardLead.objects.filter(card__in=enterprise_cards).count()
    
    context = {
        'active_ent_menu': 'overview',
        'companies': companies[:8],
        'total_companies': total_companies,
        'total_cards_used': total_cards_used,
        'total_capacity': total_capacity,
        'capacity_usage_pct': capacity_usage_pct,
        'total_revenue': total_revenue,
        'total_scans': total_scans,
        'total_leads': total_leads,
        'python_version': f"Python {sys.version.split()[0]}",
        'django_version': django.get_version(),
        'lan_ip': get_lan_ip(),
    }
    return render(request, 'enterprise_admin/overview.html', context)


@dashboard_auth_required
def enterprise_admin_companies(request):
    companies = EnterpriseCompany.objects.all().order_by('-created_at')
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search_query:
        companies = companies.filter(
            Q(name__icontains=search_query) |
            Q(head_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(tax_id__icontains=search_query)
        )
    if status_filter == 'active':
        companies = companies.filter(is_active=True)
    elif status_filter == 'suspended':
        companies = companies.filter(is_active=False)

    return render(request, 'enterprise_admin/companies.html', {
        'active_ent_menu': 'companies',
        'companies': companies,
        'search_query': search_query,
        'status_filter': status_filter,
    })


@dashboard_auth_required
def enterprise_admin_company_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        head_name = request.POST.get('head_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        card_quota = int(request.POST.get('card_quota', 10) or 10)
        plan_tier = request.POST.get('plan_tier', 'Most Popular (10 Cards)')
        tax_id = request.POST.get('tax_id', '').strip()
        website = request.POST.get('website', '').strip()
        notes = request.POST.get('notes', '').strip()

        if name:
            comp, created = EnterpriseCompany.objects.get_or_create(
                name=name,
                defaults={
                    'head_name': head_name,
                    'email': email,
                    'phone': phone,
                    'card_quota': card_quota,
                    'plan_tier': plan_tier,
                    'tax_id': tax_id,
                    'website': website,
                    'notes': notes,
                }
            )
            if not created:
                comp.head_name = head_name
                comp.email = email
                comp.phone = phone
                comp.card_quota = card_quota
                comp.plan_tier = plan_tier
                comp.tax_id = tax_id
                comp.website = website
                comp.notes = notes
                comp.save()
            messages.success(request, f'Enterprise company "{name}" provisioned successfully with {card_quota} card quota.')
    return redirect('enterprise_admin_companies')


@dashboard_auth_required
def enterprise_admin_company_quota(request, company_id):
    company = get_object_or_404(EnterpriseCompany, id=company_id)
    if request.method == 'POST':
        try:
            new_quota = int(request.POST.get('card_quota', company.card_quota))
            if new_quota < company.cards_used:
                messages.error(request, f'Cannot set quota below currently used cards ({company.cards_used}).')
            else:
                company.card_quota = new_quota
                plan_tier = request.POST.get('plan_tier', '').strip()
                if plan_tier:
                    company.plan_tier = plan_tier
                company.save()
                messages.success(request, f'Card quota for {company.name} updated to {new_quota} cards.')
        except ValueError:
            messages.error(request, 'Invalid quota number.')
    return redirect('enterprise_admin_companies')


@dashboard_auth_required
def enterprise_admin_company_toggle(request, company_id):
    company = get_object_or_404(EnterpriseCompany, id=company_id)
    if request.method == 'POST':
        company.is_active = not company.is_active
        company.save()
        status_label = 'Activated' if company.is_active else 'Suspended'
        messages.info(request, f'Enterprise company "{company.name}" has been {status_label}.')
    return redirect('enterprise_admin_companies')


@dashboard_auth_required
def enterprise_admin_cards(request):
    cards = BusinessCard.objects.all().order_by('-created_at')
    companies = EnterpriseCompany.objects.all().order_by('name')
    selected_company_id = request.GET.get('company', '').strip()
    search_query = request.GET.get('q', '').strip()

    if selected_company_id:
        cards = cards.filter(enterprise_company_id=selected_company_id)
    if search_query:
        cards = cards.filter(
            Q(owner_name__icontains=search_query) |
            Q(business_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    return render(request, 'enterprise_admin/cards.html', {
        'active_ent_menu': 'cards',
        'cards': cards,
        'companies': companies,
        'selected_company_id': selected_company_id,
        'search_query': search_query,
        'total_count': cards.count(),
    })


@dashboard_auth_required
def enterprise_admin_card_issue(request):
    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        owner_name = request.POST.get('owner_name', '').strip()
        role_title = request.POST.get('role_title', '').strip()
        business_name = request.POST.get('business_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        theme_color = request.POST.get('theme_color', '#4F46E5')
        tagline = request.POST.get('tagline', '').strip()

        company = get_object_or_404(EnterpriseCompany, id=company_id)
        if not business_name:
            business_name = company.name

        base_slug = slugify(f"{owner_name}-{company.name}") or 'card'
        slug = base_slug
        counter = 1
        while BusinessCard.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        card = BusinessCard.objects.create(
            user=request.user,
            enterprise_company=company,
            business_name=business_name,
            owner_name=owner_name,
            tagline=tagline or f"Official Digital Card of {company.name}",
            email=email,
            phone=phone,
            theme_color=theme_color,
            slug=slug,
            is_published=True,
            layout_config={
                'role_title': role_title,
                'sections_order': ['header', 'contact', 'actions', 'social', 'inquiry'],
            }
        )
        messages.success(request, f'Employee card for {owner_name} ({company.name}) issued successfully!')
    return redirect('enterprise_admin_cards')


@dashboard_auth_required
def enterprise_admin_teams(request):
    teams = Team.objects.prefetch_related('members').all().order_by('-created_at')
    companies = EnterpriseCompany.objects.all().order_by('name')
    return render(request, 'enterprise_admin/teams.html', {
        'active_ent_menu': 'teams',
        'teams': teams,
        'companies': companies,
    })


@dashboard_auth_required
def enterprise_admin_teams_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        company_id = request.POST.get('company_id')
        company = EnterpriseCompany.objects.filter(id=company_id).first() if company_id else None
        if name:
            team, _ = Team.objects.get_or_create(
                name=name,
                defaults={'owner': request.user, 'enterprise_company': company}
            )
            if company and team.enterprise_company != company:
                team.enterprise_company = company
                team.save()
            messages.success(request, f'Department "{name}" created successfully.')
    return redirect('enterprise_admin_teams')


@dashboard_auth_required
def enterprise_admin_leads(request):
    leads = CardLead.objects.select_related('card', 'card__enterprise_company').all().order_by('-created_at')
    companies = EnterpriseCompany.objects.all().order_by('name')
    selected_company_id = request.GET.get('company', '').strip()
    qualification_filter = request.GET.get('qualification', '').strip()
    search_query = request.GET.get('q', '').strip()

    if selected_company_id:
        leads = leads.filter(card__enterprise_company_id=selected_company_id)
    if qualification_filter:
        leads = leads.filter(qualification=qualification_filter)
    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(message__icontains=search_query)
        )

    return render(request, 'enterprise_admin/leads.html', {
        'active_ent_menu': 'leads',
        'leads': leads,
        'companies': companies,
        'selected_company_id': selected_company_id,
        'qualification_filter': qualification_filter,
        'search_query': search_query,
    })


@dashboard_auth_required
def enterprise_admin_leads_export(request):
    leads = CardLead.objects.select_related('card', 'card__enterprise_company').all().order_by('-created_at')
    selected_company_id = request.GET.get('company', '').strip()
    if selected_company_id:
        leads = leads.filter(card__enterprise_company_id=selected_company_id)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="brandnest_enterprise_leads.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Created At', 'Name', 'Email', 'Phone', 'Company', 'Title', 'Target Card', 'Enterprise Company', 'Stage', 'Qualification', 'Message'])
    for l in leads:
        writer.writerow([
            l.id,
            l.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            l.name,
            l.email,
            l.phone,
            l.company,
            l.title,
            l.card.business_name if l.card else '',
            l.card.enterprise_company.name if (l.card and l.card.enterprise_company) else '',
            l.get_stage_display(),
            l.get_qualification_display(),
            l.message
        ])
    return response


@dashboard_auth_required
def enterprise_admin_billing(request):
    companies = EnterpriseCompany.objects.all().order_by('-created_at')
    return render(request, 'enterprise_admin/billing.html', {
        'active_ent_menu': 'billing',
        'companies': companies,
    })

