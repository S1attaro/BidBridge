import re

from django.db import models
from django.urls import reverse
from django.utils import timezone

from . import codes


class Agency(models.Model):
    name = models.CharField(max_length=200)
    sub_tier = models.CharField(max_length=200, blank=True)
    office = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name_plural = "agencies"
        constraints = [
            models.UniqueConstraint(fields=["name", "sub_tier", "office"], name="unique_agency"),
        ]

    def __str__(self):
        return self.sub_tier or self.name

    @property
    def short_name(self):
        """The most useful single name. Sub-tier is usually the one people know (like "Army")."""
        name = codes.nice_case(self.sub_tier or self.name)
        # "Veterans Affairs, Department of" reads better as "Dept of Veterans Affairs".
        backwards = re.match(r"^(.+), Department of(?: the)?$", name, re.I)
        if backwards:
            name = f"Dept of {backwards.group(1)}"
        return name


class Contract(models.Model):
    notice_id = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=500)
    # A shorter title for lists. The full title is shown on the job's details.
    short_title = models.CharField(max_length=120, blank=True)
    solicitation_number = models.CharField(max_length=128, blank=True)
    agency = models.ForeignKey(Agency, null=True, blank=True, on_delete=models.SET_NULL, related_name="contracts")
    notice_type = models.CharField(max_length=80, blank=True)
    naics_code = models.CharField(max_length=10, blank=True, db_index=True)
    psc_code = models.CharField(max_length=10, blank=True)
    set_aside = models.CharField(max_length=20, blank=True)
    posted_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True, db_index=True)
    place_city = models.CharField(max_length=100, blank=True)
    place_state = models.CharField(max_length=2, blank=True, db_index=True)
    place_zip = models.CharField(max_length=10, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    award_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    sam_url = models.URLField(max_length=300, blank=True)
    description_text = models.TextField(blank=True)
    description_url = models.URLField(max_length=300, blank=True)
    description_fetched = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    is_demo = models.BooleanField(default=False)
    # Product buys (parts, food, supplies) are hidden. BidBridge is for on-site work.
    is_goods = models.BooleanField(default=False, db_index=True)
    # Agencies repost a job when they change it. Only the newest copy is shown.
    dupe_key = models.CharField(max_length=200, blank=True, db_index=True)
    is_repeat = models.BooleanField(default=False, db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return self.title

    @property
    def display_title(self):
        return self.short_title or self.title

    def tidy(self):
        """Fill in short_title, is_goods, and dupe_key from the other fields."""
        from .cleanup import dupe_key, is_goods, short_title
        self.short_title = short_title(self.title)[:120]
        self.is_goods = is_goods(self.psc_code, self.title)
        agency = self.agency
        self.dupe_key = dupe_key(self.solicitation_number, agency.name if agency else "", self.title,
                                 agency.office if agency else "", self.due_date)
        return self

    def get_absolute_url(self):
        return reverse("contracts:detail", args=[self.notice_id])

    @property
    def bid_url(self):
        """The public SAM.gov page for this exact notice. Works without signing in."""
        if self.is_demo:
            return ""
        return f"https://sam.gov/opp/{self.notice_id}/view"

    @property
    def trade_key(self):
        return codes.trade_for_naics(self.naics_code)[0]

    @property
    def trade_name(self):
        return codes.trade_for_naics(self.naics_code)[1]

    @property
    def set_aside_name(self):
        return codes.set_aside_name(self.set_aside)

    @property
    def notice_type_name(self):
        return codes.plain_notice_type(self.notice_type)

    @property
    def place(self):
        return ", ".join(p for p in [codes.nice_case(self.place_city), self.place_state] if p)

    @property
    def days_left(self):
        if not self.due_date:
            return None
        return (timezone.localtime(self.due_date).date() - timezone.localdate()).days

    @property
    def time_left(self):
        """Number and unit for the badge. Jobs closing today show hours, since days would say 0."""
        days = self.days_left
        if days is None:
            return ("", "")
        if days > 0:
            return (days, "day" if days == 1 else "days")
        hours = int((self.due_date - timezone.now()).total_seconds() // 3600)
        if hours < 1:
            return ("<1", "hr")
        return (hours, "hr" if hours == 1 else "hrs")

    @property
    def due_soon(self):
        days = self.days_left
        return days is not None and days <= 7


class BidClick(models.Model):
    """Someone clicked "Bid on SAM.gov". This is the main thing BidBridge is for."""

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="bid_clicks")
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    page = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.contract.notice_id} from {self.page}"


class ApiCall(models.Model):
    """One row per outside API call, so we can stay under the daily limits."""

    source = models.CharField(max_length=20)
    endpoint = models.CharField(max_length=500)
    ok = models.BooleanField(default=True)
    status = models.IntegerField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.source} {self.status} {self.created_at:%Y-%m-%d %H:%M}"
