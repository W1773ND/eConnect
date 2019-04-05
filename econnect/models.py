from django.db import models
from django.db.models import Model
from django.utils.translation import gettext_lazy as _
from djangotoolbox.fields import ListField, EmbeddedModelField

from ikwen.core.models import Service, AbstractWatchModel
from ikwen.accesscontrol.models import Member


class ModelI18n(Model):

    language = models.CharField(max_length=6, blank=True, null=True)

    class Meta:
        abstract = True


class Product(ModelI18n):
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=250)
    summary = models.CharField(max_length=250)
    description = models.TextField(blank=True, null=True)
    installation_cost = models.IntegerField(default=0)
    logo = models.ImageField(blank=True, null=True,
                             help_text="150 x 150px")
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return self.name


class Package(ModelI18n):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=5)
    description = models.CharField(max_length=250)
    cost = models.IntegerField()
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.product) + ' ' + self.name

    def get_obj_details(self):
        return "%s | %s" % (self.description, self.cost)


class Equipment (ModelI18n):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=250)
    purchase_cost = models.IntegerField(default=0)
    rent_cost = models.IntegerField(default=0)
    is_purchased = models.BooleanField(default=True)
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.product) + ' | ' + self.name


class Extra(ModelI18n):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=250)
    cost = models.IntegerField(default=0)
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.product) + ' | ' + self.name


class AddOn(ModelI18n):
    product = models.ForeignKey(Product)
    equipment = models.ForeignKey(Equipment)
    extra = models.ForeignKey(Extra)


class Order(Model):
    member = models.ForeignKey(Member, related_name='+')
    product = models.ForeignKey(Package)
    addon_list = ListField(EmbeddedModelField('AddOn'))
    cost = models.IntegerField(default=0)


class CustomerRequest(Model):
    member = models.ForeignKey(Member, related_name='+')
    name = models.CharField(max_length=250)
    label = models.CharField(max_length=250, blank=False, null=False)

