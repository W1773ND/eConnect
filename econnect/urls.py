from django.conf.urls import url, patterns
from django.contrib.auth.decorators import permission_required, login_required

from ikwen.billing.invoicing.views import InvoiceList

from econnect.collect import confirm_invoice_payment
from econnect.utils import get_media, delete_tinyMCE_photo
from econnect.views import Admin, HomeView, Numerilink, NumerilinkHotel, Homelink, Officelink, Corporatelink, \
    PricingNumerilink, PricingNumerilinkHotel, PendingOrderList, PaidOrderList, \
    CustomerRequestList, ChangeProduct, ProductList, ChangePackage, PackageList, EquipmentList, ChangeEquipment, \
    ExtraList, ChangeExtra, PricingOfficelink, PricingHomelink, PricingCorporatelink, Maps, \
    OrderConfirm, ChangeMailCampaign, ReportedOrderList, About, Legal, Privacy, Offline, CanceledOrderList

urlpatterns = patterns(
    '',
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^offline.html$', Offline.as_view(), name='offline'),
    url(r'^about/$', About.as_view(), name='about'),
    url(r'^legal/$', Legal.as_view(), name='legal'),
    url(r'^privacy/$', Privacy.as_view(), name='privacy'),
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
    url(r'^MyCreolink/$', login_required(InvoiceList.as_view()), name='my_creolink'),
    url(r'^confirm_invoice_payment/(?P<tx_id>[-\w]+)$', confirm_invoice_payment, name='confirm_invoice_payment'),
    url(r'^admin/home/$', permission_required('econnect.ik_econnect_admin')(Admin.as_view()), name='admin'),
    url(r'^products/$', permission_required('econnect.ik_econnect_admin')(ProductList.as_view()), name='product_list'),
    url(r'^product/$', permission_required('econnect.ik_econnect_admin')(ChangeProduct.as_view()), name='change_product'),
    url(r'^product/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeProduct.as_view()), name='change_product'),
    url(r'^packages/$', permission_required('econnect.ik_econnect_admin')(PackageList.as_view()), name='package_list'),
    url(r'^package/$', permission_required('econnect.ik_econnect_admin')(ChangePackage.as_view()), name='change_package'),
    url(r'^package/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangePackage.as_view()), name='change_package'),
    url(r'^equipments/$', permission_required('econnect.ik_econnect_admin')(EquipmentList.as_view()), name='equipment_list'),
    url(r'^equipment/$', permission_required('econnect.ik_econnect_admin')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^equipment/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^extras/$', permission_required('econnect.ik_econnect_admin')(ExtraList.as_view()), name='extra_list'),
    url(r'^extra/$', permission_required('econnect.ik_econnect_admin')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^extra/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^admin/pendingOrder$', permission_required('econnect.ik_econnect_admin')(PendingOrderList.as_view()), name='pending_order'),
    url(r'^admin/paidOrder$', permission_required('econnect.ik_econnect_admin')(PaidOrderList.as_view()), name='paid_order'),
    url(r'^admin/reportedOrder$', permission_required('econnect.ik_econnect_admin')(ReportedOrderList.as_view()), name='reported_order'),
    url(r'^admin/canceledOrder$', permission_required('econnect.ik_econnect_admin')(CanceledOrderList.as_view()), name='canceled_order'),
    url(r'^mailCampaign/$', permission_required('echo.ik_messaging_campaign')(ChangeMailCampaign.as_view()), name='change_mailcampaign'),
    url(r'^mailCampaign/(?P<object_id>[-\w]+)/$', permission_required('echo.ik_messaging_campaign')(ChangeMailCampaign.as_view()), name='change_mailcampaign'),
    url(r'^admin/customerRequest$', permission_required('econnect.ik_econnect_admin')(CustomerRequestList.as_view()), name='admin_request'),
    url(r'^get_media$', get_media, name='get_media'),
    url(r'^delete_tinymce_photo', delete_tinyMCE_photo, name='delete_tinymce_photo'),
)
