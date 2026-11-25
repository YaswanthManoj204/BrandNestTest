import json
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from apps.domains.models import Domain
from apps.cards.models import BusinessCard, UserPlan, PlatformPricing, CardLead, EnterpriseCompany
from apps.websites.models import Industry, Website


class FrontendFlowTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.client = Client()
        self.test_user = User.objects.create_user(
            username='builder_test',
            email='builder_test@brandnest.io',
            password='BuilderTestPassword123!'
        )
        self.industry = Industry.objects.create(
            name="Technology and IT",
            slug="technology-and-it",
            icon="bi-cpu",
            form_schema={
                "sections": [
                    {
                        "id": "services",
                        "title": "Services",
                        "fields": [{"name": "services_list", "label": "Services", "type": "text"}]
                    }
                ]
            }
        )

    def test_landing_page(self):
        res = self.client.get(reverse('landing'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Build business card")
        self.assertContains(res, "Order physical NFC card")

    def test_card_builder_requires_login_redirect(self):
        res = self.client.get(reverse('card_builder'))
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login/?next=/card/create/', res['Location'])

    def test_card_builder_get(self):
        self.client.force_login(self.test_user)
        res = self.client.get(reverse('card_builder'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Build your digital business card")
        self.assertNotContains(res, "Existing website URL")

    def test_card_builder_post_flow(self):
        self.client.force_login(self.test_user)
        post_data = {
            'business_name': 'Sarah Legal & Advisory',
            'owner_name': 'Sarah Jenkins',
            'tagline': 'Corporate Law Partner',
            'phone': '+1 555 123 4567',
            'email': 'sarah@legal.com',
            'whatsapp': '+15551234567',
            'address': '450 Lexington Ave, NY',
            'existing_website': 'https://sarahconsulting.com',
            'theme_color': '#2563EB',
            'social_linkedin': 'https://linkedin.com/in/sarahjenkins',
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)  # Redirects to preview

        card = BusinessCard.objects.get(business_name='Sarah Legal & Advisory')
        self.assertEqual(card.existing_website, 'https://sarahconsulting.com')

        # Test card preview page
        preview_res = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}))
        self.assertEqual(preview_res.status_code, 200)
        self.assertContains(preview_res, 'Sarah Legal &amp; Advisory')
        self.assertContains(preview_res, 'sarahconsulting.com')
        # Check removed options from preview page
        self.assertNotContains(preview_res, 'Delete')
        self.assertNotContains(preview_res, 'My Cards')
        self.assertNotContains(preview_res, 'Live Card')
        self.assertNotContains(preview_res, 'Build Another Card')
        self.assertContains(preview_res, 'Return to Homepage')

        # Test standalone card template
        standalone_res = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(standalone_res.status_code, 200)
        self.assertContains(standalone_res, 'Sarah Legal &amp; Advisory')

    def test_card_builder_with_custom_layout_order(self):
        self.client.force_login(self.test_user)
        post_data = {
            'business_name': 'Medowa Global Pvt Ltd',
            'owner_name': 'Sujithra Ramaswamy',
            'role_title': 'Head-Business & Operations',
            'banner_tagline': 'We Solve Business Challenges',
            'about_heading': 'ELEVATE YOUR DIGITAL PRESENCE.',
            'bio': 'Strategic digital marketing partners.',
            'services': 'Search Engine Optimization, Search Engine Marketing',
            'brands': 'Qklly Connect, BlackPillar',
            'phone': '+91 98765 43210',
            'email': 'sujithra@medowaglobal.com',
            'whatsapp': '+919876543210',
            'address': 'Chennai, Tamil Nadu, India',
            'website': 'medowaglobal.com',
            'accent_color': '#0084FF',
            'linkedin': 'https://linkedin.com/in/sujithra',
            'youtube': 'https://youtube.com/@medowaglobal',
            'section_order': '["about", "capabilities", "connect", "callback", "brands", "socials"]',
            'disabled_sections': '[]'
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Medowa Global Pvt Ltd')
        self.assertEqual(card.owner_name, 'Sujithra Ramaswamy')
        self.assertEqual(card.layout_config['role_title'], 'Head-Business & Operations')
        self.assertEqual(card.layout_config['section_order'], ['about', 'capabilities', 'connect', 'callback', 'brands', 'socials'])

        # Standalone verification
        res_view = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(res_view.status_code, 200)
        self.assertContains(res_view, 'ELEVATE YOUR DIGITAL PRESENCE.')
        self.assertContains(res_view, 'Sujithra Ramaswamy')

    def test_website_builder_get(self):
        res = self.client.get(reverse('website_builder'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Choose Your Industry")
        self.assertContains(res, "Technology and IT")

    def test_website_builder_post_flow(self):
        post_data = {
            'domain_name': 'hypercloud.io',
            'industry_slug': 'technology-and-it',
            'title': 'HyperCloud Infrastructure',
            'tagline': 'Next-Gen Serverless Hosting',
            'about_text': 'Building automated cloud deployments.',
            'contact_email': 'ops@hypercloud.io',
            'contact_phone': '+1 800 555 9999',
            'address': '100 Tech Blvd, Austin TX',
            'custom_services_list': 'Multi-cloud Kubernetes, Edge CI/CD',
        }
        res = self.client.post(reverse('website_builder'), post_data)
        self.assertEqual(res.status_code, 302)  # Redirects to preview

        site = Website.objects.get(title='HyperCloud Infrastructure')
        self.assertEqual(site.domain.domain_name, 'hypercloud.io')
        self.assertEqual(site.industry.slug, 'technology-and-it')
        self.assertIn('services_list', site.custom_data)

        # Test website preview page
        preview_res = self.client.get(reverse('website_preview', kwargs={'site_id': site.site_id}))
        self.assertEqual(preview_res.status_code, 200)
        self.assertContains(preview_res, 'HyperCloud Infrastructure')

        # Test standalone website template
        standalone_res = self.client.get(reverse('website_standalone', kwargs={'slug': site.slug}))
        self.assertEqual(standalone_res.status_code, 200)
        self.assertContains(standalone_res, 'HyperCloud Infrastructure')
        self.assertContains(standalone_res, 'Next-Gen Serverless Hosting')

    def test_signup_get(self):
        res = self.client.get(reverse('signup'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Create your account")
        self.assertContains(res, "BrandNest ID")

    def test_signup_post_success(self):
        post_data = {
            'full_name': 'Yash Manoj',
            'email': 'yash@brandnest.io',
            'username': 'yashmanoj',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        }
        res = self.client.post(reverse('signup'), post_data)
        self.assertEqual(res.status_code, 302)  # Redirects to landing or next
        
        # Verify user created and authenticated
        from django.contrib.auth.models import User
        user = User.objects.get(email='yash@brandnest.io')
        self.assertEqual(user.username, 'yashmanoj')
        self.assertEqual(user.first_name, 'Yash')
        self.assertEqual(user.last_name, 'Manoj')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_signup_post_password_mismatch(self):
        post_data = {
            'full_name': 'Test User',
            'email': 'test@brandnest.io',
            'password': 'Password123',
            'confirm_password': 'DifferentPassword456',
        }
        res = self.client.post(reverse('signup'), post_data)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Passwords do not match")

    def test_login_get(self):
        res = self.client.get(reverse('login'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Welcome back")
        self.assertContains(res, "Sign in to BrandNest")

    def test_login_post_by_username(self):
        from django.contrib.auth.models import User
        User.objects.create_user(username='alexv', email='alex@brandnest.io', password='TestSecretPassword123')

        res = self.client.post(reverse('login'), {
            'login_identifier': 'alexv',
            'password': 'TestSecretPassword123',
            'next': '/card/create/',
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res['Location'], '/card/create/')
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_login_post_by_email(self):
        from django.contrib.auth.models import User
        User.objects.create_user(username='sarahc', email='sarah@brandnest.io', password='TestSecretPassword123')

        # Login using email instead of username
        res = self.client.post(reverse('login'), {
            'login_identifier': 'sarah@brandnest.io',
            'password': 'TestSecretPassword123'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_login_post_invalid_credentials(self):
        res = self.client.post(reverse('login'), {
            'login_identifier': 'nonexistent@brandnest.io',
            'password': 'WrongPassword!'
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Invalid email/username or password")

    def test_logout(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user(username='logoutuser', email='logout@brandnest.io', password='Password123')
        self.client.force_login(user)
        self.assertTrue('_auth_user_id' in self.client.session)

        res = self.client.get(reverse('logout'))
        self.assertEqual(res.status_code, 302)
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_enterprise_bundle_quota_and_topup_flow(self):
        from apps.cards.models import UserPlan

        choose_res = self.client.get(reverse('card_choose_plan'))
        self.assertEqual(choose_res.status_code, 200)
        self.assertContains(choose_res, 'For Personal Use')
        self.assertContains(choose_res, 'For Enterprise')
        self.assertContains(choose_res, reverse('enterprise_company'))

        # Step 1: Company details onboarding (creates account + saves company info)
        company_get = self.client.get(reverse('enterprise_company'))
        self.assertEqual(company_get.status_code, 200)
        company_post = self.client.post(reverse('enterprise_company'), {
            'company_name': 'Apex Global Corp',
            'company_head_name': 'Rahul Sharma',
            'company_phone': '+91 9876543210',
            'company_email': 'rahul@apexglobal.com',
            'password': 'EnterprisePassword123',
            'confirm_password': 'EnterprisePassword123',
        })
        self.assertEqual(company_post.status_code, 302)
        self.assertEqual(company_post['Location'], reverse('enterprise_checkout'))

        from django.contrib.auth.models import User
        ent_user = User.objects.get(email='rahul@apexglobal.com')

        checkout_get = self.client.get(reverse('enterprise_checkout'))
        self.assertEqual(checkout_get.status_code, 200)
        self.assertContains(checkout_get, 'Apex Global Corp')
        self.assertContains(checkout_get, '5 Business Cards')
        self.assertContains(checkout_get, '10 Business Cards')
        self.assertContains(checkout_get, '15 Business Cards')
        self.assertContains(checkout_get, '5 Business Cards + 5 NFC Cards')
        self.assertContains(checkout_get, '10 Business Cards + 10 NFC Cards')
        self.assertContains(checkout_get, '15 Business Cards + 15 NFC Cards')

        # Step 2: Purchase 5-card Enterprise bundle
        checkout_post = self.client.post(reverse('enterprise_checkout'), {'bundle_size': '5'})
        self.assertEqual(checkout_post.status_code, 302)
        self.assertEqual(checkout_post['Location'], reverse('card_list'))

        plan = UserPlan.objects.get(user=ent_user)
        self.assertEqual(plan.plan_type, 'enterprise')
        self.assertEqual(plan.company_name, 'Apex Global Corp')
        self.assertEqual(plan.card_limit, 5)

        # Step 3: Create 5 cards (owner + 4 team)
        for i in range(5):
            r = self.client.post(reverse('card_builder'), {'business_name': f'Team Member {i+1}'})
            self.assertEqual(r.status_code, 302)
            self.assertTrue(r['Location'] == reverse('card_list') or '/card/preview/' in r['Location'])

        # 6th attempt redirects to /cards/?upgrade=1 and shows top-up modal
        sixth_attempt = self.client.get(reverse('card_builder'))
        self.assertEqual(sixth_attempt.status_code, 302)
        self.assertIn('/cards/?upgrade=1', sixth_attempt['Location'])

        list_res = self.client.get(reverse('card_list') + '?upgrade=1')
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, 'Add More Users')
        self.assertContains(list_res, '5 / 5')

        # Top up with +5 more users
        topup_res = self.client.post(reverse('enterprise_topup'), {'extra_cards': '5'})
        self.assertEqual(topup_res.status_code, 302)
        self.assertTrue(topup_res['Location'] in (reverse('card_list'), reverse('card_builder')))

        plan.refresh_from_db()
        self.assertEqual(plan.card_limit, 10)

        # 6th card creation now succeeds
        sixth_ok = self.client.get(reverse('card_builder'))
        self.assertEqual(sixth_ok.status_code, 200)

    def test_payment_validation_images_brands_and_address_location(self):
        import json
        self.client.force_login(self.test_user)

        # 1. Enabled payment toggle with empty ID should block card creation
        invalid_res = self.client.post(reverse('card_builder'), {
            'business_name': 'Validation Test Biz',
            'payment_gpay_enabled': 'on',
            'payment_gpay': '',
        })
        self.assertEqual(invalid_res.status_code, 200)
        self.assertContains(invalid_res, 'Google Pay')
        self.assertFalse(BusinessCard.objects.filter(business_name='Validation Test Biz').exists())

        # 2. Valid payment + brands + images + Google Maps link saves and renders properly
        ok_res = self.client.post(reverse('card_builder'), {
            'business_name': 'Gallery & Brand Studio',
            'address': '221B Baker Street',
            'maps_link': 'https://maps.google.com/?q=221B+Baker+Street',
            'payment_gpay_enabled': 'on',
            'payment_gpay': 'studio@okaxis',
            'brands_data': json.dumps([{'id': 1, 'title': 'Studio Brand', 'image': '', 'description': 'Hidden on card, visible in popup'}]),
            'images_data': json.dumps([{'id': 2, 'title': 'Showroom Photo', 'image': 'https://example.com/photo.jpg'}]),
        })
        self.assertEqual(ok_res.status_code, 302)
        card = BusinessCard.objects.get(business_name='Gallery & Brand Studio')
        self.assertEqual(len(card.layout_config['images_items']), 1)

        standalone = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(standalone.status_code, 200)
        html = standalone.content.decode('utf-8')
        self.assertIn('id="block-images"', html)
        self.assertIn('Showroom Photo', html)
        self.assertIn('Studio Brand', html)
        # Brand description is in data-desc for popup, not rendered as a <p> below brand title
        self.assertIn('data-desc="Hidden on card, visible in popup"', html)
        self.assertNotIn('<p>Hidden on card, visible in popup</p>', html)
        # Address tile carries Google Maps link for the Location button in popup
        self.assertIn('data-map-url="https://maps.google.com/?q=221B+Baker+Street"', html)

    def test_enterprise_incremental_stepper_and_inr_currency(self):
        self.client.force_login(self.test_user)

        # 1. Enterprise checkout displays INR currency
        chk_res = self.client.get(reverse('enterprise_checkout'))
        self.assertEqual(chk_res.status_code, 200)
        chk_html = chk_res.content.decode('utf-8')
        self.assertIn('₹999', chk_html)
        self.assertIn('₹199.80 / card', chk_html)
        self.assertNotIn('$49', chk_html)

        # 2. Activate enterprise plan
        post_chk = self.client.post(reverse('enterprise_checkout'), {'bundle_size': '5'})
        self.assertEqual(post_chk.status_code, 302)
        plan = UserPlan.objects.get(user=self.test_user)
        self.assertEqual(plan.card_limit, 5)

        # 3. Topup with +1 card stepper (incremental)
        topup1 = self.client.post(reverse('enterprise_topup'), {'extra_cards': '1'})
        self.assertEqual(topup1.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.card_limit, 6)
        self.assertEqual(plan.total_paid, 999 + 199)

        # 4. Topup with +3 cards
        topup3 = self.client.post(reverse('enterprise_topup'), {'extra_cards': '3'})
        self.assertEqual(topup3.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.card_limit, 9)
        self.assertEqual(plan.total_paid, 999 + 199 + (3 * 199))

        # 5. Card list renders stepper UI and INR price
        list_res = self.client.get(reverse('card_list'))
        self.assertEqual(list_res.status_code, 200)
        list_html = list_res.content.decode('utf-8')
        self.assertIn('displayExtraCardsCount', list_html)
        self.assertIn('btnStepPlus', list_html)
        self.assertIn('btnStepMinus', list_html)
        self.assertIn('₹199', list_html)
        self.assertNotIn('Super Admin', list_html)
        self.assertNotIn('New card limit', list_html)

    def test_youtube_featured_video_and_channel_tab(self):
        self.client.force_login(self.test_user)

        post_data = {
            'business_name': 'Aura Studio Digital',
            'owner_name': 'Sarah Connor',
            'youtube_video_url': 'https://www.youtube.com/watch?v=07d2dXHYb94',
            'youtube': 'https://youtube.com/@aurastudio',
            'yt_channel_name': 'Aura Studio Official',
            'yt_subscribers': '25K Subscribers',
            'yt_description': 'Official channel featuring digital design and transformation case studies.',
            'section_order': '["video", "capabilities", "about", "brands", "images", "connect", "socials"]',
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Aura Studio Digital')
        self.assertEqual(card.layout_config['youtube_video_url'], 'https://www.youtube.com/watch?v=07d2dXHYb94')
        self.assertEqual(card.layout_config['yt_channel_name'], 'Aura Studio Official')
        self.assertEqual(card.layout_config['yt_subscribers'], '25K Subscribers')
        self.assertIn('video', card.layout_config['section_order'])

        # Standalone verification
        view_res = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(view_res.status_code, 200)
        html = view_res.content.decode('utf-8')

        # Check Home tab Featured Video block above capabilities
        self.assertIn('id="block-video"', html)
        self.assertIn('pVideoPosterBox', html)
        self.assertIn('07d2dXHYb94', html)  # Extracted YouTube video ID in thumbnail URL

        # Check YouTube Channel tab & Subscribe pill
        self.assertIn('id="tabYoutubeBtn"', html)
        self.assertIn('Youtube Channel', html)
        self.assertIn('id="tabContentYoutube"', html)
        self.assertIn('Aura Studio Official', html)
        self.assertIn('25K Subscribers', html)
        self.assertIn('LATEST VIDEOS', html)
        self.assertIn('pYtSubscribeBtn', html)

    def test_banner_draggable_and_adjustable_configuration(self):
        """Verify banner draggable & adjustable coordinates and zoom persist and render correctly."""
        self.client.force_login(self.test_user)

        post_data = {
            'business_name': 'Horizon Brand Studio',
            'owner_name': 'Elena Rostova',
            'owner_role': 'Creative Director',
            'phone': '+1987654321',
            'email': 'elena@horizonstudio.com',
            'banner_position': '62.5% 38.0%',
            'banner_x': '12.5%',
            'banner_y': '-12.0%',
            'banner_zoom': '1.35',
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Horizon Brand Studio')
        self.assertEqual(card.layout_config.get('banner_x'), '12.5%')
        self.assertEqual(card.layout_config.get('banner_y'), '-12.0%')
        self.assertEqual(card.layout_config.get('banner_zoom'), '1.35')
        self.assertEqual(card.layout_config.get('banner_position'), '62.5% 38.0%')

        # Builder preview check
        builder_res = self.client.get(reverse('card_edit', kwargs={'card_id': card.card_id}))
        self.assertEqual(builder_res.status_code, 200)
        builder_html = builder_res.content.decode('utf-8')
        self.assertIn('id="rangeBannerZoom"', builder_html)
        self.assertIn('pBannerLayer', builder_html)
        self.assertIn('banner-drag-hint', builder_html)
        self.assertIn('translate(12.5%, -12.0%)', builder_html)
        self.assertIn('scale(1.35)', builder_html)

        # Standalone public card check
        view_res = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(view_res.status_code, 200)
        view_html = view_res.content.decode('utf-8')
        self.assertIn('translate(12.5%, -12.0%)', view_html)
        self.assertIn('scale(1.35)', view_html)

    def test_youtube_embed_player_configuration_and_referrer_policy(self):
        """Verify strict-origin-when-cross-origin referrer policy and YouTube embed iframe attributes."""
        from apps.frontend.views import _extract_youtube_id

        # Verify various YouTube URL formats
        self.assertEqual(_extract_youtube_id('https://www.youtube.com/watch?v=07d2dXHYb94'), '07d2dXHYb94')
        self.assertEqual(_extract_youtube_id('https://www.youtube.com/watch?feature=shared&v=07d2dXHYb94'), '07d2dXHYb94')
        self.assertEqual(_extract_youtube_id('https://youtu.be/07d2dXHYb94?si=xyz123'), '07d2dXHYb94')
        self.assertEqual(_extract_youtube_id('https://www.youtube.com/shorts/07d2dXHYb94'), '07d2dXHYb94')
        self.assertEqual(_extract_youtube_id('https://www.youtube.com/embed/07d2dXHYb94'), '07d2dXHYb94')
        self.assertEqual(_extract_youtube_id('07d2dXHYb94'), '07d2dXHYb94')

        self.client.force_login(self.test_user)
        res = self.client.get(reverse('card_builder'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')
        html = res.content.decode('utf-8')
        self.assertIn('referrerpolicy="strict-origin-when-cross-origin"', html)
        self.assertIn('meta name="referrer" content="strict-origin-when-cross-origin"', html)
        self.assertIn('youtube-nocookie.com/embed', html)

    def test_youtube_channel_auto_fetch_api_and_social_link_auto_population(self):
        """Verify YouTube Channel auto-fetch API endpoint returns title, subs, bio, and videos."""
        self.client.force_login(self.test_user)

        # 1. API endpoint validation
        api_res = self.client.get(reverse('api_youtube_channel_info'), {'url': 'https://www.youtube.com/@techworld'})
        self.assertEqual(api_res.status_code, 200)
        data = api_res.json()
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('title'))
        self.assertTrue(data.get('subscribers'))

        # 2. Saving card with only YouTube URL auto-populates channel fields on backend
        post_data = {
            'business_name': 'Quantum Media Labs',
            'owner_name': 'Victor Stone',
            'youtube': 'https://youtube.com/@quantumlabs',
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Quantum Media Labs')
        self.assertTrue(card.layout_config.get('yt_channel_name'))
        self.assertTrue(card.layout_config.get('yt_subscribers'))
        self.assertTrue(card.layout_config.get('yt_description'))

    def test_google_maps_url_linking_and_popup_location_handling(self):
        """Verify Google Maps URL is normalized and integrated into Address modal & Google Map tile."""
        self.client.force_login(self.test_user)

        post_data = {
            'business_name': 'Apex Map Studio',
            'owner_name': 'Maya Lin',
            'address': '456 Tech Park Way, Suite 100',
            'maps_link': 'maps.app.goo.gl/a2YSR',
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Apex Map Studio')
        self.assertEqual(card.google_maps_url, 'https://maps.app.goo.gl/a2YSR')
        self.assertEqual(card.address, '456 Tech Park Way, Suite 100')

        # Verify standalone card template rendering
        standalone_res = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(standalone_res.status_code, 200)
        html = standalone_res.content.decode('utf-8')
        self.assertIn('handleGoogleMapClick', html)
        self.assertIn('data-map-url="https://maps.app.goo.gl/a2YSR"', html)
        self.assertIn('openAddressModal', html)

    def test_multiple_youtube_videos_and_map_fallback(self):
        """Verify adding multiple videos in Socials & YouTube Channel and fallback address search."""
        self.client.force_login(self.test_user)

        import json
        videos_data = [
            {'id': 1, 'title': 'Product Architecture Overview', 'url': 'https://www.youtube.com/watch?v=07d2dXHYb94'},
            {'id': 2, 'title': 'Customer Success Stories', 'url': 'https://youtu.be/ScMzIvxBSi4'},
        ]

        post_data = {
            'business_name': 'Omni Video Labs',
            'owner_name': 'Elena Rostova',
            'address': '789 Innovation Boulevard, Austin, TX',
            'maps_link': '',  # Test auto-fallback to google maps search query
            'yt_videos_json': json.dumps(videos_data),
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Omni Video Labs')
        # Check auto-fallback google maps query
        self.assertTrue(card.google_maps_url.startswith('https://www.google.com/maps/search/?api=1&query='))
        
        # Check multiple videos stored and thumbnails auto-derived
        saved_vids = card.layout_config.get('yt_videos', [])
        self.assertEqual(len(saved_vids), 2)
        self.assertEqual(saved_vids[0]['title'], 'Product Architecture Overview')
        self.assertEqual(saved_vids[0]['thumbnail'], 'https://img.youtube.com/vi/07d2dXHYb94/hqdefault.jpg')
        self.assertEqual(saved_vids[1]['thumbnail'], 'https://img.youtube.com/vi/ScMzIvxBSi4/hqdefault.jpg')

        # Check standalone rendering
        standalone_res = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(standalone_res.status_code, 200)
        html = standalone_res.content.decode('utf-8')
        self.assertIn('Product Architecture Overview', html)
        self.assertIn('Customer Success Stories', html)
        self.assertIn('pYtDescToggleBtn', html)
        self.assertIn('toggleYtDescExpand', html)

    def test_published_card_disables_image_dragging_and_gestures(self):
        """Verify that on published cards (after generate/publish), dragging and gestures are strictly disabled."""
        self.client.force_login(self.test_user)
        card = BusinessCard.objects.create(
            user=self.test_user,
            business_name='Static Shield Corp',
            owner_name='Marcus Sterling',
            phone='+1122334455',
            email='marcus@staticshield.com',
            existing_website='https://staticshield.com',
            layout_config={
                'banner_x': '5.0%',
                'banner_y': '-10.0%',
                'banner_zoom': '1.20',
                'avatar_x': '0.0%',
                'avatar_y': '0.0%',
                'avatar_zoom': '1.0',
            }
        )

        # 1. Check builder view (before generate / when editing in builder)
        builder_res = self.client.get(reverse('card_edit', kwargs={'card_id': card.card_id}))
        self.assertEqual(builder_res.status_code, 200)
        builder_html = builder_res.content.decode('utf-8')
        self.assertIn('<body class="card-builder-mode">', builder_html)
        self.assertIn('isCardBuilderActive', builder_html)

        # 2. Check public / standalone card view (after publish / when scanned via QR)
        pub_res = self.client.get(reverse('card_standalone', kwargs={'slug': card.slug}))
        self.assertEqual(pub_res.status_code, 200)
        pub_html = pub_res.content.decode('utf-8')

        # Published card body must NOT have card-builder-mode class
        self.assertNotIn('<body class="card-builder-mode">', pub_html)
        self.assertIn('<body>', pub_html)
        # Published card must NOT block logo clicks with preventDefault
        self.assertNotIn('onclick="event.preventDefault();"', pub_html)
        # Published card preserves the saved transform coordinates statically
        self.assertIn('translate(5.0%, -10.0%) scale(1.20)', pub_html)
        # Drag controller guard logic is present
        self.assertIn('isCardBuilderActive()', pub_html)
        # Drag hints are hidden by default in CSS and only scoped to .card-builder-mode
        self.assertIn('.banner-drag-hint {', pub_html)
        self.assertIn('display: none !important;', pub_html)
        self.assertIn('.card-builder-mode .banner-drag-hint', pub_html)
        self.assertIn('.card-builder-mode .avatar-drag-hint', pub_html)

    def test_brochure_document_link_optional_and_builder_persistence(self):
        """Verify Option B Document URL is optional and builder reloads saved items when going back/editing."""
        self.client.force_login(self.test_user)

        # 1. Post a card without Option B document link URL (should succeed without error)
        capabilities = [
            {'id': 1, 'title': 'Enterprise Branding', 'image': 'https://example.com/b.jpg', 'description': 'Full scale branding'}
        ]
        brands = [
            {'id': 101, 'title': 'Apex Partner Co', 'image': 'https://example.com/logo.png', 'description': 'Design studio partner'}
        ]
        images = [
            {'id': 201, 'title': 'Showcase Room', 'image': 'https://example.com/room.jpg'}
        ]
        videos = [
            {'id': 301, 'title': 'Launch Keynote', 'url': 'https://youtu.be/07d2dXHYb94', 'thumbnail': 'https://img.youtube.com/vi/07d2dXHYb94/hqdefault.jpg'}
        ]

        post_data = {
            'business_name': 'Quantum Architecture',
            'owner_name': 'Kavya Sharma',
            'owner_role': 'Principal Partner',
            'phone': '+91 9988776655',
            'email': 'kavya@quantumarch.com',
            'more_section_title': 'Brochure & Dossier',
            'more_doc_enabled': 'on',
            'more_doc_title': 'Firm Overview',
            'more_doc_url': '',  # Option B left completely empty
            'capabilities_data': json.dumps(capabilities),
            'brands_data': json.dumps(brands),
            'images_data': json.dumps(images),
            'yt_videos_json': json.dumps(videos),
            'section_order': json.dumps(["capabilities", "brands", "more", "video"]),
            'disabled_sections': json.dumps(["callback"]),
        }

        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Quantum Architecture')
        self.assertEqual(card.layout_config['more']['section_title'], 'Brochure & Dossier')
        self.assertEqual(card.layout_config['more']['doc_url'], '')
        self.assertEqual(len(card.layout_config['capabilities_items']), 1)
        self.assertEqual(len(card.layout_config['brands_items']), 1)
        self.assertEqual(len(card.layout_config['images_items']), 1)
        self.assertEqual(len(card.layout_config['yt_videos']), 1)

        # 2. Open edit builder (simulate user hitting back or clicking Edit Card)
        edit_res = self.client.get(reverse('card_edit', kwargs={'card_id': card.card_id}))
        self.assertEqual(edit_res.status_code, 200)
        html = edit_res.content.decode('utf-8')

        # Check Option B is text input with (Optional) label
        self.assertIn('Option B: Document Link URL <span style="font-weight:normal;color:#64748B;font-size:11.5px;">(Optional)</span>', html)
        self.assertIn('id="more_doc_url" name="more_doc_url"', html)

        # Check saved capabilities, brands, images, videos & section order are populated in builder context
        self.assertIn('Enterprise Branding', html)
        self.assertIn('Apex Partner Co', html)
        self.assertIn('Showcase Room', html)
        self.assertIn('Launch Keynote', html)
        self.assertIn('brandnest_card_draft_', html)

        # 3. Check preview page for callout text
        preview_res = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}))
        self.assertEqual(preview_res.status_code, 200)
        self.assertNotContains(preview_res, 'Need a full business website?')
        self.assertNotContains(preview_res, 'single-page company website')
        self.assertNotContains(preview_res, 'multi-page company website')
        self.assertNotContains(preview_res, 'Build Another Card')

    def test_multiuser_personal_card_isolation_and_reload(self):
        from django.contrib.auth.models import User
        # Create User A and User B
        user_a = User.objects.create_user(username='user_a', email='user_a@brandnest.io', password='Password123!')
        user_b = User.objects.create_user(username='user_b', email='user_b@brandnest.io', password='Password123!')

        # 1. User A logs in and visits card builder
        self.client.force_login(user_a)
        res_a_new = self.client.get(reverse('card_builder'))
        self.assertEqual(res_a_new.status_code, 200)
        self.assertFalse(res_a_new.context['is_edit'])
        # New card fields must be empty (no other person's or dummy data)
        self.assertEqual(res_a_new.context['card'].owner_name, '')
        self.assertEqual(res_a_new.context['card'].business_name, '')
        self.assertEqual(res_a_new.context['card'].email, '')

        # User A fills details and generates personal card
        post_data_a = {
            'business_name': 'Alpha Apex Consulting',
            'owner_name': 'Alice Archer',
            'owner_role': 'Managing Director',
            'phone': '+1 555 111 2222',
            'email': 'alice@alphaapex.com',
            'whatsapp': '+1 555 111 2222',
            'bio': 'Strategic growth advisors for modern tech brands.',
        }
        create_res = self.client.post(reverse('card_builder'), post_data_a)
        self.assertEqual(create_res.status_code, 302)
        card_a = BusinessCard.objects.get(owner_name='Alice Archer')
        self.assertEqual(card_a.user, user_a)

        # User A logs in again or visits /card/create/ -> sees their existing card and can make changes
        res_a_return = self.client.get(reverse('card_builder'))
        self.assertEqual(res_a_return.status_code, 200)
        self.assertTrue(res_a_return.context['is_edit'])
        self.assertEqual(res_a_return.context['card'].card_id, card_a.card_id)
        self.assertEqual(res_a_return.context['card'].owner_name, 'Alice Archer')
        self.assertEqual(res_a_return.context['card'].business_name, 'Alpha Apex Consulting')

        # 2. User B logs in
        self.client.force_login(user_b)
        res_b = self.client.get(reverse('card_builder'))
        self.assertEqual(res_b.status_code, 200)
        # User B has no card, so is_edit is False and all fields are empty
        self.assertFalse(res_b.context['is_edit'])
        self.assertEqual(res_b.context['card'].owner_name, '')
        self.assertEqual(res_b.context['card'].business_name, '')
        self.assertEqual(res_b.context['card'].email, '')

        # Ensure HTML does NOT leak User A's details to User B
        html_b = res_b.content.decode('utf-8')
        self.assertNotIn('Alice Archer', html_b)
        self.assertNotIn('Alpha Apex Consulting', html_b)
        self.assertNotIn('alice@alphaapex.com', html_b)

        # 3. User B cannot access or edit User A's card directly
        res_b_tamper = self.client.get(reverse('card_edit', kwargs={'card_id': card_a.card_id}))
        self.assertEqual(res_b_tamper.status_code, 404)

        # 4. User B cannot delete User A's card
        res_b_delete = self.client.post(reverse('card_delete', kwargs={'card_id': card_a.card_id}))
        self.assertEqual(res_b_delete.status_code, 404)
        self.assertTrue(BusinessCard.objects.filter(card_id=card_a.card_id).exists())

    def test_banner_section_create_and_render(self):
        self.client.force_login(self.test_user)
        post_data = {
            'business_name': 'Solaris Products & Tech',
            'owner_name': 'David Ray',
            'banners_data': json.dumps([
                {
                    'id': 1,
                    'title': 'Flagship Tech Suite 2026',
                    'image': 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800',
                    'link': 'https://solaris.io/products'
                },
                {
                    'id': 2,
                    'title': 'Special Enterprise Promo',
                    'image': 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',
                    'link': 'https://solaris.io/enterprise'
                }
            ]),
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.get(business_name='Solaris Products & Tech')
        self.assertIn('banners_items', card.layout_config)
        self.assertEqual(len(card.layout_config['banners_items']), 2)
        self.assertEqual(card.layout_config['banners_items'][0]['title'], 'Flagship Tech Suite 2026')

        # Test builder edit GET
        edit_res = self.client.get(reverse('card_edit', kwargs={'card_id': card.card_id}))
        self.assertEqual(edit_res.status_code, 200)
        html = edit_res.content.decode('utf-8')
        self.assertIn('id="btnAddBanner"', html)
        self.assertIn('Flagship Tech Suite 2026', html)

        # Test preview GET contains banner section and items
        preview_res = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}))
        self.assertEqual(preview_res.status_code, 200)
        self.assertContains(preview_res, 'id="block-banners"')
        self.assertContains(preview_res, 'Flagship Tech Suite 2026')
        self.assertContains(preview_res, 'Special Enterprise Promo')

        # Test updating with portrait orientation
        post_data['banner_aspect'] = 'portrait'
        update_res = self.client.post(reverse('card_edit', kwargs={'card_id': card.card_id}), post_data)
        self.assertEqual(update_res.status_code, 302)
        card.refresh_from_db()
        self.assertEqual(card.layout_config['banner_aspect'], 'portrait')

        preview_portrait_res = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}))
        self.assertEqual(preview_portrait_res.status_code, 200)
        self.assertContains(preview_portrait_res, 'is-portrait')
        self.assertContains(preview_portrait_res, 'data-aspect="portrait"')

        # Test updating with square orientation
        post_data['banner_aspect'] = 'square'
        update_res_sq = self.client.post(reverse('card_edit', kwargs={'card_id': card.card_id}), post_data)
        self.assertEqual(update_res_sq.status_code, 302)
        card.refresh_from_db()
        self.assertEqual(card.layout_config['banner_aspect'], 'square')

        preview_sq_res = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}))
        self.assertEqual(preview_sq_res.status_code, 200)
        self.assertContains(preview_sq_res, 'is-square')
        self.assertContains(preview_sq_res, 'data-aspect="square"')

    def test_builder_clean_buttons_and_share_popup(self):
        self.client.force_login(self.test_user)
        # Create a card for test_user
        card = BusinessCard.objects.create(
            user=self.test_user,
            business_name='Aura Innovations',
            owner_name='Aura Leader'
        )

        # 1. Verify card_edit does NOT have Delete Card or Cancel / Back to Preview buttons
        edit_res = self.client.get(reverse('card_edit', kwargs={'card_id': card.card_id}))
        self.assertEqual(edit_res.status_code, 200)
        edit_html = edit_res.content.decode('utf-8')
        self.assertNotIn('Delete Card', edit_html)
        self.assertNotIn('Cancel / Back to Preview', edit_html)
        self.assertIn('Update & Save Business Card', edit_html)

        # 2. Verify share popup modal with Share Link and Send QR Code exists in preview/card
        preview_res = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}))
        self.assertEqual(preview_res.status_code, 200)
        self.assertContains(preview_res, 'id="cardShareBottomSheet"')
        self.assertContains(preview_res, 'id="shareTabContentLink"')
        self.assertContains(preview_res, 'id="shareTabContentQr"')
        self.assertContains(preview_res, 'Share Link')
        self.assertContains(preview_res, 'Send QR Code')

    def test_dashboard_and_lead_tracking_integration(self):
        """
        Verify real-time lead capture, analytics event tracking, and the new
        Qkbiz-style BrandNest Admin Dashboard views connected to database models.
        """
        self.client.force_login(self.test_user)

        # 1. Create a business card
        card = BusinessCard.objects.create(
            user=self.test_user,
            business_name='Medowa Ventures',
            owner_name='Riyaz Hakkim',
            views_count=25
        )

        # 2. Test visitor lead submission via public card endpoint
        lead_payload = {
            'name': 'Client Inquirer',
            'email': 'inquirer@globaltech.com',
            'phone': '+91 9876543210',
            'message': 'Hi, I would like to request an enterprise quote.'
        }
        lead_res = self.client.post(
            reverse('record_card_lead', kwargs={'slug': card.slug}),
            data=json.dumps(lead_payload),
            content_type='application/json'
        )
        self.assertEqual(lead_res.status_code, 200)
        from apps.cards.models import CardLead, CardAnalyticsEvent
        self.assertEqual(CardLead.objects.filter(card=card).count(), 1)
        lead = CardLead.objects.get(card=card)
        self.assertEqual(lead.name, 'Client Inquirer')

        # 3. Test event tracking endpoint
        track_res = self.client.post(reverse('record_card_event', kwargs={'slug': card.slug, 'event_type': 'share_click'}))
        self.assertEqual(track_res.status_code, 200)
        self.assertTrue(CardAnalyticsEvent.objects.filter(card=card, event_type='share_click').exists())

        # 4. Test Dashboard Overview
        self.test_user.is_staff = True
        self.test_user.save()
        overview_res = self.client.get(reverse('dashboard_overview'))
        self.assertEqual(overview_res.status_code, 200)
        self.assertContains(overview_res, 'Medowa Ventures')
        self.assertContains(overview_res, 'Page Views')
        self.assertContains(overview_res, 'Leads Generated')

        # 5. Test Web Cards View
        cards_res = self.client.get(reverse('dashboard_cards'))
        self.assertEqual(cards_res.status_code, 200)
        self.assertContains(cards_res, 'Web Cards')
        self.assertContains(cards_res, 'Medowa Ventures')

        # 6. Test QR Codes View
        qr_res = self.client.get(reverse('dashboard_qr_codes'))
        self.assertEqual(qr_res.status_code, 200)
        self.assertContains(qr_res, 'QR Codes')
        self.assertContains(qr_res, 'Medowa Ventures')

        # 7. Test Contacts View
        contacts_res = self.client.get(reverse('dashboard_contacts'))
        self.assertEqual(contacts_res.status_code, 200)
        self.assertContains(contacts_res, 'Client Inquirer')
        self.assertContains(contacts_res, 'inquirer@globaltech.com')

        # 8. Test Messages View
        msgs_res = self.client.get(reverse('dashboard_messages'))
        self.assertEqual(msgs_res.status_code, 200)
        self.assertContains(msgs_res, 'Client Inquirer')
        self.assertContains(msgs_res, 'enterprise quote')

        # 9. Test NFC Tags View & mode update
        from apps.cards.models import NFCTag
        tag = NFCTag.objects.create(card=card, nfc_mode='web_card')
        nfc_res = self.client.get(reverse('dashboard_nfc'))
        self.assertEqual(nfc_res.status_code, 200)
        self.assertContains(nfc_res, tag.unique_code)

        # Update NFC mode
        update_mode_res = self.client.post(reverse('dashboard_nfc_update', kwargs={'tag_id': tag.id}), {'nfc_mode': 'save_contact'})
        self.assertEqual(update_mode_res.status_code, 302)
        tag.refresh_from_db()
        self.assertEqual(tag.nfc_mode, 'save_contact')

        # 10. Test Teams View & Add Team
        teams_res = self.client.get(reverse('dashboard_teams'))
        self.assertEqual(teams_res.status_code, 200)
        add_team_res = self.client.post(reverse('dashboard_teams_add'), {'name': 'Operations Team'})
        self.assertEqual(add_team_res.status_code, 302)
        from apps.cards.models import Team
        self.assertTrue(Team.objects.filter(name='Operations Team').exists())

        # 11. Test Leads View & Export
        leads_res = self.client.get(reverse('dashboard_leads'))
        self.assertEqual(leads_res.status_code, 200)
        self.assertContains(leads_res, 'Client Inquirer')

        export_res = self.client.get(reverse('dashboard_leads_export'))
        self.assertEqual(export_res.status_code, 200)
        self.assertEqual(export_res['Content-Type'], 'text/csv')
        self.assertIn('Client Inquirer', export_res.content.decode('utf-8'))

        # 12. Test Settings View & Save Business Info
        settings_res = self.client.get(reverse('dashboard_settings'))
        self.assertEqual(settings_res.status_code, 200)
        save_biz_res = self.client.post(reverse('dashboard_settings_save_business'), {
            'company_name': 'MEDOWA GLOBAL VENTURES',
            'tax_id': '32AAVCM2073R1ZQ',
            'website': 'www.medowaglobal.com',
            'total_employees': '15'
        })
        self.assertEqual(save_biz_res.status_code, 302)
        from apps.cards.models import CompanySettings
        comp = CompanySettings.objects.first()
        self.assertEqual(comp.company_name, 'MEDOWA GLOBAL VENTURES')
        self.assertEqual(comp.tax_id, '32AAVCM2073R1ZQ')

        # 13. Test Wallet Pass Designer View
        pass_res = self.client.get(reverse('dashboard_wallet_pass'))
        self.assertEqual(pass_res.status_code, 200)
        self.assertContains(pass_res, 'Wallet Pass')
        self.assertContains(pass_res, 'Add to Apple Wallet')

        # 14. Test /admin and /admin/ gateway and dedicated admin login
        admin_c = Client()
        res_admin = admin_c.get('/admin', follow=True)
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn('/admin/login/', res_admin.request['PATH_INFO'])

        res_admin_slash = admin_c.get('/admin/', follow=True)
        self.assertEqual(res_admin_slash.status_code, 200)
        self.assertIn('/admin/login/', res_admin_slash.request['PATH_INFO'])

        # Create superuser in test db and log in
        from django.contrib.auth.models import User
        User.objects.create_superuser('admin_unit', 'admin_unit@brandnest.io', 'BrandNest@2026')
        res_login = admin_c.post(reverse('admin_login'), {'username': 'admin_unit', 'password': 'BrandNest@2026'}, follow=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertIn('/dashboard/overview/', res_login.request['PATH_INFO'])

        # Test admin logout redirects to admin login, not main website
        res_logout = admin_c.get(reverse('admin_logout'), follow=True)
        self.assertEqual(res_logout.status_code, 200)
        self.assertIn('/admin/login/', res_logout.request['PATH_INFO'])

        # 15. Test Enterprise Super Admin Suite
        ent_c = Client()
        # Unauthenticated redirect
        res_ent_unauth = ent_c.get(reverse('enterprise_admin_overview'), follow=False)
        self.assertEqual(res_ent_unauth.status_code, 302)
        self.assertIn('/admin/login/', res_ent_unauth['Location'])

        # Login with super admin
        ent_c.post(reverse('admin_login'), {'username': 'admin_unit', 'password': 'BrandNest@2026'}, follow=True)

        # Overview
        res_overview = ent_c.get(reverse('enterprise_admin_overview'))
        self.assertEqual(res_overview.status_code, 200)
        self.assertContains(res_overview, 'Enterprise Platform Overview')

        # Create Enterprise Company
        from apps.cards.models import EnterpriseCompany
        res_new_comp = ent_c.post(reverse('enterprise_admin_company_create'), {
            'name': 'Apex Global Enterprise',
            'head_name': 'Marcus Vance',
            'email': 'marcus@apex.com',
            'phone': '+1 555 0199',
            'card_quota': 15,
            'plan_tier': 'Best Value (15 Cards)',
            'tax_id': 'GST992019',
        }, follow=True)
        self.assertEqual(res_new_comp.status_code, 200)
        comp_apex = EnterpriseCompany.objects.filter(name='Apex Global Enterprise').first()
        self.assertIsNotNone(comp_apex)
        self.assertEqual(comp_apex.card_quota, 15)

        # Companies View
        res_comps = ent_c.get(reverse('enterprise_admin_companies'))
        self.assertEqual(res_comps.status_code, 200)
        self.assertContains(res_comps, 'Apex Global Enterprise')

        # Issue Employee Card
        res_issue = ent_c.post(reverse('enterprise_admin_card_issue'), {
            'company_id': comp_apex.id,
            'owner_name': 'Marcus Vance',
            'role_title': 'Managing Partner',
            'email': 'marcus@apex.com',
            'phone': '+1 555 0199',
        }, follow=True)
        self.assertEqual(res_issue.status_code, 200)
        self.assertEqual(comp_apex.cards_used, 1)

        # Cards View
        res_ent_cards = ent_c.get(reverse('enterprise_admin_cards'))
        self.assertEqual(res_ent_cards.status_code, 200)
        self.assertContains(res_ent_cards, 'Marcus Vance')

        # Quota Top-Up
        res_quota = ent_c.post(reverse('enterprise_admin_company_quota', kwargs={'company_id': comp_apex.id}), {
            'card_quota': 25,
            'plan_tier': 'Custom 25 Cards',
        }, follow=True)
        self.assertEqual(res_quota.status_code, 200)
        comp_apex.refresh_from_db()
        self.assertEqual(comp_apex.card_quota, 25)

        # Leads View & Export
        res_ent_leads = ent_c.get(reverse('enterprise_admin_leads'))
        self.assertEqual(res_ent_leads.status_code, 200)

        res_ent_export = ent_c.get(reverse('enterprise_admin_leads_export'))
        self.assertEqual(res_ent_export.status_code, 200)
        self.assertEqual(res_ent_export['Content-Type'], 'text/csv')

        # Billing View
        res_billing = ent_c.get(reverse('enterprise_admin_billing'))
        self.assertEqual(res_billing.status_code, 200)
        self.assertContains(res_billing, 'Enterprise Bundles')

    def test_personal_card_razorpay_checkout_flow(self):
        """
        Verify the end-to-end personal business card builder flow:
        1. Choice page shows ₹499 Personal Use option.
        2. Personal builder loads with Razorpay gateway modal.
        3. Form submission with ₹499 Razorpay demo payment captures receipt and redirects to card preview.
        4. Card preview renders verified payment status, live phone frame, and QR sharing.
        """
        self.client.force_login(self.test_user)

        # 1. Chooser page
        choose_res = self.client.get(reverse('card_choose_plan'))
        self.assertEqual(choose_res.status_code, 200)
        self.assertContains(choose_res, 'For Personal Use')
        self.assertContains(choose_res, '₹499')
        self.assertContains(choose_res, reverse('card_builder'))

        # 2. Builder page
        builder_res = self.client.get(reverse('card_builder') + '?new=1')
        self.assertEqual(builder_res.status_code, 200)
        self.assertContains(builder_res, 'razorpayDemoModal')
        self.assertContains(builder_res, 'Generate Business Card')

        # 3. Submit card generation with Razorpay demo payment
        card_data = {
            'business_name': 'Horizon Studio Co',
            'owner_name': 'Aarav Sharma',
            'role_title': 'Principal Architect',
            'email': 'aarav@horizonstudio.in',
            'phone': '+91 9845012345',
            'address': 'MG Road, Bangalore, India',
            'razorpay_payment_id': 'pay_demo_test_998877',
            'razorpay_amount': '499',
            'razorpay_method': 'UPI (Google Pay)',
            'payment_verified': 'true',
        }
        submit_res = self.client.post(reverse('card_builder'), card_data)
        self.assertEqual(submit_res.status_code, 302)

        # 4. Check database card & payment receipt
        card = BusinessCard.objects.filter(business_name='Horizon Studio Co', user=self.test_user).first()
        self.assertIsNotNone(card)
        self.assertEqual(submit_res['Location'], reverse('card_preview', kwargs={'card_id': card.card_id}))
        receipt = card.layout_config.get('payment_receipt', {})
        self.assertEqual(receipt.get('payment_id'), 'pay_demo_test_998877')
        self.assertEqual(receipt.get('amount'), 499)

        # 5. Follow redirect to card preview
        preview_res = self.client.get(submit_res['Location'])
        self.assertEqual(preview_res.status_code, 200)
        self.assertContains(preview_res, 'Horizon Studio Co')
        self.assertContains(preview_res, 'Paid ₹499')
        self.assertContains(preview_res, 'Razorpay Demo')
        self.assertContains(preview_res, 'pay_demo_test_998877')
        self.assertContains(preview_res, 'Download QR')

    def test_personal_card_and_nfc_bundle_checkout_flow(self):
        """
        Verify the ₹999 Business Card + Physical NFC Smart Card flow:
        1. Builder page contains the NFC customizer studio modal and hardware bundle option.
        2. Form submit with ₹999 Razorpay demo payment and customized front/back details.
        3. Card saves with nfc_card metadata and NFCTag record.
        4. Preview page displays live card AND custom physical NFC card with flip support.
        """
        self.client.force_login(self.test_user)

        # 1. Builder page contains NFC studio elements
        builder_res = self.client.get(reverse('card_builder') + '?new=1')
        self.assertEqual(builder_res.status_code, 200)
        self.assertContains(builder_res, 'nfcStudioModal')
        self.assertContains(builder_res, 'btnCustomizeNfcCard')
        self.assertContains(builder_res, 'Business Card + NFC Card')
        self.assertContains(builder_res, '₹999')

        # 2. Submit card generation with ₹999 NFC Hardware Bundle
        card_data = {
            'business_name': 'Astra Dynamics Tech',
            'owner_name': 'Vikram Malhotra',
            'role_title': 'Managing Director',
            'email': 'vikram@astradynamics.in',
            'phone': '+91 9988776655',
            'address': 'Cyber City, Hyderabad, India',
            'razorpay_payment_id': 'pay_demo_nfc_bundle_778899',
            'razorpay_amount': '999',
            'razorpay_method': 'UPI (PhonePe)',
            'payment_verified': 'true',
            'nfc_ordered': 'true',
            'nfc_theme': 'obsidian_black',
            'nfc_name': 'Vikram Malhotra',
            'nfc_designation': 'Managing Director',
            'nfc_foil': 'gold',
            'nfc_website': 'www.astradynamics.in',
            'nfc_company_name': 'Astra Dynamics Tech',
            'nfc_pass_tagline': 'Executive Smart Pass',
            'nfc_chip_spec': 'NTAG216 · 888 BYTES',
            'nfc_back_tagline': 'SMART CONTACTLESS TOUCHPOINT',
            'nfc_tap_hint': 'Tap against any iPhone or Android phone',
            'nfc_back_badge': 'Direct NFC Tap',
            'nfc_logo_data': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            'nfc_logo_scale': '1.3',
            'nfc_positions': '{"front_name_role":{"x":10,"y":5},"back_logo":{"x":0,"y":-8}}',
        }
        submit_res = self.client.post(reverse('card_builder'), card_data)
        self.assertEqual(submit_res.status_code, 302)

        # 3. Check database record
        card = BusinessCard.objects.filter(business_name='Astra Dynamics Tech', user=self.test_user).first()
        self.assertIsNotNone(card)
        self.assertEqual(submit_res['Location'], reverse('card_preview', kwargs={'card_id': card.card_id}))

        receipt = card.layout_config.get('payment_receipt', {})
        self.assertEqual(receipt.get('payment_id'), 'pay_demo_nfc_bundle_778899')
        self.assertEqual(receipt.get('amount'), 999)

        nfc_conf = card.layout_config.get('nfc_card', {})
        self.assertTrue(nfc_conf.get('ordered'))
        self.assertEqual(nfc_conf.get('theme'), 'obsidian_black')
        self.assertEqual(nfc_conf.get('name'), 'Vikram Malhotra')
        self.assertEqual(nfc_conf.get('designation'), 'Managing Director')
        self.assertEqual(nfc_conf.get('website'), 'www.astradynamics.in')
        self.assertEqual(nfc_conf.get('pass_tagline'), 'Executive Smart Pass')
        self.assertEqual(nfc_conf.get('tap_hint'), 'Tap against any iPhone or Android phone')
        self.assertEqual(nfc_conf.get('logo_scale'), '1.3')

        # 4. Preview page rendering
        preview_res = self.client.get(submit_res['Location'])
        self.assertEqual(preview_res.status_code, 200)
        self.assertContains(preview_res, 'Astra Dynamics Tech')
        self.assertContains(preview_res, 'Paid ₹999')
        self.assertContains(preview_res, 'Your Custom Smart NFC Physical Card')
        self.assertContains(preview_res, 'Vikram Malhotra')
        self.assertContains(preview_res, 'Managing Director')
        self.assertContains(preview_res, 'www.astradynamics.in')
        self.assertContains(preview_res, 'Executive Smart Pass')
        self.assertContains(preview_res, 'Tap against any iPhone or Android phone')
        self.assertContains(preview_res, 'Flip NFC Card (Front / Back)')

    def test_enterprise_nfc_bundle_checkout_and_quota(self):
        """
        Verify purchasing an Enterprise Digital + NFC Card Hardware bundle (5_nfc, 10_nfc, 15_nfc):
        1. Checks checkout page renders all Digital and NFC bundle tiers.
        2. Submits 5_nfc bundle purchase (₹2499).
        3. Confirms UserPlan has card_limit=5, nfc_card_limit=5, total_paid=2499.
        """
        self.client.force_login(self.test_user)
        res = self.client.get(reverse('enterprise_checkout'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '5 Business Cards + 5 NFC Cards')
        self.assertContains(res, '10 Business Cards + 10 NFC Cards')
        self.assertContains(res, '15 Business Cards + 15 NFC Cards')
        self.assertContains(res, '₹2499')
        self.assertContains(res, '₹4499')
        self.assertContains(res, '₹5999')

        # Purchase 5_nfc bundle
        post_res = self.client.post(reverse('enterprise_checkout'), {'bundle_size': '5_nfc'})
        self.assertEqual(post_res.status_code, 302)
        self.assertEqual(post_res['Location'], reverse('card_list'))

        plan = UserPlan.objects.get(user=self.test_user)
        self.assertEqual(plan.plan_type, 'enterprise')
        self.assertEqual(plan.card_limit, 5)
        self.assertEqual(plan.nfc_card_limit, 5)
        self.assertEqual(plan.total_paid, 2499)

    def test_enterprise_ceo_add_user_and_employee_free_generation_flow(self):
        """
        Verify the complete Enterprise CEO delegation workflow:
        1. CEO purchases 5_nfc bundle (5 Cards + 5 NFC).
        2. CEO views /cards/ and sees 'Add User' and 'Create My Business Card' options.
        3. CEO adds an employee via /enterprise/add-user/ with email and password.
        4. Employee logs in via credentials/link and is redirected to card builder.
        5. Employee generates their Digital + NFC card for FREE (₹0, covered by CEO's plan).
        6. Card is saved, live preview opens, and card status reflects in CEO's team list.
        """
        # 1. Setup CEO with 5_nfc bundle
        self.client.force_login(self.test_user)
        self.client.post(reverse('enterprise_checkout'), {'bundle_size': '5_nfc'})
        ceo_plan = UserPlan.objects.get(user=self.test_user)
        ceo_plan.company_name = 'Apex Global Corp'
        ceo_plan.save()

        # 2. Check /cards/ page for CEO buttons
        list_res = self.client.get(reverse('card_list'))
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, 'Add User')
        self.assertContains(list_res, 'Create My Business Card')
        self.assertContains(list_res, 'Team Members &amp; Employee Card Slots')
        self.assertContains(list_res, 'Apex Global Corp')

        # 3. CEO adds an employee user
        add_user_res = self.client.post(reverse('enterprise_add_user'), {
            'full_name': 'Rohan Mehta',
            'email': 'rohan@apexcorp.com',
            'password': 'RohanSecurePass123',
            'employee_role': 'VP of Engineering',
        })
        self.assertEqual(add_user_res.status_code, 302)
        self.assertEqual(add_user_res['Location'], reverse('card_list'))

        # Verify employee user and plan created in DB
        from django.contrib.auth.models import User
        emp_user = User.objects.get(email='rohan@apexcorp.com')
        self.assertEqual(emp_user.first_name, 'Rohan Mehta')
        self.assertTrue(emp_user.check_password('RohanSecurePass123'))

        emp_plan = UserPlan.objects.get(user=emp_user)
        self.assertEqual(emp_plan.enterprise_parent, self.test_user)
        self.assertEqual(emp_plan.employee_role, 'VP of Engineering')
        self.assertEqual(emp_plan.company_name, 'Apex Global Corp')
        self.assertEqual(emp_plan.initial_password, 'RohanSecurePass123')
        self.assertEqual(emp_plan.nfc_card_limit, 1)

        # 4. Check CEO sees employee in team list
        list_after_add = self.client.get(reverse('card_list'))
        self.assertEqual(list_after_add.status_code, 200)
        self.assertContains(list_after_add, 'Rohan Mehta')
        self.assertContains(list_after_add, 'rohan@apexcorp.com')
        self.assertContains(list_after_add, 'VP of Engineering')
        self.assertContains(list_after_add, 'Pending Creation')

        # 5. Employee logs in via shared link
        self.client.logout()
        login_page_res = self.client.get(f"{reverse('login')}?email=rohan@apexcorp.com&next={reverse('card_builder')}")
        self.assertEqual(login_page_res.status_code, 200)
        self.assertContains(login_page_res, 'value="rohan@apexcorp.com"')

        login_res = self.client.post(reverse('login'), {
            'login_identifier': 'rohan@apexcorp.com',
            'password': 'RohanSecurePass123',
            'next': reverse('card_builder'),
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertEqual(login_res['Location'], reverse('card_builder'))

        # 6. Employee opens card builder - sees Free / Pre-paid corporate pricing
        builder_res = self.client.get(reverse('card_builder'))
        self.assertEqual(builder_res.status_code, 200)
        self.assertContains(builder_res, 'Covered by Apex Global Corp')
        self.assertContains(builder_res, 'PRE-PAID (FREE)')

        # 7. Employee generates card without paying any Razorpay amount (FREE generation)
        card_post_data = {
            'business_name': 'Apex Global Corp',
            'owner_name': 'Rohan Mehta',
            'role_title': 'VP of Engineering',
            'email': 'rohan@apexcorp.com',
            'phone': '+91 9876543210',
            'nfc_ordered': 'true',
            'nfc_theme': 'obsidian_black',
            'nfc_name': 'Rohan Mehta',
            'nfc_designation': 'VP of Engineering',
        }
        submit_res = self.client.post(reverse('card_builder'), card_post_data)
        self.assertEqual(submit_res.status_code, 302)

        # Verify card created in DB
        emp_card = BusinessCard.objects.get(user=emp_user)
        self.assertEqual(emp_card.owner_name, 'Rohan Mehta')
        self.assertEqual(submit_res['Location'], reverse('card_preview', kwargs={'card_id': emp_card.card_id}))

        # Verify receipt is Enterprise Pre-paid (₹0) and NFC card is ordered
        receipt = emp_card.layout_config.get('payment_receipt', {})
        self.assertEqual(receipt.get('gateway'), 'Enterprise Pre-paid')
        self.assertEqual(receipt.get('amount'), 0)
        self.assertTrue(emp_card.layout_config.get('nfc_card', {}).get('ordered'))

        # 8. CEO logs back in and checks that employee status is now 'Card Built'
        self.client.force_login(self.test_user)
        ceo_list_res = self.client.get(reverse('card_list'))
        self.assertEqual(ceo_list_res.status_code, 200)
        self.assertContains(ceo_list_res, 'Card Built')
        self.assertContains(ceo_list_res, '1 of 5 Business Cards Built')

    def test_enterprise_digital_vs_nfc_plans_and_navigation(self):
        """
        Verify:
        1. When CEO chooses Digital-only plan (has_nfc=False):
           - Only "Generate Business Card" is shown.
           - NO Option 2 (Business Card + NFC Card / Generate NFC Card) is shown.
        2. When CEO chooses Digital+NFC plan (has_nfc=True):
           - Both "Generate Business Card" and "Generate NFC Card" are shown.
        3. Employee logs in from home page (no next param) -> redirects to card_list if card exists,
           or card_builder if card not created yet.
        4. Landing navbar contains 'My Cards' when logged in.
        """
        # A. Digital-only plan (5 cards, has_nfc=False)
        ceo_digital = User.objects.create_user(username='ceo_digital', email='ceo_digital@example.com', password='password123')
        UserPlan.objects.create(
            user=ceo_digital,
            plan_type='enterprise',
            is_ceo=True,
            company_name='Digital Innovators',
            card_limit=5,
            nfc_card_limit=0
        )
        self.client.force_login(ceo_digital)
        builder_get = self.client.get(reverse('card_builder'))
        self.assertEqual(builder_get.status_code, 200)
        self.assertContains(builder_get, 'Generate Business Card')
        self.assertNotContains(builder_get, 'Business Card + NFC Card')
        self.assertNotContains(builder_get, 'Generate NFC Card')

        # Add employee under digital CEO
        add_emp_res = self.client.post(reverse('enterprise_add_user'), {
            'full_name': 'Aarav Kumar',
            'email': 'aarav@digital.com',
            'password': 'password123',
            'employee_role': 'Product Lead',
        })
        self.assertEqual(add_emp_res.status_code, 302)
        emp_digital = User.objects.get(email='aarav@digital.com')

        # Employee logs in to builder: should see ONLY "Generate Business Card"
        self.client.force_login(emp_digital)
        emp_builder = self.client.get(reverse('card_builder'))
        self.assertEqual(emp_builder.status_code, 200)
        self.assertContains(emp_builder, 'Generate Business Card')
        self.assertNotContains(emp_builder, 'Business Card + NFC Card')
        self.assertNotContains(emp_builder, 'Generate NFC Card')

        # Employee creates card -> redirects to card_preview
        create_res = self.client.post(reverse('card_builder'), {
            'business_name': 'Digital Innovators',
            'owner_name': 'Aarav Kumar',
        })
        self.assertEqual(create_res.status_code, 302)
        self.assertIn('/card/preview/', create_res['Location'])

        # Now employee visits login/home -> login without next redirects to card_edit because card exists
        emp_created_card = BusinessCard.objects.get(user=emp_digital)
        self.client.logout()
        login_res = self.client.post(reverse('login'), {
            'login_identifier': 'aarav@digital.com',
            'password': 'password123'
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertEqual(login_res['Location'], reverse('card_edit', kwargs={'card_id': emp_created_card.card_id}))

        # Employee checks landing page: has 'My Cards' in navbar
        landing_res = self.client.get(reverse('landing'))
        self.assertEqual(landing_res.status_code, 200)
        self.assertContains(landing_res, 'My Cards')

        # B. NFC Plan (5 cards + 5 NFC, has_nfc=True)
        ceo_nfc = User.objects.create_user(username='ceo_nfc', email='ceo_nfc@example.com', password='password123')
        UserPlan.objects.create(
            user=ceo_nfc,
            plan_type='enterprise',
            is_ceo=True,
            company_name='NFC Tech Corp',
            card_limit=5,
            nfc_card_limit=5
        )
        self.client.force_login(ceo_nfc)
        builder_nfc_get = self.client.get(reverse('card_builder'))
        self.assertEqual(builder_nfc_get.status_code, 200)
        self.assertContains(builder_nfc_get, 'Generate Business Card')
        self.assertContains(builder_nfc_get, 'Business Card + NFC Card')
        self.assertContains(builder_nfc_get, 'Generate NFC Card')

    def test_personal_user_signup_pay_signout_login_edit_without_paying(self):
        """
        Verify:
        1. A user signs up.
        2. Creates personal card and pays money (₹499).
        3. Signs out.
        4. Logs back in with the same credentials -> directed to his business card (card_edit).
        5. The page displays edit mode with "Save & Update Business Card (Free)" and no ₹499/₹999 purchase buttons.
        6. Submitting updates saves successfully with ZERO payment requested and redirects to card_preview.
        """
        # 1. Sign up
        signup_res = self.client.post(reverse('signup'), {
            'full_name': 'Kavya Sharma',
            'email': 'kavya@personalbrand.in',
            'password': 'MyStrongPassword123!',
            'confirm_password': 'MyStrongPassword123!'
        })
        self.assertEqual(signup_res.status_code, 302)
        kavya = User.objects.get(email='kavya@personalbrand.in')

        # 2. Kavya creates card and pays ₹499 via Razorpay demo
        card_data = {
            'business_name': 'Kavya Design Studio',
            'owner_name': 'Kavya Sharma',
            'role_title': 'Principal UI Designer',
            'email': 'kavya@personalbrand.in',
            'phone': '+91 9988776655',
            'razorpay_payment_id': 'pay_demo_kavya12345',
            'razorpay_amount': '499',
            'razorpay_method': 'UPI (Demo)'
        }
        create_res = self.client.post(reverse('card_builder'), card_data)
        self.assertEqual(create_res.status_code, 302)
        card = BusinessCard.objects.get(user=kavya)
        self.assertEqual(card.business_name, 'Kavya Design Studio')
        self.assertEqual(card.layout_config['payment_receipt']['amount'], 499)

        # 3. Kavya signs out
        self.client.logout()

        # 4. Kavya logs in from the homepage/login page
        login_res = self.client.post(reverse('login'), {
            'login_identifier': 'kavya@personalbrand.in',
            'password': 'MyStrongPassword123!'
        })
        self.assertEqual(login_res.status_code, 302)
        # Directly directed to her business card in edit mode
        expected_edit_url = reverse('card_edit', kwargs={'card_id': card.card_id})
        self.assertEqual(login_res['Location'], expected_edit_url)

        # 5. Open edit page -> verify edit UI (Active & Paid, no ₹499/₹999 checkout)
        edit_page = self.client.get(expected_edit_url)
        self.assertEqual(edit_page.status_code, 200)
        self.assertContains(edit_page, 'Business Card Active &amp; Paid (Yearly Plan)')
        self.assertIn('Update & Save Business Card', edit_page.content.decode('utf-8'))
        self.assertNotContains(edit_page, 'Generate Business Card (₹499)')
        self.assertNotContains(edit_page, 'Design NFC Card &amp; Pay (₹999)')

        # 6. Kavya updates her card (e.g. changes role and phone) WITHOUT any payment id
        update_data = {
            'business_name': 'Kavya Design Studio',
            'owner_name': 'Kavya Sharma',
            'role_title': 'Founder & Creative Director',
            'email': 'kavya@personalbrand.in',
            'phone': '+91 9123456780',
        }
        update_res = self.client.post(expected_edit_url, update_data)
        self.assertEqual(update_res.status_code, 302)
        self.assertEqual(update_res['Location'], reverse('card_preview', kwargs={'card_id': card.card_id}))

        # Verify DB updated and payment receipt preserved
        card.refresh_from_db()
        self.assertEqual(card.tagline, 'Founder & Creative Director')
        self.assertEqual(card.phone, '+91 9123456780')
        self.assertEqual(card.layout_config['payment_receipt']['payment_id'], 'pay_demo_kavya12345')

    def test_yearly_plan_expiration_tracking_and_email_notification(self):
        """
        Verify that Personal and Enterprise plans are recorded as yearly renewable plans
        with a 365-day expiration cycle, and automated reminder emails are dispatched
        to the user's/CEO's Gmail address.
        """
        from datetime import timedelta
        from django.utils import timezone
        from django.core import mail
        from django.core.management import call_command
        from apps.cards.notifications import send_plan_expiration_email

        # 1. Personal user signup with Gmail
        rajesh = User.objects.create_user(
            username='rajesh_tech',
            email='rajesh.brand@gmail.com',
            password='PasswordRajesh123!',
            first_name='Rajesh',
            last_name='Kumar'
        )
        self.client.force_login(rajesh)

        # 2. Rajesh creates a card and pays for yearly Personal Pro + NFC
        post_data = {
            'business_name': 'Rajesh Tech Innovations',
            'owner_name': 'Rajesh Kumar',
            'role_title': 'Chief Architect',
            'email': 'rajesh.brand@gmail.com',
            'phone': '+91 9876543210',
            'razorpay_payment_id': 'pay_demo_rajesh_yearly',
            'razorpay_amount': '999',
            'nfc_ordered': 'true',
        }
        res = self.client.post(reverse('card_builder'), post_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.filter(user=rajesh).first()
        self.assertIsNotNone(card)
        receipt = card.layout_config.get('payment_receipt', {})
        self.assertEqual(receipt.get('billing_cycle'), 'yearly')
        self.assertIn('Yearly', receipt.get('plan', ''))

        # Check UserPlan
        plan = UserPlan.objects.get(user=rajesh)
        self.assertEqual(plan.plan_type, 'personal')
        self.assertEqual(plan.billing_cycle, 'yearly')
        self.assertIsNotNone(plan.effective_expires_at)
        self.assertGreaterEqual(plan.days_remaining, 360)
        self.assertEqual(plan.status_label, 'Active')

        # 3. Simulate plan expiring in 10 days
        plan.expires_at = timezone.now() + timedelta(days=10)
        plan.save()
        self.assertEqual(plan.status_label, 'Expiring Soon')
        self.assertLessEqual(plan.days_remaining, 10)

        # 4. Trigger notification helper directly
        mail.outbox.clear()
        res_email = send_plan_expiration_email(
            recipient_email=plan.user.email,
            recipient_name=plan.user.get_full_name(),
            plan_name=plan.plan_name,
            expires_at=plan.effective_expires_at,
            days_left=plan.days_remaining,
            is_enterprise=False
        )
        self.assertTrue(res_email.get('success'))
        self.assertEqual(len(mail.outbox), 1)
        sent_msg = mail.outbox[0]
        self.assertEqual(sent_msg.to, ['rajesh.brand@gmail.com'])
        self.assertIn('Expires Soon', sent_msg.subject)
        self.assertIn('Rajesh', sent_msg.body)
        self.assertIn('scheduled to expire', sent_msg.body)
        self.assertIn('Personal Pro + Physical NFC Card', sent_msg.body)

        # 5. Run management command notify_expiring_plans
        mail.outbox.clear()
        plan.last_notification_sent_at = None
        plan.save()
        call_command('notify_expiring_plans', days=30)
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['rajesh.brand@gmail.com'])

    def test_super_admin_dashboard_personal_and_enterprise_plan_views(self):
        """
        Verify that Super Admin can view Personal Plans and Enterprise Plans with details,
        view expiration countdowns, and manually send reminder notices to Gmail.
        """
        from datetime import timedelta
        from django.utils import timezone
        from django.core import mail
        from apps.cards.models import EnterpriseCompany

        # 1. Create Super Admin User
        admin_user = User.objects.create_user(
            username='super_admin_boss',
            email='admin@brandnest.io',
            password='SuperAdminPass123!',
            is_staff=True
        )
        self.client.force_login(admin_user)

        # 2. Create Personal User with paid yearly plan
        priya = User.objects.create_user(
            username='priya_designs',
            email='priya.designs@gmail.com',
            password='PriyaPassword123!',
            first_name='Priya',
            last_name='Nair'
        )
        priya_plan = UserPlan.objects.create(
            user=priya,
            plan_type='personal',
            plan_name='Personal Pro Digital (Yearly)',
            billing_cycle='yearly',
            total_paid=499,
            expires_at=timezone.now() + timedelta(days=200)
        )
        BusinessCard.objects.create(
            user=priya,
            business_name='Priya Creative Studio',
            owner_name='Priya Nair',
            email='priya.designs@gmail.com'
        )

        # 3. Create Enterprise Company + CEO with 10 cards yearly bundle
        vikram_ceo = User.objects.create_user(
            username='vikram_ceo',
            email='vikram.ceo@gmail.com',
            password='VikramCeoPass123!',
            first_name='Vikram',
            last_name='Singhania'
        )
        vikram_plan = UserPlan.objects.create(
            user=vikram_ceo,
            plan_type='enterprise',
            is_ceo=True,
            company_name='Singhania Global Tech',
            company_head_name='Vikram Singhania',
            company_email='vikram.ceo@gmail.com',
            plan_name='10 Business Cards (Yearly)',
            card_limit=10,
            billing_cycle='yearly',
            total_paid=1799,
            expires_at=timezone.now() + timedelta(days=15) # Expiring soon
        )
        EnterpriseCompany.objects.create(
            name='Singhania Global Tech',
            head_name='Vikram Singhania',
            email='vikram.ceo@gmail.com',
            plan_tier='10 Business Cards (Yearly)',
            card_quota=10,
            total_paid=1799,
            billing_cycle='yearly',
            expires_at=vikram_plan.expires_at
        )

        # 4. Super Admin visits Personal Plans view
        res_personal = self.client.get(reverse('enterprise_admin_plans'), {'view': 'personal'})
        self.assertEqual(res_personal.status_code, 200)
        self.assertContains(res_personal, 'Personal Plan Subscribers (Yearly Renewable)')
        self.assertContains(res_personal, 'priya.designs@gmail.com')
        self.assertContains(res_personal, 'Priya Creative Studio')
        self.assertContains(res_personal, 'Personal Pro Digital (Yearly)')
        self.assertContains(res_personal, 'Send Notice')

        # 5. Super Admin visits Enterprise Plans view
        res_ent = self.client.get(reverse('enterprise_admin_plans'), {'view': 'enterprise'})
        self.assertEqual(res_ent.status_code, 200)
        self.assertContains(res_ent, 'Enterprise Corporate Accounts &amp; CEOs')
        self.assertContains(res_ent, 'Singhania Global Tech')
        self.assertContains(res_ent, 'vikram.ceo@gmail.com')
        self.assertContains(res_ent, '10 Business Cards (Yearly)')
        self.assertContains(res_ent, 'Notice to CEO')

        # 6. Super Admin clicks Send Notice to CEO Gmail
        mail.outbox.clear()
        post_reminder = self.client.post(reverse('enterprise_admin_send_reminder'), {
            'plan_id': vikram_plan.id,
            'view_type': 'enterprise'
        })
        self.assertEqual(post_reminder.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['vikram.ceo@gmail.com'])
        self.assertIn('Singhania', mail.outbox[0].body)
        self.assertIn('Expires Soon', mail.outbox[0].subject)

        # Verify last_notification_sent_at updated in DB
        vikram_plan.refresh_from_db()
        self.assertIsNotNone(vikram_plan.last_notification_sent_at)

    def test_nfc_card_order_admin_notification_printing_and_status_tracking(self):
        """
        Verify:
        1. When a user creates/pays for an NFC card, the Super Admin receives an email notification with design and link.
        2. Super admin console /enterprise-admin/nfc-orders/ lists the card with design details.
        3. Super admin updates status to 'Shipped' with tracking info, client receives email notification.
        4. Client's card_preview page shows updated status 'Shipped' and tracking info.
        5. Print sheet /enterprise-admin/nfc-orders/print/<card_id>/ renders production sheet.
        """
        from django.core import mail

        # 1. User orders Personal Pro + NFC card
        user = User.objects.create_user(
            username='arjun_nfc',
            email='arjun.innovations@gmail.com',
            password='ArjunPassword123!',
            first_name='Arjun',
            last_name='Reddy'
        )
        self.client.force_login(user)

        mail.outbox.clear()
        card_data = {
            'business_name': 'Arjun Robotics Labs',
            'owner_name': 'Arjun Reddy',
            'role_title': 'Director of Robotics',
            'email': 'arjun.innovations@gmail.com',
            'phone': '+91 9988776655',
            'website': 'https://arjunrobotics.in',
            'razorpay_payment_id': 'pay_demo_arjun_nfc',
            'razorpay_amount': '999',
            'nfc_ordered': 'true',
            'nfc_theme': 'obsidian_black',
            'nfc_foil': 'gold',
            'nfc_name': 'Arjun Reddy',
            'nfc_designation': 'Director of Robotics',
            'nfc_company_name': 'Arjun Robotics Labs',
            'nfc_website': 'www.arjunrobotics.in',
        }
        res = self.client.post(reverse('card_builder'), card_data)
        self.assertEqual(res.status_code, 302)

        card = BusinessCard.objects.filter(user=user).first()
        self.assertIsNotNone(card)

        # Verify Super Admin received email notification with design and link
        self.assertGreaterEqual(len(mail.outbox), 2)
        admin_emails = [m for m in mail.outbox if 'admin@brandnest.io' in m.to or 'SUPER ADMIN' in m.body or 'New Physical NFC' in m.subject]
        self.assertTrue(len(admin_emails) > 0)
        admin_email = admin_emails[0]
        self.assertIn('Physical NFC Card Order', admin_email.subject)
        self.assertIn('Arjun Robotics Labs', admin_email.subject)
        self.assertIn('Obsidian Black', admin_email.body)
        self.assertIn('Gold', admin_email.body)
        self.assertIn(card.share_url, admin_email.body)

        # Verify Client received Order Placed confirmation email to their login/signup email
        client_order_emails = [m for m in mail.outbox if 'arjun.innovations@gmail.com' in m.to]
        self.assertTrue(len(client_order_emails) > 0)
        client_order_email = client_order_emails[0]
        self.assertIn('Order Placed', client_order_email.subject)
        self.assertIn('Physical Contactless NFC Card', client_order_email.subject)
        self.assertIn('Arjun Reddy', client_order_email.body)
        self.assertIn('Obsidian Black', client_order_email.body)

        # 2. Super Admin logs in
        admin_user = User.objects.create_user(
            username='nfc_super_admin',
            email='admin@brandnest.io',
            password='AdminPassword123!',
            is_staff=True
        )
        self.client.force_login(admin_user)

        # 3. Super Admin views Personal NFC orders console (/dashboard/nfc/)
        personal_orders_page = self.client.get(reverse('dashboard_nfc'))
        self.assertEqual(personal_orders_page.status_code, 200)
        self.assertContains(personal_orders_page, 'Arjun Robotics Labs')
        self.assertContains(personal_orders_page, 'Arjun Reddy')
        self.assertContains(personal_orders_page, 'arjun.innovations@gmail.com')
        self.assertContains(personal_orders_page, 'Print Sheet')

        # Personal order must NOT show in Enterprise NFC orders console
        ent_orders_page = self.client.get(reverse('enterprise_admin_nfc_orders'))
        self.assertEqual(ent_orders_page.status_code, 200)
        self.assertNotIn(card, ent_orders_page.context['orders'])

        # 4. Super Admin updates status to 'Shipped' with tracking details from Personal Dashboard
        mail.outbox.clear()
        update_res = self.client.post(
            reverse('dashboard_nfc_status_update', kwargs={'card_id': card.card_id}),
            {
                'status': 'Shipped',
                'tracking_info': 'BlueDart AW77889900'
            }
        )
        self.assertEqual(update_res.status_code, 302)

        card.refresh_from_db()
        self.assertEqual(card.layout_config['nfc_card']['status'], 'Shipped')
        self.assertEqual(card.layout_config['nfc_card']['tracking_info'], 'BlueDart AW77889900')

        # Verify client received email update about Shipped status
        self.assertEqual(len(mail.outbox), 1)
        client_email = mail.outbox[0]
        self.assertEqual(client_email.to, ['arjun.innovations@gmail.com'])
        self.assertIn('Shipped', client_email.subject)
        self.assertIn('BlueDart AW77889900', client_email.body)

        # 5. Client views preview page (as seen in Screenshot 2) -> shows 'Shipped' status
        self.client.force_login(user)
        preview_page = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}))
        self.assertEqual(preview_page.status_code, 200)
        self.assertContains(preview_page, 'Shipped')
        self.assertContains(preview_page, 'BlueDart AW77889900')

        # 6. Super Admin opens print specification sheet
        self.client.force_login(admin_user)
        print_sheet = self.client.get(reverse('enterprise_admin_nfc_print_sheet', kwargs={'card_id': card.card_id}))
        self.assertEqual(print_sheet.status_code, 200)
        self.assertContains(print_sheet, 'Production Ticket for Laser Engraving')
        self.assertContains(print_sheet, 'CR80 FORM FACTOR')
        self.assertContains(print_sheet, 'Arjun Robotics Labs')

    def test_personal_vs_enterprise_nfc_orders_separation(self):
        """
        Verify:
        - Personal user card with NFC reflects in Personal Super Admin Dashboard (/dashboard/nfc/).
        - Enterprise CEO card / team cards with NFC reflect in Enterprise Super Admin Dashboard (/enterprise-admin/nfc-orders/).
        - Cross-filtering strictly separates personal from enterprise orders.
        """
        from apps.cards.models import EnterpriseCompany

        # 1. Super admin user
        admin = User.objects.create_superuser('super_director', 'director@brandnest.io', 'DirectorPass123!')
        self.client.force_login(admin)

        # 2. Personal user with NFC card
        p_user = User.objects.create_user('priya_personal', 'priya.k@gmail.com', 'PriyaPass123!')
        p_card = BusinessCard.objects.create(
            user=p_user,
            business_name='Priya Studio',
            owner_name='Priya Kumar',
            email='priya.k@gmail.com',
            layout_config={
                'payment_receipt': {'amount': 999, 'plan': 'Personal Pro + Physical NFC Card (Yearly)'},
                'nfc_card': {'ordered': True, 'name': 'Priya Kumar', 'status': 'Ready for Dispatch'}
            }
        )

        # 3. Enterprise company & CEO with NFC card
        e_company = EnterpriseCompany.objects.create(name='Nexus Health Tech', website='https://nexushealth.com')
        e_user = User.objects.create_user('raj_ceo', 'raj.ceo@nexushealth.com', 'RajCeoPass123!')
        e_plan = UserPlan.objects.create(
            user=e_user,
            plan_type='enterprise',
            is_ceo=True,
            card_limit=10,
            nfc_card_limit=10,
            company_name='Nexus Health Tech'
        )
        e_card = BusinessCard.objects.create(
            user=e_user,
            enterprise_company=e_company,
            business_name='Nexus Health Tech',
            owner_name='Rajesh Varma',
            email='raj.ceo@nexushealth.com',
            layout_config={
                'payment_receipt': {'amount': 4499, 'plan': 'Growth Pro + 10 Smart NFC Cards'},
                'nfc_card': {'ordered': True, 'name': 'Rajesh Varma', 'status': 'Printing & Engraving'}
            }
        )

        # Check Personal Super Admin Dashboard (/dashboard/nfc/)
        res_personal = self.client.get(reverse('dashboard_nfc'))
        self.assertEqual(res_personal.status_code, 200)
        self.assertContains(res_personal, 'Priya Studio')
        self.assertContains(res_personal, 'Priya Kumar')
        self.assertNotContains(res_personal, 'Nexus Health Tech')

        # Check Enterprise Super Admin Dashboard (/enterprise-admin/nfc-orders/)
        res_enterprise = self.client.get(reverse('enterprise_admin_nfc_orders'))
        self.assertEqual(res_enterprise.status_code, 200)
        self.assertContains(res_enterprise, 'Nexus Health Tech')
        self.assertContains(res_enterprise, 'Rajesh Varma')
        self.assertNotContains(res_enterprise, 'Priya Studio')

    def test_regular_user_cannot_access_admin_or_dashboard(self):
        """
        Verify:
        1. A regular client who signs up / pays cannot access /admin or /dashboard/.
        2. Visiting /admin or /dashboard/ redirects to /admin/login/ with an admin warning.
        3. Attempting to log into /admin/login/ with non-staff credentials is rejected with Access Denied.
        4. Logging into /admin/login/ with superuser credentials succeeds and grants access.
        """
        regular_user = User.objects.create_user(
            username='client_sarah',
            email='sarah@mybrand.com',
            password='SarahPassword123!'
        )
        self.client.force_login(regular_user)

        # 1. Regular user visits /admin -> must redirect to /admin/login/
        admin_res = self.client.get('/admin', follow=False)
        self.assertEqual(admin_res.status_code, 302)
        self.assertEqual(admin_res.url, reverse('admin_login'))

        # 2. Regular user visits /dashboard/overview/ -> must redirect to /admin/login/?next=/dashboard/overview/
        dash_res = self.client.get(reverse('dashboard_overview'), follow=True)
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, 'Administrator privileges required')
        self.assertContains(dash_res, 'client_sarah')

        # 3. Regular user attempts to log into admin portal with regular credentials -> Access Denied
        login_res = self.client.post(reverse('admin_login'), {
            'username': 'client_sarah',
            'password': 'SarahPassword123!'
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertContains(login_res, 'Access denied')

        # 4. Super admin logs in -> success
        admin_user = User.objects.create_superuser('boss_admin', 'boss@brandnest.io', 'BossPass123!')
        login_admin = self.client.post(reverse('admin_login'), {
            'username': 'boss_admin',
            'password': 'BossPass123!'
        })
        self.assertEqual(login_admin.status_code, 302)
        self.assertEqual(login_admin.url, reverse('dashboard_overview'))

    def test_super_admin_change_prices_and_dynamic_reflection(self):
        """
        Verify:
        1. Super Admin can view pricing management in both Personal Super Admin (/dashboard/pricing/)
           and Enterprise Super Admin (/enterprise-admin/pricing/).
        2. Super Admin can submit updated prices for Personal Digital, NFC, and Enterprise bundles.
        3. Updated prices immediately reflect across the platform:
           - /card/choose-plan/
           - /card/build/
           - /enterprise/checkout/
           - Personal card creation payment receipt calculations.
        4. Super Admin can reset prices back to system defaults.
        """
        admin_user = User.objects.create_superuser('price_admin', 'pricing@brandnest.io', 'PriceAdminPass123!')
        self.client.force_login(admin_user)

        # 1. Access pricing page from both dashboards
        res_dash = self.client.get(reverse('dashboard_pricing'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'Plan &amp; Card Pricing Management')

        res_ent = self.client.get(reverse('enterprise_admin_pricing'))
        self.assertEqual(res_ent.status_code, 200)
        self.assertContains(res_ent, 'Plan &amp; Card Pricing Management')

        # 2. Update prices to custom values
        post_data = {
            'action': 'save',
            'personal_digital_price': '699',
            'personal_nfc_price': '1299',
            'enterprise_5_digital_price': '1499',
            'enterprise_10_digital_price': '2599',
            'enterprise_15_digital_price': '3499',
            'enterprise_5_nfc_price': '3199',
            'enterprise_10_nfc_price': '5799',
            'enterprise_15_nfc_price': '7999',
            'enterprise_extra_card_price': '249',
        }
        save_res = self.client.post(reverse('dashboard_pricing'), post_data, follow=True)
        self.assertEqual(save_res.status_code, 200)
        self.assertContains(save_res, 'Pricing configuration updated and published across all plans successfully!')

        pricing = PlatformPricing.get_pricing()
        self.assertEqual(pricing.personal_digital_price, 699)
        self.assertEqual(pricing.personal_nfc_price, 1299)
        self.assertEqual(pricing.enterprise_5_digital_price, 1499)
        self.assertEqual(pricing.enterprise_10_digital_price, 2599)
        self.assertEqual(pricing.enterprise_15_digital_price, 3499)
        self.assertEqual(pricing.enterprise_5_nfc_price, 3199)
        self.assertEqual(pricing.enterprise_10_nfc_price, 5799)
        self.assertEqual(pricing.enterprise_15_nfc_price, 7999)
        self.assertEqual(pricing.enterprise_extra_card_price, 249)

        # 3. Check reflection on /card/choose-plan/
        choose_res = self.client.get(reverse('card_choose_plan'))
        self.assertEqual(choose_res.status_code, 200)
        self.assertContains(choose_res, '₹699')
        self.assertContains(choose_res, 'Digital Card (₹699) or Custom Smart NFC Card Bundle (₹1299)')

        # 4. Check reflection on /card/build/
        build_res = self.client.get(reverse('card_builder'))
        self.assertEqual(build_res.status_code, 200)
        self.assertContains(build_res, '₹699')
        self.assertContains(build_res, 'Generate Business Card (₹699)')
        self.assertContains(build_res, '₹1299')
        self.assertContains(build_res, 'Design NFC Card &amp; Pay (₹1299)')
        self.assertContains(build_res, 'window.personalDigitalPrice = 699;')
        self.assertContains(build_res, 'window.personalNfcPrice = 1299;')

        # 5. Check reflection in enterprise checkout
        session = self.client.session
        session['enterprise_onboarding'] = {
            'company_name': 'Acme Global Ventures',
            'company_head_name': 'Alice Wonder',
            'email': 'alice@acmeglobal.com',
            'phone': '+919876543210',
            'industry': 'technology-and-it',
        }
        session.save()
        ent_checkout_res = self.client.get(reverse('enterprise_checkout'))
        self.assertEqual(ent_checkout_res.status_code, 200)
        self.assertContains(ent_checkout_res, '₹1499')
        self.assertContains(ent_checkout_res, '₹3199')

        # 6. Verify personal card creation saves receipt with the updated price
        card_res = self.client.post(reverse('card_builder'), {
            'business_name': 'Alice Dynamic Studio',
            'owner_name': 'Alice Wonder',
            'nfc_ordered': 'true',
            'razorpay_payment_id': 'pay_dyn_test_123',
            'razorpay_amount': '1299',
        })
        self.assertEqual(card_res.status_code, 302)
        new_card = BusinessCard.objects.get(business_name='Alice Dynamic Studio')
        receipt = new_card.layout_config.get('payment_receipt', {})
        self.assertEqual(receipt.get('amount'), 1299)

        # 7. Reset to defaults from Enterprise Admin Pricing
        reset_res = self.client.post(reverse('enterprise_admin_pricing'), {'action': 'reset'}, follow=True)
        self.assertEqual(reset_res.status_code, 200)
        self.assertContains(reset_res, 'Pricing configuration successfully reset to system defaults.')

        pricing_reset = PlatformPricing.get_pricing()
        self.assertEqual(pricing_reset.personal_digital_price, 499)
        self.assertEqual(pricing_reset.personal_nfc_price, 999)
        self.assertEqual(pricing_reset.enterprise_5_digital_price, 999)
        self.assertEqual(pricing_reset.enterprise_extra_card_price, 199)

    def test_personal_vs_enterprise_full_dashboard_segregation(self):
        """
        Verify that Personal cards/leads/metrics and Enterprise cards/leads/metrics
        are strictly isolated and never mix up:
        1. Personal user builds a card -> visible in /dashboard/cards/, NOT in /enterprise-admin/cards/.
        2. Enterprise CEO/team builds cards -> visible in /enterprise-admin/cards/, NOT in /dashboard/cards/.
        3. Leads submitted to Personal cards appear in /dashboard/leads/ & /dashboard/contacts/, NOT in /enterprise-admin/leads/.
        4. Leads submitted to Enterprise cards appear in /enterprise-admin/leads/, NOT in /dashboard/leads/ & /dashboard/contacts/.
        5. QR codes (/dashboard/qr-codes/) list only personal cards.
        """
        admin = User.objects.create_superuser('dash_seg_admin', 'seg_admin@brandnest.io', 'SegAdminPass123!')
        self.client.force_login(admin)

        # 1. Create a Personal User and Personal Card
        personal_user = User.objects.create_user('john_freelance', 'john@freelance.org', 'JohnPass123!')
        UserPlan.objects.create(
            user=personal_user,
            plan_type='personal',
            plan_name='Personal Pro Digital (Yearly)',
            total_paid=499
        )
        personal_card = BusinessCard.objects.create(
            user=personal_user,
            business_name='John Photo Studio',
            owner_name='John Doe',
            email='john@freelance.org',
            views_count=15,
            layout_config={
                'payment_receipt': {'amount': 499, 'plan': 'Personal Pro Digital (Yearly)'}
            }
        )

        # 2. Create an Enterprise Company, CEO, and Enterprise Card
        company = EnterpriseCompany.objects.create(name='Acme Robotics Corp', email='corp@acmerobotics.com')
        ent_ceo = User.objects.create_user('acme_ceo', 'ceo@acmerobotics.com', 'AcmeCeoPass123!')
        UserPlan.objects.create(
            user=ent_ceo,
            plan_type='enterprise',
            is_ceo=True,
            company_name='Acme Robotics Corp',
            card_limit=10,
            total_paid=4499
        )
        enterprise_card = BusinessCard.objects.create(
            user=ent_ceo,
            enterprise_company=company,
            business_name='Acme Robotics Corp',
            owner_name='Dr. Elena Vance',
            email='elena@acmerobotics.com',
            views_count=50,
            layout_config={
                'payment_receipt': {'amount': 4499, 'plan': 'Acme Robotics Corp Enterprise Corporate Plan'}
            }
        )

        # 3. Create Leads for each card
        personal_lead = CardLead.objects.create(
            card=personal_card,
            name='Sarah Client',
            email='sarah@wedding.com',
            message='Need photography quote'
        )
        enterprise_lead = CardLead.objects.create(
            card=enterprise_card,
            name='Procurement Officer',
            email='buyer@megacorp.com',
            message='Interested in bulk enterprise contract'
        )

        # === VERIFY PERSONAL SUPER ADMIN DASHBOARD ===
        # A. Personal Cards page (/dashboard/cards/)
        res_p_cards = self.client.get(reverse('dashboard_cards'))
        self.assertEqual(res_p_cards.status_code, 200)
        self.assertContains(res_p_cards, 'John Photo Studio')
        self.assertContains(res_p_cards, 'John Doe')
        self.assertNotContains(res_p_cards, 'Acme Robotics Corp')
        self.assertNotContains(res_p_cards, 'Dr. Elena Vance')

        # B. Personal QR Codes page (/dashboard/qr-codes/)
        res_p_qr = self.client.get(reverse('dashboard_qr_codes'))
        self.assertEqual(res_p_qr.status_code, 200)
        self.assertContains(res_p_qr, 'John Photo Studio')
        self.assertNotContains(res_p_qr, 'Acme Robotics Corp')

        # C. Personal Leads page (/dashboard/leads/)
        res_p_leads = self.client.get(reverse('dashboard_leads'))
        self.assertEqual(res_p_leads.status_code, 200)
        self.assertContains(res_p_leads, 'Sarah Client')
        self.assertNotContains(res_p_leads, 'Procurement Officer')

        # D. Personal Contacts page (/dashboard/contacts/)
        res_p_contacts = self.client.get(reverse('dashboard_contacts'))
        self.assertEqual(res_p_contacts.status_code, 200)
        self.assertContains(res_p_contacts, 'Sarah Client')
        self.assertNotContains(res_p_contacts, 'Procurement Officer')

        # E. Personal Overview (/dashboard/overview/)
        res_p_overview = self.client.get(reverse('dashboard_overview'))
        self.assertEqual(res_p_overview.status_code, 200)
        self.assertContains(res_p_overview, 'John Photo Studio')
        self.assertNotContains(res_p_overview, 'Acme Robotics Corp')

        # === VERIFY ENTERPRISE SUPER ADMIN DASHBOARD ===
        # A. Enterprise Cards page (/enterprise-admin/cards/)
        res_e_cards = self.client.get(reverse('enterprise_admin_cards'))
        self.assertEqual(res_e_cards.status_code, 200)
        self.assertContains(res_e_cards, 'Acme Robotics Corp')
        self.assertContains(res_e_cards, 'Dr. Elena Vance')
        self.assertNotContains(res_e_cards, 'John Photo Studio')
        self.assertNotContains(res_e_cards, 'John Doe')

        # B. Enterprise Leads page (/enterprise-admin/leads/)
        res_e_leads = self.client.get(reverse('enterprise_admin_leads'))
        self.assertEqual(res_e_leads.status_code, 200)
        self.assertContains(res_e_leads, 'Procurement Officer')
        self.assertNotContains(res_e_leads, 'Sarah Client')

    def test_personal_card_nfc_upgrade_flow(self):
        """
        Verify that a personal user with a digital-only card can:
        1. View the NFC upgrade banner and preview/customizer in edit mode.
        2. Successfully submit an upgrade payment with custom NFC specs.
        3. Upon payment, nfc_card is marked ordered, and order appears in Personal Super Admin NFC dashboard.
        4. The order does NOT appear in Enterprise Super Admin NFC dashboard.
        """
        user = User.objects.create_user(username='upgrade_user', password='password123', email='upgrade@example.com')
        card = BusinessCard.objects.create(
            user=user,
            business_name='Upgrade Digital Tech',
            owner_name='Vikram Seth',
            slug='upgrade-digital-tech',
            card_id='c_upgrade_01',
            email='upgrade@example.com',
            layout_config={
                'payment_receipt': {
                    'plan': 'Personal Pro Digital (Yearly)',
                    'amount': 499,
                    'status': 'captured',
                }
            }
        )
        self.client.login(username='upgrade_user', password='password123')

        # 1. Access edit page: should contain the NFC upgrade option & preview button
        edit_url = reverse('card_edit', kwargs={'card_id': card.card_id})
        res_edit = self.client.get(edit_url)
        self.assertEqual(res_edit.status_code, 200)
        self.assertContains(res_edit, 'PHYSICAL HARDWARE UPGRADE')
        self.assertContains(res_edit, 'Preview &amp; Customize NFC')
        self.assertContains(res_edit, 'Order NFC Card')

        # 2. Submit NFC Hardware Upgrade with Razorpay payment
        upgrade_data = {
            'business_name': 'Upgrade Digital Tech',
            'owner_name': 'Vikram Seth',
            'email': 'upgrade@example.com',
            'phone': '9876543210',
            'razorpay_payment_id': 'pay_demo_upgrade_9999',
            'razorpay_amount': '500',
            'razorpay_method': 'UPI (Fast Pay)',
            'nfc_ordered': 'true',
            'nfc_theme': 'titanium_blue',
            'nfc_foil': 'gold',
            'nfc_name': 'Vikram Seth',
            'nfc_designation': 'CTO & Co-Founder',
        }
        res_post = self.client.post(edit_url, upgrade_data, follow=True)
        self.assertEqual(res_post.status_code, 200)

        card.refresh_from_db()
        nfc_cfg = (card.layout_config or {}).get('nfc_card', {})
        self.assertTrue(nfc_cfg.get('ordered'))
        self.assertEqual(nfc_cfg.get('theme'), 'titanium_blue')
        self.assertEqual(nfc_cfg.get('foil'), 'gold')
        self.assertEqual(nfc_cfg.get('designation'), 'CTO & Co-Founder')

        # 3. Verify in Personal Super Admin Dashboard
        admin_user = User.objects.create_superuser(username='superadmin_nfc', password='password123', email='admin@brandnest.in')
        self.client.login(username='superadmin_nfc', password='password123')
        session = self.client.session
        session['dashboard_admin_logged_in'] = True
        session.save()

        res_p_nfc = self.client.get(reverse('dashboard_nfc'))
        self.assertEqual(res_p_nfc.status_code, 200)
        self.assertContains(res_p_nfc, 'Upgrade Digital Tech')
        self.assertContains(res_p_nfc, 'c_upgrade_01')

        # 4. Verify NOT in Enterprise Super Admin Dashboard
        res_e_nfc = self.client.get(reverse('enterprise_admin_nfc_orders'))
        self.assertEqual(res_e_nfc.status_code, 200)
        self.assertNotContains(res_e_nfc, 'Upgrade Digital Tech')
        self.assertNotContains(res_e_nfc, 'c_upgrade_01')

    def test_wallet_pass_qr_code_sync_with_card(self):
        """
        Verify that the wallet pass QR code accurately mirrors the business card's QR code and link.
        """
        user = User.objects.create_user(username='wallet_user', password='password123', email='wallet@example.com')
        card = BusinessCard.objects.create(
            user=user,
            business_name='Apex Design Lab',
            owner_name='Rahul Sharma',
            slug='apex-design-lab',
            card_id='c_apex_01',
            email='rahul@apex.com'
        )
        self.client.login(username='wallet_user', password='password123')

        res = self.client.get(reverse('card_edit', kwargs={'card_id': card.card_id}))
        self.assertEqual(res.status_code, 200)
        self.assertIn('qr_data_uri', res.context)
        self.assertIn('share_url', res.context)
        self.assertTrue(len(res.context['qr_data_uri']) > 0)
        self.assertIn('apex-design-lab', res.context['share_url'])
        self.assertContains(res, 'apex-design-lab')
        self.assertContains(res, 'walletQrImg')

    def test_super_admin_new_business_dashboards(self):
        """
        Verify that both Personal and Enterprise Super Admin dashboards provide the
        New Business sections displaying newly created cards and NFC hardware orders.
        """
        p_user = User.objects.create_user(username='p_client_nb', password='password123', email='client@personal.com')
        p_card = BusinessCard.objects.create(
            user=p_user,
            business_name='Personal Studio Pro',
            owner_name='Aditi Rao',
            slug='personal-studio-pro',
            card_id='c_p_nb_01',
            email='client@personal.com',
            layout_config={
                'payment_receipt': {'plan': 'Personal Pro + Physical NFC Card (Yearly)', 'amount': 999},
                'nfc_card': {'ordered': True, 'theme': 'obsidian_black', 'status': 'Ready for Dispatch'}
            }
        )

        company = EnterpriseCompany.objects.create(
            name='Titan Global Tech',
            email='ceo@titan.com',
            head_name='Vikram Titan',
            card_quota=10
        )
        e_user = User.objects.create_user(username='e_emp_nb', password='password123', email='emp@titan.com')
        e_card = BusinessCard.objects.create(
            user=e_user,
            enterprise_company=company,
            business_name='Titan Global Tech',
            owner_name='Siddharth Titan',
            slug='siddharth-titan',
            card_id='c_e_nb_01',
            email='emp@titan.com',
            layout_config={
                'payment_receipt': {'plan': 'Titan Global Tech Enterprise Corporate Plan', 'amount': 0},
                'nfc_card': {'ordered': True, 'theme': 'titanium_blue', 'status': 'Ready for Printing'}
            }
        )

        admin_user = User.objects.create_superuser(username='superadmin_nb', password='password123', email='admin_nb@brandnest.in')
        self.client.login(username='superadmin_nb', password='password123')
        session = self.client.session
        session['dashboard_admin_logged_in'] = True
        session.save()

        # 1. Personal Super Admin Overview
        res_p_overview = self.client.get(reverse('dashboard_overview'))
        self.assertEqual(res_p_overview.status_code, 200)
        self.assertContains(res_p_overview, 'New Business: Recent Cards &amp; NFC Orders')
        self.assertContains(res_p_overview, 'Personal Studio Pro')
        self.assertContains(res_p_overview, 'Aditi Rao')
        self.assertNotContains(res_p_overview, 'Titan Global Tech')
        self.assertNotContains(res_p_overview, 'Siddharth Titan')

        # 2. Enterprise Super Admin Overview
        res_e_overview = self.client.get(reverse('enterprise_admin_overview'))
        self.assertEqual(res_e_overview.status_code, 200)
        self.assertContains(res_e_overview, 'New Business: Corporate Cards &amp; Employee NFC Generations')
        self.assertContains(res_e_overview, 'Titan Global Tech')
        self.assertContains(res_e_overview, 'Siddharth Titan')
        self.assertNotContains(res_e_overview, 'Personal Studio Pro')
        self.assertNotContains(res_e_overview, 'Aditi Rao')

    def test_super_admin_new_nfc_orders_and_print_sheet(self):
        """
        Verify that:
        1. Both Personal (/dashboard/nfc/) and Enterprise (/enterprise-admin/nfc/) dashboards
           provide a 'New NFC Orders' option/filter that isolates unfulfilled orders ready for printing.
        2. Super admin can click to view new NFC orders and directly generate/print CR80 print sheets.
        3. Strict Personal vs Enterprise isolation is preserved across NFC consoles.
        """
        # Create Personal User Cards
        p_user = User.objects.create_user(username='p_nfc_client', password='password123', email='client@pers.in')
        p_card_new = BusinessCard.objects.create(
            user=p_user,
            business_name='Aura Innovations',
            owner_name='Kabir Sharma',
            slug='kabir-aura',
            card_id='c_p_nfc_new_01',
            email='kabir@aura.in',
            layout_config={
                'payment_receipt': {'plan': 'Business Card + Smart NFC Card', 'amount': 999},
                'nfc_card': {'ordered': True, 'theme': 'obsidian_black', 'foil': 'gold', 'status': 'Ready for Printing & Dispatch'}
            }
        )
        p_card_shipped = BusinessCard.objects.create(
            user=p_user,
            business_name='Aura Shipped Lab',
            owner_name='Kabir Past',
            slug='kabir-past',
            card_id='c_p_nfc_shipped_02',
            email='kabir@aura.in',
            layout_config={
                'payment_receipt': {'plan': 'Business Card + Smart NFC Card', 'amount': 999},
                'nfc_card': {'ordered': True, 'theme': 'pearl_white', 'foil': 'silver', 'status': 'Shipped'}
            }
        )

        # Create Enterprise Company & Cards
        company = EnterpriseCompany.objects.create(
            name='Vertex Aerospace',
            email='admin@vertex.com',
            head_name='Meera Vertex',
            card_quota=20
        )
        e_user = User.objects.create_user(username='e_nfc_client', password='password123', email='emp@vertex.com')
        e_card_new = BusinessCard.objects.create(
            user=e_user,
            enterprise_company=company,
            business_name='Vertex Aerospace',
            owner_name='Dev Mehra',
            slug='dev-vertex',
            card_id='c_e_nfc_new_03',
            email='emp@vertex.com',
            layout_config={
                'payment_receipt': {'plan': 'Vertex Aerospace Enterprise Plan', 'amount': 0},
                'nfc_card': {'ordered': True, 'theme': 'titanium_blue', 'status': 'Order Placed'}
            }
        )
        e_card_delivered = BusinessCard.objects.create(
            user=e_user,
            enterprise_company=company,
            business_name='Vertex Aerospace',
            owner_name='Ananya Old',
            slug='ananya-vertex',
            card_id='c_e_nfc_del_04',
            email='emp@vertex.com',
            layout_config={
                'payment_receipt': {'plan': 'Vertex Aerospace Enterprise Plan', 'amount': 0},
                'nfc_card': {'ordered': True, 'theme': 'royal_gold', 'status': 'Delivered'}
            }
        )

        # Admin login
        admin = User.objects.create_superuser(username='super_nfc_boss', password='password123', email='boss@brandnest.in')
        self.client.login(username='super_nfc_boss', password='password123')
        session = self.client.session
        session['dashboard_admin_logged_in'] = True
        session.save()

        # 1. Personal NFC Dashboard - All vs New NFC Orders
        p_nfc_res = self.client.get(reverse('dashboard_nfc'))
        self.assertEqual(p_nfc_res.status_code, 200)
        self.assertContains(p_nfc_res, 'New NFC Orders')
        self.assertContains(p_nfc_res, 'Aura Innovations')
        self.assertContains(p_nfc_res, 'Aura Shipped Lab')
        self.assertNotContains(p_nfc_res, 'Vertex Aerospace')

        # Filter ?filter=new on Personal
        p_nfc_new_res = self.client.get(reverse('dashboard_nfc') + '?filter=new')
        self.assertEqual(p_nfc_new_res.status_code, 200)
        self.assertContains(p_nfc_new_res, 'Aura Innovations')
        self.assertContains(p_nfc_new_res, 'NEW NFC ORDER')
        self.assertContains(p_nfc_new_res, 'Print Sheet &rarr;')
        self.assertNotContains(p_nfc_new_res, 'Aura Shipped Lab')
        self.assertNotContains(p_nfc_new_res, 'Vertex Aerospace')

        # 2. Enterprise NFC Dashboard - All vs New NFC Orders
        e_nfc_res = self.client.get(reverse('enterprise_admin_nfc_orders'))
        self.assertEqual(e_nfc_res.status_code, 200)
        self.assertContains(e_nfc_res, 'New NFC Orders')
        self.assertContains(e_nfc_res, 'Dev Mehra')
        self.assertContains(e_nfc_res, 'Ananya Old')
        self.assertNotContains(e_nfc_res, 'Aura Innovations')

        # Filter ?filter=new on Enterprise
        e_nfc_new_res = self.client.get(reverse('enterprise_admin_nfc_orders') + '?filter=new')
        self.assertEqual(e_nfc_new_res.status_code, 200)
        self.assertContains(e_nfc_new_res, 'Dev Mehra')
        self.assertContains(e_nfc_new_res, 'NEW NFC ORDER')
        self.assertContains(e_nfc_new_res, 'Print Sheet &rarr;')
        self.assertNotContains(e_nfc_new_res, 'Ananya Old')
        self.assertNotContains(e_nfc_new_res, 'Aura Innovations')

        # 3. Print Sheet Generation for workshop
        sheet_res = self.client.get(reverse('enterprise_admin_nfc_print_sheet', kwargs={'card_id': p_card_new.card_id}))
        self.assertEqual(sheet_res.status_code, 200)
        self.assertContains(sheet_res, 'BrandNest Hardware Fulfillment')
        self.assertContains(sheet_res, 'CR80 FORM FACTOR')
        self.assertContains(sheet_res, 'Kabir Sharma')
        self.assertContains(sheet_res, 'c_p_nfc_new_01')
        self.assertContains(sheet_res, reverse('dashboard_nfc'))

        # Check ?autoprint=1 triggers window.print()
        sheet_autoprint = self.client.get(reverse('enterprise_admin_nfc_print_sheet', kwargs={'card_id': p_card_new.card_id}) + '?autoprint=1')
        self.assertEqual(sheet_autoprint.status_code, 200)
        self.assertContains(sheet_autoprint, 'window.print()')

        # 4. Verify order moves across tabs when status is updated:
        # Step A: Update to 'Printing & Engraving' -> Moves from New to 'In Production'
        post_prod = self.client.post(
            reverse('dashboard_nfc_status_update', kwargs={'card_id': p_card_new.card_id}),
            {'status': 'Printing & Engraving', 'tracking_info': '', 'next': reverse('dashboard_nfc') + '?filter=new'}
        )
        self.assertEqual(post_prod.status_code, 302)

        # After updating, Aura Innovations is NO LONGER in ?filter=new (New NFC Orders)
        p_new_after = self.client.get(reverse('dashboard_nfc') + '?filter=new')
        self.assertEqual(len(p_new_after.context['orders']), 0)
        self.assertEqual(p_new_after.context['stats']['new_orders'], 0)
        self.assertEqual(p_new_after.context['stats']['in_production'], 1)

        # It is now visible in ?status=Printing+%26+Engraving (In Production)
        p_prod_tab = self.client.get(reverse('dashboard_nfc') + '?status=Printing+%26+Engraving')
        self.assertEqual(len(p_prod_tab.context['orders']), 1)
        self.assertEqual(p_prod_tab.context['orders'][0].business_name, 'Aura Innovations')
        self.assertContains(p_prod_tab, 'Printing &amp; Engraving')

        # Step B: Update to 'Ready for Dispatch' -> Moves to 'Ready for Dispatch' tab
        post_ready = self.client.post(
            reverse('dashboard_nfc_status_update', kwargs={'card_id': p_card_new.card_id}),
            {'status': 'Ready for Dispatch', 'tracking_info': ''}
        )
        self.assertEqual(post_ready.status_code, 302)
        p_ready_tab = self.client.get(reverse('dashboard_nfc') + '?status=Ready+for+Dispatch')
        self.assertEqual(len(p_ready_tab.context['orders']), 1)
        self.assertEqual(p_ready_tab.context['orders'][0].business_name, 'Aura Innovations')

        # Step C: Update to 'Shipped' with tracking -> Moves to 'Shipped' tab
        post_ship = self.client.post(
            reverse('dashboard_nfc_status_update', kwargs={'card_id': p_card_new.card_id}),
            {'status': 'Shipped', 'tracking_info': 'BlueDart AW12345678'}
        )
        self.assertEqual(post_ship.status_code, 302)
        p_shipped_tab = self.client.get(reverse('dashboard_nfc') + '?status=Shipped')
        self.assertIn(p_card_new.card_id, [c.card_id for c in p_shipped_tab.context['orders']])
        self.assertContains(p_shipped_tab, 'BlueDart AW12345678')

        # Step D: Update to 'Delivered' -> Moves to 'Delivered' tab
        post_del = self.client.post(
            reverse('dashboard_nfc_status_update', kwargs={'card_id': p_card_new.card_id}),
            {'status': 'Delivered', 'tracking_info': 'Delivered to recipient'}
        )
        self.assertEqual(post_del.status_code, 302)
        p_del_tab = self.client.get(reverse('dashboard_nfc') + '?status=Delivered')
        self.assertEqual(len(p_del_tab.context['orders']), 1)
        self.assertEqual(p_del_tab.context['orders'][0].business_name, 'Aura Innovations')

    def test_card_subdomain_urls_and_routing(self):
        """
        Verify that:
        1. When running on local host machine / unhosted Django server, card URLs are formatted
           as local server IP subdomains: e.g. http://raj.192.168.1.34:8000/
        2. When hosted on a domain (CARD_BASE_DOMAIN set), card URLs are formatted as
           https://raj.mybrand.com/
        3. SubdomainRoutingMiddleware automatically routes requests on both IP-subdomains
           (raj.192.168.1.34) and domain-subdomains (raj.mybrand.com) directly to the card.
        4. System reserved subdomains (e.g. www) pass through to the main application.
        5. Unknown subdomains render a clean 404 page.
        """
        from apps.frontend.views import get_card_subdomain_url, get_shareable_url, get_lan_ip
        from django.test import RequestFactory, override_settings

        rf = RequestFactory()
        user = User.objects.create_user(username='subdomain_user', password='password123', email='raj@test.com')
        card = BusinessCard.objects.create(
            user=user,
            business_name='Raj Luxury Studio',
            owner_name='Raj Malhotra',
            slug='raj',
            card_id='c_raj_sub_01',
            email='raj@test.com',
            phone='+919876543210',
            layout_config={'payment_receipt': {'plan': 'Business Card', 'amount': 499}}
        )

        expected_ip = get_lan_ip() or '127.0.0.1'
        expected_local_url = f"http://raj.{expected_ip}.nip.io:8000/"

        # 1. Verify Local Server URL Generation (Unhosted Mode with nip.io)
        subdomain_url = get_card_subdomain_url(card.slug)
        self.assertEqual(subdomain_url, expected_local_url)
        self.assertEqual(card.subdomain_url, expected_local_url)
        self.assertEqual(card.share_url, expected_local_url)

        req_local = rf.get('/card/raj/', HTTP_HOST='192.168.1.34:8000')
        share_url_local = get_shareable_url(req_local, f'/card/{card.slug}/')
        self.assertEqual(share_url_local, 'http://raj.192.168.1.34.nip.io:8000/')

        # 2. Verify Card Preview Page displays the local server link
        self.client.force_login(user)
        preview_res = self.client.get(reverse('card_preview', kwargs={'card_id': card.card_id}), HTTP_HOST='192.168.1.34:8000')
        self.assertEqual(preview_res.status_code, 200)
        self.assertContains(preview_res, 'http://raj.192.168.1.34.nip.io:8000/')
        self.assertContains(preview_res, 'Shareable Subdomain Link:')

        # 3. Verify Subdomain Routing Middleware on nip.io (http://raj.192.168.1.34.nip.io:8000/)
        sub_res_nip = self.client.get('/', HTTP_HOST='raj.192.168.1.34.nip.io:8000')
        self.assertEqual(sub_res_nip.status_code, 200)
        self.assertContains(sub_res_nip, 'Raj Luxury Studio')
        self.assertContains(sub_res_nip, 'Raj Malhotra')

        # Subdomain direct QR code request on nip.io: http://raj.192.168.1.34.nip.io:8000/qr.png
        sub_qr_nip = self.client.get('/qr.png', HTTP_HOST='raj.192.168.1.34.nip.io:8000')
        self.assertEqual(sub_qr_nip.status_code, 200)
        self.assertEqual(sub_qr_nip['Content-Type'], 'image/png')

        # 4. Verify Production Domain Hosting Mode (e.g. CARD_BASE_DOMAIN='mybrand.com')
        with override_settings(CARD_BASE_DOMAIN='mybrand.com'):
            prod_url = get_card_subdomain_url(card.slug)
            self.assertEqual(prod_url, 'https://raj.mybrand.com/')

            sub_res_prod = self.client.get('/', HTTP_HOST='raj.mybrand.com')
            self.assertEqual(sub_res_prod.status_code, 200)
            self.assertContains(sub_res_prod, 'Raj Luxury Studio')

        # 5. Reserved subdomain (e.g. www.192.168.1.34:8000) routes to landing view
        www_res = self.client.get('/', HTTP_HOST='www.192.168.1.34:8000')
        self.assertEqual(www_res.status_code, 200)
        self.assertContains(www_res, 'BrandNest')

        # 6. Non-existent subdomain routes to 404 Card Not Found
        missing_res = self.client.get('/', HTTP_HOST='unknown-person.192.168.1.34:8000')
        self.assertEqual(missing_res.status_code, 404)
        self.assertContains(missing_res, 'Card Not Found', status_code=404)
        self.assertContains(missing_res, 'unknown-person.192.168.1.34:8000', status_code=404)

    def test_nfc_order_and_status_dropdown_email_notifications_flow(self):
        """
        Verify the complete NFC email notification flow across both Personal and Enterprise dashboards:
        1. When user places/pays for an NFC card, they receive an 'Order Placed' confirmation email to their signup email.
        2. In Personal Super Admin (/dashboard/nfc/), selecting each status from the dropdown:
           - 'Order Placed'
           - 'Printing & Engraving'
           - 'Ready for Dispatch'
           - 'Shipped'
           - 'Delivered'
           and clicking 'Save Status & Notify Client' sends the user an automated status update email to their signup email.
        3. In Enterprise Super Admin (/enterprise-admin/nfc-orders/), selecting each status from the dropdown
           and clicking 'Save Status & Notify Client' sends the enterprise cardholder/employee an automated status email.
        """
        from django.core import mail
        from apps.cards.notifications import get_user_notification_email, get_user_notification_recipients

        # Setup Super Admin
        admin = User.objects.create_superuser(username='super_nfc_manager', email='admin_nfc@brandnest.io', password='AdminPass123!')

        # --- A. PERSONAL NFC CARD FLOW ---
        personal_user = User.objects.create_user(
            username='personal_nfc_user',
            email='pers.user.signup@gmail.com',
            password='UserPass123!',
            first_name='Kavya',
            last_name='Nair'
        )

        # 1. User orders Personal NFC card through card_builder
        self.client.force_login(personal_user)
        mail.outbox.clear()

        nfc_payload = {
            'business_name': 'Kavya Fine Jewels',
            'owner_name': 'Kavya Nair',
            'role_title': 'Lead Jewelry Designer',
            'email': 'kavya.jewels@business.com',  # Card business email
            'phone': '+91 9876543210',
            'razorpay_payment_id': 'pay_demo_kavya_nfc_999',
            'razorpay_amount': '999',
            'nfc_ordered': 'true',
            'nfc_theme': 'obsidian_black',
            'nfc_foil': 'gold',
            'nfc_name': 'Kavya Nair',
            'nfc_designation': 'Lead Jewelry Designer',
            'nfc_company_name': 'Kavya Fine Jewels',
            'nfc_website': 'www.kavyajewels.com',
        }
        res_order = self.client.post(reverse('card_builder'), nfc_payload)
        self.assertEqual(res_order.status_code, 302)

        p_card = BusinessCard.objects.filter(user=personal_user).first()
        self.assertIsNotNone(p_card)

        # Verify email recipient resolution prioritizes signup/login email (pers.user.signup@gmail.com)
        self.assertEqual(get_user_notification_email(p_card), 'pers.user.signup@gmail.com')
        recipients = get_user_notification_recipients(p_card)
        self.assertIn('pers.user.signup@gmail.com', recipients)

        # Verify 'Order Placed' confirmation email was sent to user's signup email
        client_order_emails = [m for m in mail.outbox if 'pers.user.signup@gmail.com' in m.to]
        self.assertTrue(len(client_order_emails) > 0)
        order_msg = client_order_emails[0]
        self.assertIn('Order Placed', order_msg.subject)
        self.assertIn('Physical Contactless NFC Card Confirmed', order_msg.subject)
        self.assertIn('Kavya Nair', order_msg.body)
        self.assertIn('Kavya Fine Jewels', order_msg.body)
        self.assertIn('Obsidian Black', order_msg.body)
        self.assertIn('FULFILLMENT ROADMAP:', order_msg.body)

        # 2. Super Admin logs in and updates status across all 5 dropdown options
        self.client.force_login(admin)

        dropdown_statuses = [
            ('Printing & Engraving', 'UV laser bed running at facility'),
            ('Ready for Dispatch', 'Packed in velvet gift sleeve'),
            ('Shipped', 'BlueDart Express Tracking: BD98234120'),
            ('Delivered', 'Handed over at doorstep'),
            ('Order Placed', 'Re-queued upon client revision request'),
        ]

        for status_val, track_val in dropdown_statuses:
            mail.outbox.clear()
            update_res = self.client.post(
                reverse('dashboard_nfc_status_update', kwargs={'card_id': p_card.card_id}),
                {
                    'status': status_val,
                    'tracking_info': track_val,
                }
            )
            self.assertEqual(update_res.status_code, 302)

            # Check database updated
            p_card.refresh_from_db()
            self.assertEqual(p_card.layout_config['nfc_card']['status'], status_val)
            self.assertEqual(p_card.layout_config['nfc_card']['tracking_info'], track_val)

            # Check email was sent to user's signup/login email
            self.assertGreaterEqual(len(mail.outbox), 1)
            status_msg = [m for m in mail.outbox if 'pers.user.signup@gmail.com' in m.to][0]
            self.assertIn(status_val, status_msg.subject)
            self.assertIn(status_val, status_msg.body)
            self.assertIn('Kavya Fine Jewels', status_msg.subject)
            if track_val:
                self.assertIn(track_val, status_msg.body)

        # --- B. ENTERPRISE NFC CARD FLOW ---
        # Setup Enterprise Company & Employee Card
        ent_comp = EnterpriseCompany.objects.create(
            name='Vertex Global Tech',
            head_name='Vikram Singhania',
            email='vikram.ceo@vertex.com',
            card_quota=10
        )
        emp_user = User.objects.create_user(
            username='emp_tanya',
            email='tanya.sharma.login@gmail.com',
            password='EmpPass123!',
            first_name='Tanya',
            last_name='Sharma'
        )
        emp_card = BusinessCard.objects.create(
            user=emp_user,
            business_name='Vertex Global Tech',
            owner_name='Tanya Sharma',
            card_id='c_ent_tanya_nfc_01',
            enterprise_company=ent_comp,
            layout_config={
                'nfc_card': {
                    'ordered': True,
                    'theme': 'pearl_white',
                    'foil': 'silver',
                    'status': 'Order Placed',
                    'name': 'Tanya Sharma',
                    'designation': 'VP Product Architecture',
                    'company_name': 'Vertex Global Tech',
                }
            }
        )

        for status_val, track_val in dropdown_statuses:
            mail.outbox.clear()
            ent_update_res = self.client.post(
                reverse('enterprise_admin_nfc_status_update', kwargs={'card_id': emp_card.card_id}),
                {
                    'status': status_val,
                    'tracking_info': track_val,
                }
            )
            self.assertEqual(ent_update_res.status_code, 302)

            emp_card.refresh_from_db()
            self.assertEqual(emp_card.layout_config['nfc_card']['status'], status_val)
            self.assertEqual(emp_card.layout_config['nfc_card']['tracking_info'], track_val)

            # Check email was dispatched to employee's signup/login email
            self.assertGreaterEqual(len(mail.outbox), 1)
            ent_msg = [m for m in mail.outbox if 'tanya.sharma.login@gmail.com' in m.to][0]
            self.assertIn(status_val, ent_msg.subject)
            self.assertIn(status_val, ent_msg.body)
            self.assertIn('Vertex Global Tech', ent_msg.subject)
            if track_val:
                self.assertIn(track_val, ent_msg.body)





