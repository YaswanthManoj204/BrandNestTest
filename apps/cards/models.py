import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from apps.domains.models import Domain


class EnterpriseCompany(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    head_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    tax_id = models.CharField(max_length=80, blank=True)
    website = models.CharField(max_length=200, blank=True)
    plan_tier = models.CharField(max_length=50, default='Starter (5 Cards)')
    card_quota = models.PositiveIntegerField(default=10)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Enterprise Companies'

    def __str__(self):
        return f"{self.name} ({self.card_quota} cards)"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            base_slug = self.slug
            counter = 1
            while EnterpriseCompany.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def cards_used(self):
        return self.cards.count()

    @property
    def cards_remaining(self):
        return max(0, self.card_quota - self.cards_used)

    @property
    def usage_percentage(self):
        if self.card_quota == 0:
            return 100
        return min(100, int((self.cards_used / self.card_quota) * 100))


class BusinessCard(models.Model):
    card_id = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cards')
    enterprise_company = models.ForeignKey(EnterpriseCompany, on_delete=models.SET_NULL, null=True, blank=True, related_name='cards')
    domain = models.ForeignKey(Domain, on_delete=models.SET_NULL, null=True, blank=True, related_name='cards')

    # Basic business info
    business_name = models.CharField(max_length=150)
    owner_name = models.CharField(max_length=150, blank=True)
    tagline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    services = models.TextField(blank=True, help_text="Comma-separated or bullet points of services offered")

    # Visual assets
    logo = models.ImageField(upload_to='cards/logos/', null=True, blank=True)
    banner_image = models.ImageField(upload_to='cards/banners/', null=True, blank=True)
    profile_image = models.ImageField(upload_to='cards/profiles/', null=True, blank=True)
    theme_color = models.CharField(max_length=20, default='#2563EB')

    # Direct contact actions
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    google_maps_url = models.URLField(max_length=500, blank=True)
    existing_website = models.URLField(blank=True)

    # Social links structured as JSON
    social_links = models.JSONField(default=dict, blank=True, help_text="Dict of platform: url (linkedin, instagram, etc.)")

    # Drag & drop customizable layout order and section configurations
    layout_config = models.JSONField(default=dict, blank=True, help_text="Custom section order, capabilities, brands, tabs and theme")

    # Publishing and sharing
    is_published = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.business_name} ({self.card_id})"

    @property
    def bio(self):
        return self.description

    @property
    def name(self):
        return self.owner_name or self.business_name

    def save(self, *args, **kwargs):
        if not self.card_id:
            self.card_id = f"CARD-{uuid.uuid4().hex[:8].upper()}"
        if not self.slug:
            base_slug = slugify(self.business_name) or "business-card"
            candidate = base_slug
            counter = 1
            while BusinessCard.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def share_url(self):
        if self.domain:
            return f"https://{self.domain.domain_name}"
        return f"/card/{self.slug}/"


class UserPlan(models.Model):
    """
    Tracks whether a user is on Personal or Enterprise card bundle plan and their allowed card quota.
    """
    PLAN_TYPES = [
        ('personal', 'Personal'),
        ('enterprise', 'Enterprise'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='card_plan')
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, default='personal')
    company_name = models.CharField(max_length=180, blank=True)
    company_head_name = models.CharField(max_length=150, blank=True)
    company_phone = models.CharField(max_length=30, blank=True)
    company_email = models.EmailField(blank=True)
    card_limit = models.PositiveIntegerField(default=0)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_plan_type_display()} ({self.card_limit} cards)"


class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    enterprise_company = models.ForeignKey(EnterpriseCompany, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_teams')
    members = models.ManyToManyField(User, related_name='teams', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()


class CardLead(models.Model):
    STAGE_CHOICES = [
        ('new_lead', 'New Lead'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('closed', 'Closed'),
    ]
    QUALIFICATION_CHOICES = [
        ('hot', 'HOT'),
        ('warm', 'WARM'),
        ('cold', 'COLD'),
    ]

    card = models.ForeignKey(BusinessCard, on_delete=models.CASCADE, related_name='leads', null=True, blank=True)
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=150, blank=True)
    title = models.CharField(max_length=150, blank=True)
    source = models.CharField(max_length=50, default='Lead')
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='new_lead')
    qualification = models.CharField(max_length=10, choices=QUALIFICATION_CHOICES, default='cold')
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.email or self.phone})"


class NFCTag(models.Model):
    MODE_CHOICES = [
        ('web_card', 'Web Card'),
        ('save_contact', 'Save Contact'),
        ('lead_generation', 'Lead Generation'),
        ('custom_url', 'Link to any URL'),
    ]

    card = models.ForeignKey(BusinessCard, on_delete=models.CASCADE, related_name='nfc_tags')
    unique_code = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    nfc_mode = models.CharField(max_length=25, choices=MODE_CHOICES, default='web_card')
    custom_url = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    total_taps = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"NFC {self.unique_code} ({self.card.business_name})"

    def save(self, *args, **kwargs):
        if not self.unique_code:
            self.unique_code = f"W{uuid.uuid4().hex[:9].upper()}"
        super().save(*args, **kwargs)


class CompanySettings(models.Model):
    company_name = models.CharField(max_length=200, default='BrandNest Global Ventures')
    tax_id = models.CharField(max_length=80, blank=True)
    website = models.CharField(max_length=200, blank=True)
    total_employees = models.PositiveIntegerField(default=10)
    
    # Contact info
    contact_email = models.EmailField(blank=True, default='support@brandnest.io')
    contact_number = models.CharField(max_length=30, blank=True)
    whatsapp_number = models.CharField(max_length=30, blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='India')
    pincode = models.CharField(max_length=20, blank=True)
    
    # Branding
    logo = models.ImageField(upload_to='company/logos/', null=True, blank=True)
    primary_color = models.CharField(max_length=20, default='#10B981')
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Company Settings'

    def __str__(self):
        return self.company_name


class WalletPassConfig(models.Model):
    card = models.OneToOneField(BusinessCard, on_delete=models.CASCADE, related_name='wallet_pass')
    color_preset = models.CharField(max_length=20, default='brand')
    custom_color = models.CharField(max_length=20, default='#1A1744')
    logo = models.ImageField(upload_to='cards/wallet_logos/', null=True, blank=True)
    banner = models.ImageField(upload_to='cards/wallet_banners/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet Pass for {self.card.business_name}"


class CardAnalyticsEvent(models.Model):
    EVENT_TYPES = [
        ('view', 'Card View'),
        ('share_click', 'Clicks on Share Button'),
        ('main_action_click', 'Clicks on Main Action Button'),
        ('whatsapp_click', 'Clicks on WhatsApp Button'),
        ('contact_download', 'Contact Downloads'),
        ('contact_exchange', 'Contacts Exchanged'),
        ('lead_submit', 'Lead Generated'),
    ]

    card = models.ForeignKey(BusinessCard, on_delete=models.CASCADE, related_name='analytics_events')
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.card.business_name} - {self.event_type}"
