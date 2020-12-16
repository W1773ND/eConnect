from django.conf.urls import url, patterns
from django.contrib.auth.decorators import permission_required, login_required

from econnect.collect import confirm_invoice_payment
from econnect.utils import get_media, delete_tinyMCE_photo
from econnect.views import HomeView, Numerilink, NumerilinkHotel, Homelink, Officelink, Corporatelink, \
    PricingNumerilink, PricingNumerilinkHotel, ChangeProduct, ProductList, ChangePackage, PackageList, EquipmentList,\
    ChangeEquipment, ExtraList, ChangeExtra, PricingOfficelink, PricingHomelink, PricingCorporatelink, Maps, \
    OrderConfirm, ChangeMailCampaign, Offline, FaqList, ChangeFaq, ChangeAdvertisement, AdvertisementList

urlpatterns = patterns(
    '',
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^offline.html$', Offline.as_view(), name='offline'),
    url(r'^NumerilinkHome/$', Numerilink.as_view(), name='numerilink-home'),
    url(r'^NumerilinkHotel/$', NumerilinkHotel.as_view(), name='numerilink-hotel'),
    url(r'^Officelink/$', Officelink.as_view(), name='officelink'),
    url(r'^Homelink/$', Homelink.as_view(), name='homelink'),
    url(r'^Corporatelink/$', Corporatelink.as_view(), name='corporatelink'),
    url(r'^NumerilinkHome/order/$', PricingNumerilink.as_view(), name='numerilink-home-pricing'),
    url(r'^NumerilinkHotel/order/$', PricingNumerilinkHotel.as_view(), name='numerilink-hotel-pricing'),
    url(r'^Homelink/order/$', PricingHomelink.as_view(), name='homelink-pricing'),
    url(r'^Officelink/order/$', PricingOfficelink.as_view(), name='officelink-pricing'),
    url(r'^Corporatelink/order/$', PricingCorporatelink.as_view(), name='corporatelink-pricing'),
    url(r'^maps$', login_required(Maps.as_view()), name='maps'),
    url(r'^OrderConfirm/$', login_required(OrderConfirm.as_view()), name='order_confirm'),


    url(r'^confirm_invoice_payment/(?P<tx_id>[-\w]+)/(?P<signature>[-\w]+)/(?P<lang>[-\w]+)$', confirm_invoice_payment, name='confirm_invoice_payment'),

    url(r'^products/$', permission_required('flatpages.ik_webmaster')(ProductList.as_view()), name='product_list'),
    url(r'^product/$', permission_required('flatpages.ik_webmaster')(ChangeProduct.as_view()), name='change_product'),
    url(r'^product/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeProduct.as_view()), name='change_product'),
    url(r'^packages/$', permission_required('flatpages.ik_webmaster')(PackageList.as_view()), name='package_list'),
    url(r'^package/$', permission_required('flatpages.ik_webmaster')(ChangePackage.as_view()), name='change_package'),
    url(r'^package/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangePackage.as_view()), name='change_package'),
    url(r'^equipments/$', permission_required('flatpages.ik_webmaster')(EquipmentList.as_view()), name='equipment_list'),
    url(r'^equipment/$', permission_required('flatpages.ik_webmaster')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^equipment/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^extras/$', permission_required('flatpages.ik_webmaster')(ExtraList.as_view()), name='extra_list'),
    url(r'^extra/$', permission_required('flatpages.ik_webmaster')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^extra/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^faqs/$', permission_required('flatpages.ik_webmaster')(FaqList.as_view()), name='faq_list'),
    url(r'^faq/$', permission_required('flatpages.ik_webmaster')(ChangeFaq.as_view()), name='change_faq'),
    url(r'^faq/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeFaq.as_view()), name='change_faq'),
    url(r'^advertisements/$', permission_required('flatpages.ik_webmaster')(AdvertisementList.as_view()), name='advertisement_list'),
    url(r'^advertisement/$', permission_required('flatpages.ik_webmaster')(ChangeAdvertisement.as_view()), name='change_advertisement'),
    url(r'^advertisement/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeAdvertisement.as_view()), name='change_advertisement'),
    url(r'^mailCampaign/$', permission_required('econnect.ik_sav')(ChangeMailCampaign.as_view()), name='change_mailcampaign'),
    url(r'^mailCampaign/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_sav')(ChangeMailCampaign.as_view()), name='change_mailcampaign'),

    url(r'^get_media$', get_media, name='get_media'),
    url(r'^delete_tinymce_photo', delete_tinyMCE_photo, name='delete_tinymce_photo'),
)
