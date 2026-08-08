"""Local fallback template catalogs for Drishti Engine stock-template search.

Mock catalog entries used when remote stock APIs are unavailable or fail.
"""

from __future__ import annotations

FALLBACK_IMAGES: list[dict] = [
    {
        "title": "Modern office desk with dual monitors",
        "url": "https://www.pexels.com/photo/modern-office-desk-with-dual-monitors-3184292/",
        "source": "local-catalog",
        "width": 1920,
        "height": 1280,
        "tags": ["office", "desk", "workspace", "monitor", "minimal"],
    },
    {
        "title": "Misty mountain landscape at sunrise",
        "url": "https://www.pexels.com/photo/misty-mountain-landscape-at-sunrise-417074/",
        "source": "local-catalog",
        "width": 1920,
        "height": 1080,
        "tags": ["mountain", "landscape", "nature", "outdoors", "sunrise"],
    },
    {
        "title": "City skyline at dusk with glowing lights",
        "url": "https://www.pexels.com/photo/city-skyline-at-dusk-with-glowing-lights-1684187/",
        "source": "local-catalog",
        "width": 2048,
        "height": 1365,
        "tags": ["city", "skyline", "urban", "architecture", "night"],
    },
    {
        "title": "Gourmet food photography on a rustic table",
        "url": "https://www.pexels.com/photo/gourmet-food-photography-on-rustic-table-1640777/",
        "source": "local-catalog",
        "width": 1920,
        "height": 1280,
        "tags": ["food", "photography", "cuisine", "dining", "recipe"],
    },
    {
        "title": "Abstract gradient background with soft waves",
        "url": "https://www.pexels.com/photo/abstract-gradient-background-with-soft-waves-1563355/",
        "source": "local-catalog",
        "width": 1600,
        "height": 1000,
        "tags": ["abstract", "gradient", "background", "design", "color"],
    },
    {
        "title": "Team meeting in a bright conference room",
        "url": "https://www.pexels.com/photo/team-meeting-in-a-bright-conference-room-3184291/",
        "source": "local-catalog",
        "width": 1920,
        "height": 1280,
        "tags": ["team", "meeting", "business", "collaboration", "office"],
    },
    {
        "title": "Beach sunset with palm tree silhouettes",
        "url": "https://www.pexels.com/photo/beach-sunset-with-palm-tree-silhouettes-1228291/",
        "source": "local-catalog",
        "width": 2048,
        "height": 1365,
        "tags": ["beach", "sunset", "travel", "ocean", "vacation"],
    },
    {
        "title": "Laptop workspace with notebook and plant",
        "url": "https://www.pexels.com/photo/laptop-workspace-with-notebook-and-plant-196645/",
        "source": "local-catalog",
        "width": 1920,
        "height": 1280,
        "tags": ["laptop", "workspace", "productivity", "remote", "desk"],
    },
]

FALLBACK_VIDEOS: list[dict] = [
    {
        "title": "Aerial drone shot over a coastline",
        "url": "https://www.pexels.com/video/aerial-drone-shot-over-a-coastline-857195/",
        "source": "local-catalog",
        "duration_seconds": 30,
        "tags": ["aerial", "drone", "coastline", "nature", "travel"],
    },
    {
        "title": "Product commercial of headphones rotating",
        "url": "https://www.pexels.com/video/product-commercial-of-headphones-rotating-5196999/",
        "source": "local-catalog",
        "duration_seconds": 20,
        "tags": ["product", "commercial", "marketing", "technology"],
    },
    {
        "title": "Corporate interview with business executives",
        "url": "https://www.pexels.com/video/corporate-interview-with-business-executives-3184401/",
        "source": "local-catalog",
        "duration_seconds": 45,
        "tags": ["corporate", "interview", "business", "office"],
    },
    {
        "title": "Nature b-roll of a forest stream close-up",
        "url": "https://www.pexels.com/video/nature-b-roll-of-a-forest-stream-close-up-1638510/",
        "source": "local-catalog",
        "duration_seconds": 25,
        "tags": ["nature", "b-roll", "forest", "water", "outdoors"],
    },
    {
        "title": "Cooking tutorial slicing fresh vegetables",
        "url": "https://www.pexels.com/video/cooking-tutorial-slicing-fresh-vegetables-5858203/",
        "source": "local-catalog",
        "duration_seconds": 60,
        "tags": ["cooking", "tutorial", "kitchen", "food", "how-to"],
    },
    {
        "title": "Tech review unboxing a new smartphone",
        "url": "https://www.pexels.com/video/tech-review-unboxing-a-new-smartphone-3981110/",
        "source": "local-catalog",
        "duration_seconds": 50,
        "tags": ["tech", "review", "smartphone", "unboxing", "gadget"],
    },
]
