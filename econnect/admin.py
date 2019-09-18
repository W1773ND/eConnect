from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class ProductAdmin(admin.ModelAdmin):
    fields = ('name', 'slogan', 'catchy', 'description', 'cta_label', 'install_cost', 'lang')


class PackageAdmin(admin.ModelAdmin):
    fields = ('product', 'type', 'name', 'target', 'optional_target_cost', 'summary', 'description', 'cost', 'duration',
              'duration_text')


class EquipmentAdmin(admin.ModelAdmin):
    fields = ('product', 'name', 'purchase_cost', 'rent_cost', 'is_purchased',)


class ExtraAdmin(admin.ModelAdmin):
    fields = ('product', 'name', 'cost',)


class FaqAdmin(admin.ModelAdmin):
    fields = ('product', 'question', 'answer',)


class AdvertisementAdmin(admin.ModelAdmin):
    fields = ('title', 'description', 'cta_label', 'cta_url', 'lang')


class ConfigAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'short_description', 'contact_email', 'contact_phone')
    fieldsets = (
        (_('General'), {'fields': ('company_name', 'short_description', 'slogan', 'description', 'payment_delay')}),
        (_('Address & Contact'), {'fields': ('contact_email', 'contact_phone', 'address', 'country', 'city')}),
        (_('Social'), {'fields': ('facebook_link', 'twitter_link', 'google_plus_link', 'instagram_link',
                                  'linkedin_link',)}),
        (_('Mailing'), {'fields': ('welcome_message', 'signature',)}),
    )
