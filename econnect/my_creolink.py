# -*- coding: utf-8 -*-

from econnect.navision import pull_invoices

__author__ = 'W1773ND (wilfriedwillend@gmail.com)'

from datetime import datetime, timedelta

import json
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.utils.translation import gettext as _
from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.accesscontrol.models import Member
from ikwen.core.models import Country
from ikwen.core.views import HybridListView, ChangeObjectBase
from ikwen.core.constants import STARTED

from econnect.admin import ProfileAdmin
from econnect.models import Order, CANCELED, Profile
from econnect.views import OrderConfirm

import logging

logger = logging.getLogger('ikwen')


class UncompletedOrderList(HybridListView):
    template_name = 'econnect/uncompleted_order_list.html'

    def get_queryset(self):
        member = self.request.user
        queryset = Order.objects.filter(member=member, status=STARTED)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(UncompletedOrderList, self).get_context_data(**kwargs)
        member = self.request.user
        queryset = Order.objects.filter(member=member, status=STARTED)
        context['uncompleted_order_list'] = queryset
        return context

    def get(self, request, *args, **kwargs):
        member = self.request.user
        queryset = Order.objects.filter(member=member, status=STARTED)
        if queryset.count() == 0:
            next_url = reverse('my_creolink')
            return HttpResponseRedirect(next_url)
        else:
            action = request.GET.get('action')
            if action == 'confirm_order':
                return OrderConfirm.confirm_order(request, *args, **kwargs)
                # return self.confirm_order(request)
            if action == 'cancel_order':
                return self.cancel_order(request)
            return super(UncompletedOrderList, self).get(request, *args, **kwargs)

    @staticmethod
    def cancel_order(request):
        order_id = request.GET['order_id']
        order = get_object_or_404(Order, id=order_id)
        order.status = CANCELED
        order.save()
        response = {"success": True}
        return HttpResponse(json.dumps(response), 'content-type: text/json')


class ProfileList(HybridListView):
    show_add = False
    change_object_url_name = 'change_profile'
    template_name = 'econnect/mycreolink/profile_list.html'

    def get_queryset(self):
        return Profile.objects.filter(member=self.request.user)


class ChangeProfile(ChangeObjectBase):
    model = Profile
    model_admin = ProfileAdmin
    template_name = 'econnect/mycreolink/change_profile.html'
    object_list_url = 'profile_list'

    def get(self, request, *args, **kwargs):
        email_verified = Member.objects.using(UMBRELLA).get(pk=request.user.id).email_verified
        if email_verified:
            # If email already verified in umbrella, report it to local database
            member = request.user
            member.email_verified = True
            member.propagate_changes()
        else:
            referrer = request.META.get('HTTP_REFERER', '/')
            next_url = reverse('ikwen:email_confirmation') + '?next=' + referrer
            return HttpResponseRedirect(next_url)
        action = request.GET.get('action')
        if action == 'check_code_and_pull_invoice':
            start_date = datetime.now() - timedelta(days=180)
            end_date = datetime.now()
            code = request.GET['code']
            try:
                profile = Profile.objects.get(code=code)
                if profile.member != request.user:
                    response = {'error': 'Attempt to use an already registered Client Code'}
                    return HttpResponse(json.dumps(response), 'content-type: text/json')
            except Profile.DoesNotExist:
                pass
            invoice_list, pending_count = pull_invoices(member=request.user, client_code=code,
                                                        start_date=start_date, end_date=end_date, send_mail=False)
            if len(invoice_list) == 0:
                response = {'error': 'Incorrect Client Code'}
            else:
                response = {'success': True}
            return HttpResponse(json.dumps(response), 'content-type: text/json')
        return super(ChangeProfile, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ChangeProfile, self).get_context_data(**kwargs)
        context['pending_count'] = self.request.session.get('pending_count')
        self.request.session['pending_count'] = 0
        return context

    def after_save(self, request, obj, *args, **kwargs):
        country_code = request.POST.get('country_code').strip()
        country = Country.objects.get(iso2__iexact=country_code)
        obj.country = country
        previous_code = request.POST.get('previous_code')
        if not obj.member:
            obj.member = request.user
        if previous_code != obj.code and obj.code_update_count < 2:
            obj.code = obj.code.strip().upper()
            obj.code_update_count += 1
            start_date = datetime.now() - timedelta(days=120)
            end_date = datetime.now()
            invoice_list, pending_count = pull_invoices(member=request.user, client_code=obj.code, start_date=start_date, end_date=end_date,
                                                        send_mail=False, dry_run=False)
            request.session['pending_count'] = pending_count
            messages.info(request, _("Import successful. You have %d pending invoices." % pending_count))
            obj.save()
            next_url = reverse('my_creolink')
            return HttpResponseRedirect(next_url)
        else:
            messages.error(request, _("You are not allowed to change Client Code more that twice."))
            obj.code = previous_code
            obj.save()

