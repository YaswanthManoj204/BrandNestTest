import re
from django.conf import settings
from django.shortcuts import render
from apps.cards.models import BusinessCard
from apps.frontend import views as frontend_views

RESERVED_SUBDOMAINS = {
    'www', 'api', 'admin', 'dashboard', 'enterprise', 'enterprise-admin',
    'static', 'media', 'mail', 'cname', 'app', 'stage', 'test', 'dev',
    'support', 'blog', 'help', 'status', 'auth', 'login', 'signup',
    'landing', 'checkout', 'cards', 'card'
}


class SubdomainRoutingMiddleware:
    """
    Subdomain Routing Engine:
    Inspects incoming requests and routes subdomains (e.g. https://raj.qkbiz.com/
    or http://raj.localhost:8000/) directly to the matching digital business card.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].lower()
        subdomain = self.extract_subdomain(host)

        if subdomain and subdomain not in RESERVED_SUBDOMAINS:
            # Let static, media, favicon and well-known assets pass through untouched
            if request.path.startswith(('/static/', '/media/', '/favicon.ico', '/.well-known/')):
                return self.get_response(request)

            card = BusinessCard.objects.filter(slug__iexact=subdomain).first()
            if card:
                request.subdomain = subdomain
                request.is_subdomain_card = True
                request.card = card

                path = request.path.rstrip('/')
                # 1. Subdomain Root -> Live Digital Business Card
                if path in ('', '/'):
                    return frontend_views.card_standalone(request, slug=card.slug)

                # 2. Subdomain QR Code image
                elif path in ('/qr.png', '/qr'):
                    return frontend_views.card_qr_image(request, slug=card.slug)

                # 3. Subdomain Lead Capture Form
                elif path == '/lead':
                    return frontend_views.record_card_lead(request, slug=card.slug)

                # 4. Subdomain Analytics & Event Tracking
                elif path.startswith('/track/'):
                    parts = [p for p in path.split('/') if p]
                    event_type = parts[1] if len(parts) > 1 else 'click'
                    return frontend_views.record_card_event(request, slug=card.slug, event_type=event_type)

            else:
                # Subdomain accessed but no card exists with this slug
                if request.path.rstrip('/') in ('', '/'):
                    return render(request, 'card_not_found.html', {
                        'subdomain': subdomain,
                        'host': host,
                    }, status=404)

        return self.get_response(request)

    @classmethod
    def extract_subdomain(cls, host):
        """
        Extracts the card subdomain from a host string.
        Examples:
        - 'medowa-global-4.192.168.1.34' -> 'medowa-global-4'
        - 'raj.192.168.1.34' -> 'raj'
        - 'raj.localhost' -> 'raj'
        - 'raj.mybrand.com' -> 'raj'
        - '192.168.1.34' -> None (pure IP address)
        - 'localhost' -> None
        """
        host = host.split(':')[0].strip().lower()

        # 1. Pure IP address (e.g. 192.168.1.34 or 127.0.0.1) -> No subdomain
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
            return None

        # 2. Subdomain on local server IP (e.g. medowa-global-4.192.168.1.34 or raj.192.168.1.34)
        ip_sub_match = re.match(r'^([a-zA-Z0-9_\-]+)\.\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host)
        if ip_sub_match:
            return ip_sub_match.group(1).lower()

        # 3. Check configured base domain if set in production (e.g. raj.mybrand.com)
        base_domain = getattr(settings, 'CARD_BASE_DOMAIN', '').strip().lower()
        if base_domain and host.endswith('.' + base_domain):
            prefix = host[:-len('.' + base_domain)]
            sub = prefix.split('.')[0].strip()
            return sub if sub else None

        # 4. Check localhost (e.g. raj.localhost)
        if host.endswith('.localhost'):
            prefix = host[:-len('.localhost')]
            sub = prefix.split('.')[0].strip()
            return sub if sub else None

        # 5. Check wildcard local DNS like nip.io or sslip.io or lvh.me
        if '.nip.io' in host or '.sslip.io' in host or '.lvh.me' in host:
            sub = host.split('.')[0].strip()
            return sub if sub else None

        # 6. Fallback for generic domains with 3+ parts (e.g. raj.hostingdomain.com)
        parts = host.split('.')
        if len(parts) >= 3 and not parts[-1].isdigit():
            if parts[-2] in ('co', 'com', 'org', 'net', 'edu', 'gov') and len(parts) >= 4:
                return parts[0]
            elif len(parts) == 3:
                return parts[0]

        return None

