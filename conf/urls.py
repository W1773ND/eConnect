from django.conf.urls import patterns, include, url

from django.contrib import admin
from django.contrib.auth.decorators import permission_required, user_passes_test, login_required
from ikwen.accesscontrol.utils import is_staff

from ikwen.billing.invoicing.views import InvoiceList

from ikwen_webnode.blog.views import AdminPostHome, ListCategory, ChangeCategory, ChangePost, CommentList

from ikwen.flatpages.views import ChangeFlatPage
from ikwen.flatpages.views import FlatPageList

from ikwen_kakocase.shopping.views import FlatPageView
from ikwen_kakocase.trade.provider.views import ProviderDashboard, CCMDashboard
from ikwen_kakocase.kakocase.views import AdminHome

from econnect.views import HomeView, UncompletedOrderList

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^laakam/', include(admin.site.urls)),
    url(r'^kakocase/', include('ikwen_kakocase.kakocase.urls', namespace='kakocase')),
    url(r'^kako/', include('ikwen_kakocase.kako.urls', namespace='kako')),
    url(r'^trade/', include('ikwen_kakocase.trade.urls', namespace='trade')),
    url(r'^MyCreolink/billing/', include('ikwen.billing.urls', namespace='billing')),
    url(r'^marketing/', include('ikwen_kakocase.commarketing.urls', namespace='marketing')),
    url(r'^sales/', include('ikwen_kakocase.sales.urls', namespace='sales')),
    url(r'^shopping/', include('ikwen_kakocase.shopping.urls', namespace='shopping')),

    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^currencies/', include('currencies.urls')),
    url(r'^items/', include('ikwen_webnode.items.urls', namespace='items')),
    url(r'^web/', include('ikwen_webnode.web.urls', namespace='web')),

    url(r'^blog/postlist/$', permission_required('flatpages.ik_webmaster')(AdminPostHome.as_view()), name='list_post'),
    url(r'^blog/postchange/$', permission_required('flatpages.ik_webmaster')(ChangePost.as_view()), name='change_post'),
    url(r'^blog/postchange/(?P<post_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangePost.as_view()), name='change_post'),
    url(r'^blog/list_categories/$', permission_required('flatpages.ik_webmaster')(ListCategory.as_view()),name='list_category'),
    url(r'^blog/changeCategory/$', permission_required('flatpages.ik_webmaster')(ChangeCategory.as_view()), name='change_category'),
    url(r'^blog/changeCategory/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeCategory.as_view()),name='change_category'),
    url(r'^blog/listcomments/$', permission_required('flatpages.ik_webmaster')(CommentList.as_view()), name='list_comment'),
    url(r'^blog/', include('ikwen_webnode.blog.urls', namespace='blog')),

    url(r'^MyCreolink/flatPages/$', permission_required('flatpages.ik_webmaster')(FlatPageList.as_view()), name='flatpage_list'),
    url(r'^MyCreolink/flatPage/$', permission_required('flatpages.ik_webmaster')(ChangeFlatPage.as_view()), name='change_flatpage'),
    url(r'^MyCreolink/flatPage/(?P<page_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeFlatPage.as_view()), name='change_flatpage'),

    url(r'^rewarding/', include('ikwen.rewarding.urls', namespace='rewarding')),

    url(r'^ikwen/dashboard/$', permission_required('trade.ik_view_dashboard')(ProviderDashboard.as_view()),
        name='dashboard'),
    url(r'^ikwen/CCMDashboard/$', permission_required('trade.ik_view_dashboard')(CCMDashboard.as_view()),
        name='ccm_dashboard'),
    url(r'^ikwen/theming/', include('ikwen.theming.urls', namespace='theming')),
    # url(r'^cci/', include('ikwen_kakocase.cci.urls', namespace='cci')),
    url(r'^ikwen/cashout/', include('ikwen.cashout.urls', namespace='cashout')),
    url(r'^MyCreolink/UncompleteOrder/$', login_required(UncompletedOrderList.as_view()), name='uncompleted_order'),
    url(r'^MyCreolink/console/$', login_required(InvoiceList.as_view()), name='console'),
    url(r'^MyCreolink/', include('ikwen.core.urls', namespace='ikwen')),
    url(r'^ikwen/home/$', user_passes_test(is_staff)(AdminHome.as_view()), name='admin_home'),
    url(r'^revival/', include('ikwen.revival.urls', namespace='revival')),

    url(r'^echo/', include('echo.urls', namespace='echo')),

    # url(r'^$', ProviderDashboard.as_view(), name='admin_home'),
    url(r'^page/(?P<url>[-\w]+)/$', FlatPageView.as_view(), name='flatpage'),

    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^webnode/$', include('ikwen_webnode.webnode.urls', namespace='webnode')),
    url(r'^', include('econnect.urls', namespace='econnect')),
)
