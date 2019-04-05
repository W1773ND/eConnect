from django.db import models
from django.db.models import Model
from django.utils.translation import gettext_lazy as _
from djangotoolbox.fields import ListField, EmbeddedModelField

from ikwen.core.models import Service, AbstractWatchModel
from ikwen.accesscontrol.models import Member


class Product(AbstractWatchModel):
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=250)
    summary = models.CharField(max_length=250)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(blank=True, null=True,
                             help_text="150 x 150px")

    def __unicode__(self):
        return self.name


class Package(AbstractWatchModel):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=5)
    description = models.CharField(max_length=250)
    cost = models.IntegerField()
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.product) + ' ' + self.name

    def get_obj_details(self):
        return "%s | %s" % (self.description, self.cost)


class AddOn(AbstractWatchModel):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=250)
    INSTALLATION = 'Installation'
    EQUIPMENT = 'Equipment'
    EXTRA = 'Extra'
    TYPE_CHOICES = (
        (INSTALLATION, _('Installation')),
        (EQUIPMENT, _('Equipment')),
        (EXTRA, 'Extra')
    )
    type = models.CharField(max_length=250, choices=TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    cost = models.IntegerField(default=0)
    is_cyclic = models.BooleanField(default=True)

    def __unicode__(self):
        return str(self.product) + ' | ' + self.name


class Order(Model):
    member = models.ForeignKey(Member, related_name='+')
    product = models.ForeignKey(Package)
    addon_list = ListField(EmbeddedModelField('AddOn'))
    cost = models.IntegerField(default=0)


class CustomerRequest(Model):
    member = models.ForeignKey(Member, related_name='+')
    name = models.CharField(max_length=250)
    label = models.CharField(max_length=250, blank=False, null=False)

