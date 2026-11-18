import csv
import tempfile
from datetime import timedelta

from django.utils import timezone

from contracts.models import Agency, Contract

HEADER = [
    "NoticeId", "Title", "Sol#", "Department/Ind.Agency", "CGAC", "Sub-Tier", "FPDS Code", "Office",
    "AAC Code", "PostedDate", "Type", "BaseType", "ArchiveType", "ArchiveDate", "SetASideCode", "SetASide",
    "ResponseDeadLine", "NaicsCode", "ClassificationCode", "PopStreetAddress", "PopCity", "PopState", "PopZip",
    "PopCountry", "Active", "AwardNumber", "AwardDate", "Award$", "Awardee", "Link", "Description",
]


def day(n):
    return (timezone.localdate() + timedelta(days=n)).isoformat()


def sample_rows():
    """Six rows: three should be kept (n1, n2, n6)."""
    def row(nid, title, sub, ntype, set_aside, due, naics, city, state, active="Yes", link="", desc=""):
        return [nid, title, f"SOL-{nid}", "DEPT OF DEFENSE", "097", sub, "2100", "OFFICE A", "W7", day(-3) + " 10:00:00.000-05",
                ntype, "", "", "", set_aside, "", due, naics, "Z2", "", city, state, "61604", "USA", active,
                "", "", "", "", link, desc]

    return [
        row("n1", "Roof repair Building 5", "DEPT OF THE ARMY", "Solicitation", "SBA", day(20) + "T17:00:00-05:00",
            "238160", "Peoria", "IL", link="https://sam.gov/opp/n1/view", desc="Replace the roof on building 5."),
        row("n2", "Janitorial services", "PUBLIC BUILDINGS SERVICE", "Combined Synopsis/Solicitation", "",
            day(10) + "T14:00:00-05:00", "561720", "Chicago", "IL",
            desc="https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=n2"),
        row("n3", "Old award", "DEPT OF THE NAVY", "Award Notice", "", day(10) + "T14:00:00-05:00", "238160", "Norfolk", "VA"),
        row("n4", "Past due lawn care", "FOREST SERVICE", "Solicitation", "SBA", day(-1) + "T14:00:00-05:00",
            "561730", "Marion", "IL"),
        row("n5", "Inactive HVAC", "DEPT OF THE ARMY", "Solicitation", "", day(20) + "T17:00:00-05:00", "238220",
            "Austin", "TX", active="No"),
        row("n6", "HVAC in Texas", "DEPT OF THE ARMY", "Sources Sought", "SDVOSBC", day(15) + "T17:00:00-05:00",
            "238220", "Austin", "TX", desc="Need HVAC help."),
    ]


def write_csv(rows=None, header=None, encoding="utf-8"):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding=encoding)
    with f:
        writer = csv.writer(f)
        writer.writerow(header or HEADER)
        writer.writerows(rows if rows is not None else sample_rows())
    return f.name


def make_contract(notice_id, title="Roof repair", naics="238160", state="IL", city="PEORIA", set_aside="SBA",
                  due_days=10, posted_days=-2, text="", **extra):
    agency, _ = Agency.objects.get_or_create(name="DEPT OF DEFENSE", sub_tier="DEPT OF THE ARMY", office="W7")
    now = timezone.now()
    return Contract.objects.create(
        notice_id=notice_id, title=title, naics_code=naics, place_state=state, place_city=city,
        set_aside=set_aside, agency=agency, notice_type="Solicitation",
        due_date=now + timedelta(days=due_days), posted_date=now + timedelta(days=posted_days),
        description_text=text, **extra,
    )
