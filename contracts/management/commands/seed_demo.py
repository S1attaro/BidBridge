"""Add a small set of DEMO contracts so the site works with no data download and no keys.

These are made up. They are marked is_demo=True and labeled "Demo" on the site.
Run `python manage.py seed_demo --clear` to remove them.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts import geo
from contracts.models import Agency, Contract

AGENCIES = [
    ("DEPT OF DEFENSE", "DEPT OF THE ARMY", "W7NV USPFO ACTIVITY IL ARNG"),
    ("DEPT OF DEFENSE", "DEPT OF THE AIR FORCE", "FA4407 375 CONS"),
    ("VETERANS AFFAIRS, DEPARTMENT OF", "VETERANS AFFAIRS, DEPARTMENT OF", "NETWORK CONTRACT OFFICE 12"),
    ("AGRICULTURE, DEPARTMENT OF", "FOREST SERVICE", "USDA-FS, CSA EAST 5"),
    ("INTERIOR, DEPARTMENT OF THE", "NATIONAL PARK SERVICE", "MWR MIDWEST REGION"),
    ("GENERAL SERVICES ADMINISTRATION", "PUBLIC BUILDINGS SERVICE", "PBS R5 GREAT LAKES"),
    ("HOMELAND SECURITY, DEPARTMENT OF", "US COAST GUARD", "BASE DETROIT"),
]

# title, naics, set-aside, city, state, zip, days until due, agency index, description
CONTRACTS = [
    ("Roof Replacement, Building 12, Scott AFB", "238160", "SBA", "Scott AFB", "IL", "62225", 21, 1,
     "The contractor shall furnish all labor, materials, and equipment to remove and replace approximately "
     "14,000 square feet of built-up roofing on Building 12. Work includes tear-off, insulation, new TPO membrane, "
     "flashing, and gutters. A site visit will be held. Contractor must hold a current roofing license and provide "
     "a 20-year manufacturer warranty. Work must be finished within 90 days of notice to proceed."),
    ("Roof Repairs at VA Medical Center", "238160", "SDVOSBC", "Danville", "IL", "61832", 12, 2,
     "Repair leaks on three hospital buildings. Replace damaged shingles and flashing, seal penetrations, and "
     "inspect drains. Work must not disrupt patient care. Contractor must complete VA safety training."),
    ("Reroof Reserve Center", "238160", "", "Peoria", "IL", "61604", 30, 0,
     "Remove existing shingle roof and install new architectural shingles on a 6,500 square foot training "
     "building. Bonding is required. Performance period is 60 days."),
    ("HVAC Preventive Maintenance, Federal Building", "238220", "SBA", "Chicago", "IL", "60604", 18, 5,
     "Provide monthly preventive maintenance and on-call repairs for chillers, boilers, air handlers, and "
     "controls in a 20-story federal building. Base year plus four option years. Technicians must hold EPA "
     "Section 608 certification."),
    ("Replace Rooftop HVAC Units", "238220", "HZC", "Rockford", "IL", "61101", 9, 0,
     "Remove two 15-ton rooftop units and install new high efficiency units with crane service. Include "
     "ductwork changes, startup, and testing. Work hours are 7 AM to 4 PM on weekdays."),
    ("Boiler Repair, Ranger Station", "238220", "SBA", "Marion", "IL", "62959", 5, 3,
     "Repair or replace the hot water boiler at the ranger station. Include parts, labor, and a one-year warranty."),
    ("Janitorial Services, Social Security Office", "561720", "SBA", "Springfield", "IL", "62701", 25, 5,
     "Provide daily cleaning for an 8,000 square foot office: trash, restrooms, floors, and windows. Five days a "
     "week after 5 PM. Base year plus four option years. Staff must pass a background check."),
    ("Custodial Services, Army Reserve Center", "561720", "WOSB", "Joliet", "IL", "60435", 16, 0,
     "Clean offices, restrooms, drill hall, and break rooms three times a week. Contractor supplies all cleaning "
     "products and equipment."),
    ("Janitorial Services, VA Clinic", "561720", "SDVOSBC", "Indianapolis", "IN", "46202", 20, 2,
     "Daily cleaning of a 12,000 square foot outpatient clinic, including infection control cleaning of exam rooms."),
    ("Grounds Maintenance, National Cemetery", "561730", "SBA", "Elwood", "IL", "60421", 28, 2,
     "Mow, trim, and edge about 300 acres from April to October. Includes leaf removal and snow removal on "
     "roads in winter. Contractor provides all mowers and equipment."),
    ("Lawn Care and Snow Removal, Federal Courthouse", "561730", "SBA", "Urbana", "IL", "61801", 14, 5,
     "Weekly lawn care in season and snow plowing and salting of parking lot and sidewalks from November to March."),
    ("Landscape Maintenance, Lock and Dam 15", "561730", "", "Rock Island", "IL", "61201", 33, 0,
     "Mowing, trimming, weed control, and tree care around the lock and dam visitor area."),
    ("Interior Painting, Training Building", "238320", "SBA", "Springfield", "IL", "62707", 11, 0,
     "Prep and paint walls, doors, and trim in about 22,000 square feet of offices and classrooms. Low VOC paint. "
     "Work after hours."),
    ("Painting of Visitor Center", "238320", "SBA", "Porter", "IN", "46304", 24, 4,
     "Exterior painting of the visitor center and two restroom buildings. Scrape, prime, and paint wood siding."),
    ("Electrical Upgrades, Hangar 3", "238210", "SBA", "Scott AFB", "IL", "62225", 19, 1,
     "Replace lighting with LED fixtures and upgrade the main electrical panel in Hangar 3. Licensed electricians "
     "only."),
    ("Parking Lot Repaving", "238110", "SBA", "Champaign", "IL", "61820", 22, 5,
     "Mill and overlay 40,000 square feet of asphalt parking lot. Restripe and replace curb stops."),
    ("Concrete Sidewalk Replacement", "238110", "HZC", "Milwaukee", "WI", "53202", 8, 6,
     "Remove and replace about 1,200 square feet of damaged concrete sidewalk and two ADA ramps."),
    ("IT Help Desk Support", "541519", "SBA", "Chicago", "IL", "60605", 27, 5,
     "Provide tier 1 and tier 2 help desk support for about 400 users. Phone, email, and walk-up support from "
     "7 AM to 6 PM. Staff need CompTIA A+ or similar."),
    ("Network Cabling, Office Move", "541512", "8A", "Arlington", "VA", "22202", 15, 5,
     "Install about 250 Cat6 data drops, patch panels, and wireless access points for an office move."),
    ("Pest Control Services", "561710", "SBA", "Great Lakes", "IL", "60088", 13, 0,
     "Monthly pest control for 30 buildings, including rodents, insects, and birds. Licensed applicator required."),
    ("Security Guard Services, Federal Building", "561612", "SBA", "Peoria", "IL", "61602", 26, 5,
     "Two armed guards, Monday to Friday, 7 AM to 6 PM. Guards must pass federal background checks."),
    ("Trash and Recycling Pickup", "562111", "SBA", "Fort Sheridan", "IL", "60037", 17, 0,
     "Weekly trash and recycling pickup from 10 dumpsters. Provide containers."),
    ("Office Supplies, Blanket Purchase Agreement", "424120", "SBA", "Chicago", "IL", "60604", 10, 5,
     "Supply paper, toner, and general office supplies on an as-needed basis with delivery within 2 business days."),
    ("Kitchen Floor Replacement, VA Hospital", "238330", "SDVOSBC", "Hines", "IL", "60141", 23, 2,
     "Remove old tile and install a seamless epoxy floor in the main kitchen. Work must be phased to keep the "
     "kitchen open."),
    ("Building Repairs, Coast Guard Station", "236220", "SBA", "Detroit", "MI", "48207", 31, 6,
     "General repairs: replace doors and windows, patch drywall, and repair the boat house siding."),
    ("Snow Removal Services", "561790", "SBA", "Arlington Heights", "IL", "60004", 6, 0,
     "Plow and salt parking lots and sidewalks when snow is over 2 inches, November through April."),
    ("Roof Inspection and Repair, Post Office", "238160", "SBA", "Austin", "TX", "78701", 18, 5,
     "Inspect and repair a low-slope roof on a post office. Replace damaged membrane and flashing."),
    ("Janitorial Services, Border Station", "561720", "SBA", "El Paso", "TX", "79901", 22, 5,
     "Daily cleaning of offices and public areas at a border station. Work happens 7 days a week."),
    ("HVAC Repairs, Forest Service Office", "238220", "", "Madison", "WI", "53703", 29, 3,
     "Repair heating and cooling systems in a district office. Includes replacing two furnaces."),
    ("Lawn Mowing, Army Reserve Center", "561730", "SBA", "Davenport", "IA", "52801", 4, 0,
     "Mow and trim 8 acres every two weeks from April to October."),
]


class Command(BaseCommand):
    help = "Add DEMO contracts (made up) so the site works without the SAM.gov download."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Only remove the demo contracts")

    def handle(self, *args, **opts):
        Contract.objects.filter(is_demo=True).delete()
        if opts["clear"]:
            self.stdout.write(self.style.SUCCESS("Removed demo contracts."))
            return

        agencies = [Agency.objects.get_or_create(name=n, sub_tier=s, office=o)[0] for n, s, o in AGENCIES]
        now = timezone.now()
        for i, (title, naics, set_aside, city, state, zip_code, days, agency, text) in enumerate(CONTRACTS, start=1):
            notice_id = f"DEMO{i:04d}"
            point = geo.locate(zip_code, city, state)
            Contract(
                notice_id=notice_id,
                title=title,
                solicitation_number=f"DEMO-26-{i:04d}",
                agency=agencies[agency],
                notice_type="Solicitation" if i % 4 else "Combined Synopsis/Solicitation",
                naics_code=naics,
                set_aside=set_aside,
                posted_date=now - timedelta(days=3 + i % 9),
                due_date=(now + timedelta(days=days)).replace(hour=16, minute=0, second=0, microsecond=0),
                place_city=city.upper(),
                place_state=state,
                place_zip=zip_code,
                lat=point[0] if point else None,
                lon=point[1] if point else None,
                sam_url="",
                description_text=text,
                description_fetched=True,
                is_demo=True,
            ).tidy().save()
        self.stdout.write(self.style.SUCCESS(f"Added {len(CONTRACTS)} DEMO contracts."))
