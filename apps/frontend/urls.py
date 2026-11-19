from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    
    # User Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Module 1: Business Card Builder, Plans, Enterprise Bundles, Edit, Delete & Manager
    path('card/choose/', views.card_choose_plan, name='card_choose_plan'),
    path('api/youtube-channel-info/', views.fetch_youtube_channel_info_api, name='api_youtube_channel_info'),
    path('enterprise/company/', views.enterprise_company, name='enterprise_company'),
    path('enterprise/checkout/', views.enterprise_checkout, name='enterprise_checkout'),
    path('enterprise/topup/', views.enterprise_topup, name='enterprise_topup'),
    path('enterprise/add-user/', views.enterprise_add_user, name='enterprise_add_user'),
    path('enterprise/remove-user/<int:user_id>/', views.enterprise_remove_user, name='enterprise_remove_user'),
    path('cards/', views.card_list, name='card_list'),
    path('card/create/', views.card_builder, name='card_builder'),
    path('card/edit/<str:card_id>/', views.card_builder, name='card_edit'),
    path('card/delete/<str:card_id>/', views.card_delete, name='card_delete'),
    path('card/preview/<str:card_id>/', views.card_preview, name='card_preview'),
    path('card/<slug:slug>/qr.png', views.card_qr_image, name='card_qr_image'),
    path('card/<slug:slug>/', views.card_standalone, name='card_standalone'),

    # Module 2: Website Builder & Preview
    path('website/create/', views.website_builder, name='website_builder'),
    path('website/preview/<str:site_id>/', views.website_preview, name='website_preview'),
    path('site/<slug:slug>/', views.website_standalone, name='website_standalone'),

    # Public Card Interaction & Tracking Endpoints
    path('card/<slug:slug>/lead/', views.record_card_lead, name='record_card_lead'),
    path('card/<slug:slug>/track/<str:event_type>/', views.record_card_event, name='record_card_event'),

    # BrandNest Dedicated Admin Auth & Gateway
    path('admin/login/', views.admin_login_view, name='admin_login'),
    path('admin/logout/', views.admin_logout_view, name='admin_logout'),

    # BrandNest Modern Dashboard & Admin Portal
    path('dashboard/', views.dashboard_overview, name='dashboard_home'),
    path('dashboard/overview/', views.dashboard_overview, name='dashboard_overview'),
    path('dashboard/cards/', views.dashboard_cards, name='dashboard_cards'),
    path('dashboard/qr-codes/', views.dashboard_qr_codes, name='dashboard_qr_codes'),
    path('dashboard/contacts/', views.dashboard_contacts, name='dashboard_contacts'),
    path('dashboard/contacts/add/', views.dashboard_contacts_add, name='dashboard_contacts_add'),
    path('dashboard/messages/', views.dashboard_messages, name='dashboard_messages'),
    path('dashboard/nfc/', views.dashboard_nfc, name='dashboard_nfc'),
    path('dashboard/nfc/add/', views.dashboard_nfc_add, name='dashboard_nfc_add'),
    path('dashboard/nfc/update/<int:tag_id>/', views.dashboard_nfc_update, name='dashboard_nfc_update'),
    path('dashboard/nfc/toggle/<int:tag_id>/', views.dashboard_nfc_toggle_active, name='dashboard_nfc_toggle_active'),
    path('dashboard/wallet-pass/', views.dashboard_wallet_pass, name='dashboard_wallet_pass'),
    path('dashboard/analytics/', views.dashboard_analytics, name='dashboard_analytics'),
    path('dashboard/teams/', views.dashboard_teams, name='dashboard_teams'),
    path('dashboard/teams/add/', views.dashboard_teams_add, name='dashboard_teams_add'),
    path('dashboard/teams/rename/<int:team_id>/', views.dashboard_teams_rename, name='dashboard_teams_rename'),
    path('dashboard/users/', views.dashboard_users, name='dashboard_users'),
    path('dashboard/users/add/', views.dashboard_users_add, name='dashboard_users_add'),
    path('dashboard/leads/', views.dashboard_leads, name='dashboard_leads'),
    path('dashboard/leads/export/', views.dashboard_leads_export, name='dashboard_leads_export'),
    path('dashboard/settings/', views.dashboard_settings, name='dashboard_settings'),
    path('dashboard/settings/business/', views.dashboard_settings_save_business, name='dashboard_settings_save_business'),
    path('dashboard/settings/contact/', views.dashboard_settings_save_contact, name='dashboard_settings_save_contact'),
    path('dashboard/settings/address/', views.dashboard_settings_save_address, name='dashboard_settings_save_address'),
    path('dashboard/settings/branding/', views.dashboard_settings_save_branding, name='dashboard_settings_save_branding'),
    path('dashboard/virtual-background/', views.dashboard_virtual_bg, name='dashboard_virtual_bg'),
    path('dashboard/email-signature/', views.dashboard_email_sig, name='dashboard_email_sig'),
    path('dashboard/templates/', views.dashboard_templates, name='dashboard_templates'),
    path('dashboard/accessories/', views.dashboard_accessories, name='dashboard_accessories'),
    path('dashboard/integrations/', views.dashboard_integrations, name='dashboard_integrations'),

    # BrandNest Enterprise Super Admin Suite
    path('enterprise-admin/', views.enterprise_admin_overview, name='enterprise_admin_overview'),
    path('enterprise-admin/companies/', views.enterprise_admin_companies, name='enterprise_admin_companies'),
    path('enterprise-admin/companies/create/', views.enterprise_admin_company_create, name='enterprise_admin_company_create'),
    path('enterprise-admin/companies/quota/<int:company_id>/', views.enterprise_admin_company_quota, name='enterprise_admin_company_quota'),
    path('enterprise-admin/companies/toggle/<int:company_id>/', views.enterprise_admin_company_toggle, name='enterprise_admin_company_toggle'),
    path('enterprise-admin/cards/', views.enterprise_admin_cards, name='enterprise_admin_cards'),
    path('enterprise-admin/cards/issue/', views.enterprise_admin_card_issue, name='enterprise_admin_card_issue'),
    path('enterprise-admin/teams/', views.enterprise_admin_teams, name='enterprise_admin_teams'),
    path('enterprise-admin/teams/add/', views.enterprise_admin_teams_add, name='enterprise_admin_teams_add'),
    path('enterprise-admin/leads/', views.enterprise_admin_leads, name='enterprise_admin_leads'),
    path('enterprise-admin/leads/export/', views.enterprise_admin_leads_export, name='enterprise_admin_leads_export'),
    path('enterprise-admin/billing/', views.enterprise_admin_billing, name='enterprise_admin_billing'),
]

