"""Populate the site with demo members so the prototype can be shown live.

    python manage.py seed_demo

Every account uses the same password (`demo1234`) and is created already
verified. Photos are generated locally — soft gradient monograms — so no
stock imagery or real person's likeness is involved.

Safe to run more than once: existing demo accounts are left alone.
"""

import io
import random

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from profiles.models import Profile, ProfilePhoto

User = get_user_model()

DEMO_PASSWORD = "demo1234"

# (name, gender, year of birth, height cm, city, country, tongue, religion,
#  education, occupation, marital status, about)
DEMO_MEMBERS = [
    ("Priya Sharma", "F", 1996, 165, "Pune", "India", "Marathi", "Hindu",
     "B.E. Computer Science", "Software Engineer", "never",
     "I work in product engineering and spend most weekends hiking around the "
     "Sahyadris. My family is easy-going and close-knit. I am looking for someone "
     "kind, curious and honest — the rest we can figure out together."),
    ("Arjun Menon", "M", 1993, 178, "Bengaluru", "India", "Malayalam", "Hindu",
     "MBA, IIM Kozhikode", "Product Manager", "never",
     "Born in Kochi, based in Bengaluru for the last eight years. I cook far more "
     "than I eat out, follow far too much cricket, and value a partner who has her "
     "own ambitions."),
    ("Aisha Rahman", "F", 1995, 160, "Hyderabad", "India", "Urdu", "Muslim",
     "MBBS, Osmania Medical College", "Paediatrician", "never",
     "A paediatrician who genuinely likes her job. Family is important to me, and "
     "so is a quiet Sunday with a book. Looking for warmth, patience and a good "
     "sense of humour."),
    ("Rohan Desai", "M", 1991, 182, "Ahmedabad", "India", "Gujarati", "Hindu",
     "CA, ICAI", "Chartered Accountant", "never",
     "I run a small practice with my father. Weekends are for badminton and long "
     "drives. I would like to meet someone who is straightforward and does not take "
     "life too seriously."),
    ("Neha Kulkarni", "F", 1994, 168, "Mumbai", "India", "Marathi", "Hindu",
     "M.Des, NID Ahmedabad", "Design Lead", "never",
     "Designer by training, illustrator by habit. I moved to Mumbai for work and "
     "stayed for the sea. Looking for a partner who is thoughtful and equally "
     "happy at a gallery or a street-food stall."),
    ("Karan Singh", "M", 1990, 175, "Delhi", "India", "Punjabi", "Sikh",
     "B.Tech, DTU", "Data Scientist", "never",
     "I build forecasting models by day and play the guitar badly by night. Close "
     "to my parents and my two nieces. Hoping to meet someone grounded who enjoys "
     "travelling as much as I do."),
    ("Ananya Iyer", "F", 1997, 158, "Chennai", "India", "Tamil", "Hindu",
     "LL.B, NLS Bangalore", "Corporate Lawyer", "never",
     "Lawyer, Carnatic music student, and an enthusiastic if mediocre baker. I like "
     "people who are direct and can laugh at themselves."),
    ("Farhan Qureshi", "M", 1992, 180, "Lucknow", "India", "Urdu", "Muslim",
     "M.Arch, Jamia Millia", "Architect", "never",
     "Architect working mostly on restoration projects, which means I spend a lot "
     "of time in old buildings. Looking for a partner who is curious about the "
     "world and patient with my irregular hours."),
    ("Meera Nair", "F", 1993, 162, "Kochi", "India", "Malayalam", "Christian",
     "M.Sc Biotechnology", "Research Associate", "divorced",
     "Researcher, dog person, early riser. I have been through one marriage and "
     "come out of it with a clearer idea of what matters: honesty, kindness and "
     "space to be yourself."),
    ("Vikram Rao", "M", 1989, 177, "Vizag", "India", "Telugu", "Hindu",
     "B.Com", "Business Owner", "never",
     "I run a logistics business my grandfather started. Simple habits — morning "
     "swim, evening walk. Looking for someone I can build a calm, steady life with."),
    ("Sana Kapoor", "F", 1998, 170, "Chandigarh", "India", "Hindi", "Hindu",
     "B.A. Journalism", "Content Strategist", "never",
     "I write for a living and read for fun. Big on road trips, small on planning "
     "them. Would love to meet someone who is warm and genuinely good to people."),
    ("Imran Shaikh", "M", 1994, 173, "Nagpur", "India", "Hindi", "Muslim",
     "M.Tech, VNIT", "Civil Engineer", "never",
     "Site engineer on infrastructure projects, so I move around a fair bit. Family "
     "is in Nagpur. Looking for a partner who is independent and up for a bit of "
     "adventure."),
]

# Backdrop pairs for the generated monogram photos.
GRADIENTS = [
    ((123, 46, 70), (192, 151, 63)),
    ((60, 74, 110), (150, 172, 190)),
    ((92, 31, 51), (214, 170, 140)),
    ((44, 84, 74), (198, 190, 140)),
    ((104, 62, 96), (222, 176, 168)),
    ((30, 58, 78), (176, 148, 120)),
]


def make_monogram(initials: str, seed: int, size=(1000, 1250)) -> ContentFile:
    """Draw a soft diagonal-gradient portrait card carrying the initials."""
    rng = random.Random(seed)
    start, end = GRADIENTS[seed % len(GRADIENTS)]
    width, height = size

    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)

    # Diagonal gradient, painted one row at a time and skewed horizontally.
    for y in range(height):
        t = y / (height - 1)
        row = tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=row)

    # A few translucent circles give the flat gradient some depth.
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for _ in range(3):
        radius = rng.randint(width // 4, width // 2)
        cx = rng.randint(0, width)
        cy = rng.randint(0, height)
        odraw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                      fill=(255, 255, 255, 16))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(image)
    font = _load_font(round(width * 0.30))
    bbox = draw.textbbox((0, 0), initials, font=font)
    draw.text(
        ((width - (bbox[2] - bbox[0])) / 2 - bbox[0],
         (height - (bbox[3] - bbox[1])) / 2 - bbox[1] - height * 0.02),
        initials, font=font, fill=(255, 255, 255),
    )

    # Thin inset frame, echoing the site's card styling.
    inset = round(width * 0.045)
    draw.rectangle([inset, inset, width - inset, height - inset],
                   outline=(255, 255, 255), width=max(2, width // 300))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    return ContentFile(buffer.getvalue())


def _load_font(size: int):
    """Best available serif font, falling back to Pillow's built-in bitmap."""
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Command(BaseCommand):
    help = "Create demo members with generated photos."

    def add_arguments(self, parser):
        parser.add_argument("--photos", type=int, default=3,
                            help="Photos to generate per demo member (default 3).")

    @transaction.atomic
    def handle(self, *args, **options):
        photos_each = max(1, options["photos"])
        created = 0

        for index, row in enumerate(DEMO_MEMBERS):
            (name, gender, birth_year, height, city, country, tongue, religion,
             education, occupation, marital, about) = row

            email = f"{name.split()[0].lower()}.{name.split()[-1].lower()}@example.com"
            if User.objects.filter(email=email).exists():
                continue

            user = User.objects.create_user(email=email, password=DEMO_PASSWORD)
            user.mark_email_verified()

            profile = Profile.objects.create(
                user=user,
                full_name=name,
                # A fixed day/month keeps ages stable between runs.
                date_of_birth=f"{birth_year}-{(index % 12) + 1:02d}-{(index % 27) + 1:02d}",
                gender=gender,
                height_cm=height,
                marital_status=marital,
                religion=religion,
                mother_tongue=tongue,
                city=city,
                country=country,
                education=education,
                occupation=occupation,
                about=about,
            )

            initials = "".join(part[0] for part in name.split()[:2]).upper()
            for n in range(photos_each):
                photo = ProfilePhoto(profile=profile, sort_order=n, is_primary=(n == 0))
                photo.image.save(
                    f"demo-{index}-{n}.jpg",
                    make_monogram(initials, seed=index * 10 + n),
                    save=False,
                )
                photo.save()

            profile.sync_published_state()
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Created {created} demo member(s). "
            f"Sign in with any of them using the password '{DEMO_PASSWORD}'."
        ))
        if created == 0:
            self.stdout.write("All demo members already existed — nothing to do.")
