import json
from django.test import TestCase, Client
from django.urls import reverse
from apps.domains.models import Domain
from apps.cards.models import BusinessCard, UserPlan
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
        self.assertContains(res, "Make your website")

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

        # Step 2: Purchase 5-card Enterprise bundle
        checkout_post = self.client.post(reverse('enterprise_checkout'), {'bundle_size': '5'})
        self.assertEqual(checkout_post.status_code, 302)
        self.assertEqual(checkout_post['Location'], reverse('card_list'))

        plan = UserPlan.objects.get(user=ent_user)
        self.assertEqual(plan.plan_type, 'enterprise')
        self.assertEqual(plan.company_name, 'Apex Global Corp')
        self.assertEqual(plan.card_limit, 5)

        # Step 3: Create 5 cards (owner + 4 team) -> each creation redirects back to /cards/
        for i in range(5):
            r = self.client.post(reverse('card_builder'), {'business_name': f'Team Member {i+1}'})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(r['Location'], reverse('card_list'))

        # 6th attempt redirects to /cards/?upgrade=1 and shows top-up modal
        sixth_attempt = self.client.get(reverse('card_builder'))
        self.assertEqual(sixth_attempt.status_code, 302)
        self.assertIn('/cards/?upgrade=1', sixth_attempt['Location'])

        list_res = self.client.get(reverse('card_list') + '?upgrade=1')
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, 'Add More Business Cards')
        self.assertContains(list_res, '5 / 5')

        # Top up with +5 more cards
        topup_res = self.client.post(reverse('enterprise_topup'), {'extra_cards': '5'})
        self.assertEqual(topup_res.status_code, 302)
        self.assertEqual(topup_res['Location'], reverse('card_builder'))

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
