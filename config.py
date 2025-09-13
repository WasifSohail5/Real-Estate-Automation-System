"""Configuration settings for the Real Estate Property System API."""

# Email configuration
EMAIL_CONFIG = {
    "EMAIL": "zuberipersonal@gmail.com",
    "PASSWORD": "lavfqbdauszbjuxp",
    "IMAP_SERVER": "imap.gmail.com",
    "IMAP_PORT": 993,
    "SMTP_SERVER": "smtp.gmail.com",
    "SMTP_PORT": 465
}

# Database configuration
DB_CONFIG = {
    "DB_PATH": r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db"
}

# Meeting configuration
OFFICE_LOCATIONS = [
    {
        "name": "Premier Properties Islamabad",
        "address": "Office #304, 3rd Floor, Emaar Business Complex, F-8 Markaz, Islamabad",
        "google_maps": "https://maps.app.goo.gl/V5wqJh7XkKZeBsry8",
        "phone": "+923197757134"
    },
    {
        "name": "Blue World Real Estate",
        "address": "Office #12, Ghauri Plaza, Jinnah Avenue, Blue Area, Islamabad",
        "google_maps": "https://maps.app.goo.gl/Z3HRs2kJpQEd5NSSA",
        "phone": "+923197757134"
    },
    {
        "name": "Capital Smart Properties",
        "address": "Suite #5, First Floor, Kohistan Plaza, F-10 Markaz, Islamabad",
        "google_maps": "https://maps.app.goo.gl/LnX8ArdK8sZAy3q78",
        "phone": "+923197757134"
    }
]

# Meeting time slots
MEETING_CONFIG = {
    "MEETING_HOURS": [f"{h}:00" for h in range(9, 18)],
    "MEETING_DAYS": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
}