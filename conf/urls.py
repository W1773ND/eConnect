from django.conf.urls import patterns, include, url

from django.contrib import admin
from django.contrib.auth.decorators import permission_required

from ikwen_webnode.blog.views import AdminPostHome, ListCategory, ChangeCategory, ChangePost, CommentList
from ikwen_kakocase.shopping.views import FlatPageView


from econnect.views import HomeView

admin.autodiscover()

urlpatterns = patterns(
    '',
    # url(r'^laakam/', include(admin.site.urls)),

    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^currencies/', include('currencies.urls')),

    url(r'^kakocase/', include('ikwen_kakocase.kakocase.urls', namespace='kakocase')),
    url(r'^kako/', include('ikwen_kakocase.kako.urls', namespace='kako')),
    url(r'^trade/', include('ikwen_kakocase.trade.urls', namespace='trade')),
    url(r'^marketing/', include('ikwen_kakocase.commarketing.urls', namespace='marketing')),
    url(r'^sales/', include('ikwen_kakocase.sales.urls', namespace='sales')),
    url(r'^shopping/', include('ikwen_kakocase.shopping.urls', namespace='shopping')),

    url(r'^rewarding/', include('ikwen.rewarding.urls', namespace='rewarding')),

    url(r'^items/', include('ikwen_webnode.items.urls', namespace='items')),
    url(r'^webnode/$', include('ikwen_webnode.webnode.urls', namespace='webnode')),
    url(r'^web/', include('ikwen_webnode.web.urls', namespace='web')),

    url(r'^blog/postlist/$', permission_required('flatpages.ik_webmaster')(AdminPostHome.as_view()), name='list_post'),
    url(r'^blog/postchange/$', permission_required('flatpages.ik_webmaster')(ChangePost.as_view()), name='change_post'),
    url(r'^blog/postchange/(?P<post_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangePost.as_view()), name='change_post'),
    url(r'^blog/list_categories/$', permission_required('flatpages.ik_webmaster')(ListCategory.as_view()),name='list_category'),
    url(r'^blog/changeCategory/$', permission_required('flatpages.ik_webmaster')(ChangeCategory.as_view()), name='change_category'),
    url(r'^blog/changeCategory/(?P<object_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeCategory.as_view()),name='change_category'),
    url(r'^blog/listcomments/$', permission_required('flatpages.ik_webmaster')(CommentList.as_view()), name='list_comment'),
    url(r'^blog/', include('ikwen_webnode.blog.urls', namespace='blog')),

    url(r'^STAFF/', include('conf.staff_url')),

    # url(r'^ikwen/dashboard/$', permission_required('trade.ik_view_dashboard')(ProviderDashboard.as_view()),
    #     name='dashboard'),
    # url(r'^ikwen/CCMDashboard/$', permission_required('trade.ik_view_dashboard')(CCMDashboard.as_view()),
    #     name='ccm_dashboard'),

    # url(r'^ikwen/theming/', include('ikwen.theming.urls', namespace='theming')),
    # url(r'^cci/', include('ikwen_kakocase.cci.urls', namespace='cci')),


    url(r'^MyCreolink/', include('conf.my_creolink_url')),

    # url(r'^ikwen/cashout/', include('ikwen.cashout.urls', namespace='cashout')),
    url(r'^revival/', include('ikwen.revival.urls', namespace='revival')),

    url(r'^echo/', include('echo.urls', namespace='echo')),

    url(r'^page/(?P<url>[-\w]+)/$', FlatPageView.as_view(), name='flatpage'),

    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^', include('econnect.urls', namespace='econnect')),
)
