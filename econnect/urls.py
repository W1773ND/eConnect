from django.conf.urls import url, patterns
from django.contrib.auth.decorators import permission_required, login_required

from ikwen.billing.invoicing.views import InvoiceList
from econnect.views import Admin, HomeView, PricingNumerilink, PricingNumerilinkHotel, PendingOrderList, PaidOrderList, \
    CustomerRequestList, ChangeProduct, ProductList, ChangePackage, PackageList, EquipmentList, ChangeEquipment, \
    ExtraList, ChangeExtra, PricingOfficelink, PricingHomelink, PricingCorporatelink, Maps, \
    OrderConfirm, ChangeMailCampaign, ReportedOrderList

urlpatterns = patterns(
    '',
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^numerilink_home/$', PricingNumerilink.as_view(), name='numerilink-home'),
    url(r'^numerilink_hotel/$', PricingNumerilinkHotel.as_view(), name='numerilink-hotel'),
    url(r'^officelink/$', PricingOfficelink.as_view(), name='officelink'),
    url(r'^homelink/$', PricingHomelink.as_view(), name='homelink'),
    url(r'^corporatelink/$', PricingCorporatelink.as_view(), name='corporatelink'),
    url(r'^maps$', login_required(Maps.as_view()), name='maps'),
    url(r'^order_confirm/$', login_required(OrderConfirm.as_view()), name='order_confirm'),
    url(r'^MyCreolink/$', login_required(InvoiceList.as_view()), name='my_creolink'),
    url(r'^admin/home/$', permission_required('econnect.ik_econnect_admin')(Admin.as_view()), name='admin'),
    url(r'^product_list/$', permission_required('econnect.ik_econnect_admin')(ProductList.as_view()), name='product_list'),
    url(r'^product/$', permission_required('econnect.ik_econnect_admin')(ChangeProduct.as_view()), name='change_product'),
    url(r'^product/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeProduct.as_view()), name='change_product'),
    url(r'^package_list/$', permission_required('econnect.ik_econnect_admin')(PackageList.as_view()), name='package_list'),
    url(r'^package/$', permission_required('econnect.ik_econnect_admin')(ChangePackage.as_view()), name='change_package'),
    url(r'^package/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangePackage.as_view()), name='change_package'),
    url(r'^equipment_list/$', permission_required('econnect.ik_econnect_admin')(EquipmentList.as_view()), name='equipment_list'),
    url(r'^equipment/$', permission_required('econnect.ik_econnect_admin')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^equipment/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^extra_list/$', permission_required('econnect.ik_econnect_admin')(ExtraList.as_view()), name='extra_list'),
    url(r'^extra/$', permission_required('econnect.ik_econnect_admin')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^extra/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^admin/pending_order$', permission_required('econnect.ik_econnect_admin')(PendingOrderList.as_view()), name='pending_order'),
    url(r'^admin/paid_order$', permission_required('econnect.ik_econnect_admin')(PaidOrderList.as_view()), name='paid_order'),
    url(r'^admin/reported_order$', permission_required('econnect.ik_econnect_admin')(ReportedOrderList.as_view()), name='reported_order'),
    url(r'^mailCampaign/$', permission_required('echo.ik_messaging_campaign')(ChangeMailCampaign.as_view()), name='change_mailcampaign'),
    url(r'^mailCampaign/(?P<object_id>[-\w]+)/$', permission_required('echo.ik_messaging_campaign')(ChangeMailCampaign.as_view()), name='change_mailcampaign'),
    url(r'^admin/customer_request$', permission_required('econnect.ik_econnect_admin')(CustomerRequestList.as_view()), name='admin_request'),
)
