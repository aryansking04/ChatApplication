import re
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup

# Regex patterns
URL_REGEX = re.compile(
    r'(https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*)',
    re.IGNORECASE
)

INSTAGRAM_REEL_PATTERN = re.compile(
    r'https?://(?:www\.)?instagram\.com/(?:reel|reels)/([A-Za-z0-9_-]+)',
    re.IGNORECASE
)
INSTAGRAM_POST_PATTERN = re.compile(
    r'https?://(?:www\.)?instagram\.com/p/([A-Za-z0-9_-]+)',
    re.IGNORECASE
)
INSTAGRAM_SHARE_PATTERN = re.compile(
    r'https?://(?:www\.)?instagram\.com/share/(?:reel/|p/)?([A-Za-z0-9_-]+)?',
    re.IGNORECASE
)

YOUTUBE_WATCH_PATTERN = re.compile(
    r'https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{11})',
    re.IGNORECASE
)
YOUTUBE_SHORT_PATTERN = re.compile(
    r'https?://(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})',
    re.IGNORECASE
)
YOUTUBE_SHARE_PATTERN = re.compile(
    r'https?://youtu\.be/([A-Za-z0-9_-]{11})',
    re.IGNORECASE
)


def extract_first_url(text: str) -> Optional[str]:
    """Find and return the first valid HTTP/HTTPS URL in the text."""
    if not text:
        return None
    match = URL_REGEX.search(text)
    if match:
        url = match.group(1).rstrip('.,!?;:)')
        return url
    return None


def is_safe_url(url: str) -> bool:
    """
    SSRF Protection: Ensure URL does not target loopback, private networks,
    link-local, cloud metadata services (169.254.169.254), or non-HTTP schemes.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Disallow localhost by name
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        # Resolve IP addresses
        addr_infos = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)

            # Block private, loopback, link-local, multicast, reserved
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or not ip.is_global
            ):
                return False

        return True
    except Exception:
        return False


def get_instagram_metadata(url: str) -> Optional[Dict[str, Any]]:
    """
    Extract Instagram Reel / Post information cleanly.
    Gracefully handles login walls by extracting shortcodes and public details.
    """
    parsed = urlparse(url)
    is_instagram = "instagram.com" in parsed.netloc.lower()
    if not is_instagram:
        return None

    # Check for Reel
    reel_match = INSTAGRAM_REEL_PATTERN.search(url)
    post_match = INSTAGRAM_POST_PATTERN.search(url)
    share_match = INSTAGRAM_SHARE_PATTERN.search(url)

    shortcode = None
    is_reel = "/reel" in url.lower() or bool(reel_match)

    if reel_match:
        shortcode = reel_match.group(1)
    elif post_match:
        shortcode = post_match.group(1)
    elif share_match and share_match.group(1):
        shortcode = share_match.group(1)

    title = "Instagram Reel" if is_reel else "Instagram Post"
    description = "View this Reel on Instagram" if is_reel else "View this Post on Instagram"

    # Default robust metadata
    data = {
        "platform": "instagram",
        "is_reel": is_reel,
        "media_id": shortcode,
        "title": title,
        "description": description,
        "image_url": None,
        "site_name": "Instagram",
        "original_url": url,
    }

    # Attempt to fetch public Open Graph / oEmbed metadata if permitted and safe
    if is_safe_url(url):
        try:
            # First try Instagram public oembed endpoint
            oembed_url = f"https://api.instagram.com/oembed/?url={url}"
            with httpx.Client(timeout=3.5, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                }
                resp = client.get(oembed_url, headers=headers)
                if resp.status_code == 200:
                    oembed_data = resp.json()
                    data["title"] = oembed_data.get("title") or title
                    data["image_url"] = oembed_data.get("thumbnail_url")
                    if oembed_data.get("author_name"):
                        data["description"] = f"Posted by @{oembed_data.get('author_name')} on Instagram"
                    return data
        except Exception:
            pass

        # Try fetching og tags directly
        try:
            with httpx.Client(timeout=3.5, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                    "Accept-Language": "en-US,en;q=0.9"
                }
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text[:250000], "html.parser")
                    og_title = soup.find("meta", property="og:title")
                    og_desc = soup.find("meta", property="og:description")
                    og_img = soup.find("meta", property="og:image")

                    if og_title and og_title.get("content"):
                        data["title"] = og_title["content"].strip()
                    if og_desc and og_desc.get("content"):
                        data["description"] = og_desc["content"].strip()
                    if og_img and og_img.get("content"):
                        data["image_url"] = og_img["content"].strip()
        except Exception:
            pass

    return data


def get_youtube_metadata(url: str) -> Optional[Dict[str, Any]]:
    """Extract YouTube video / shorts metadata and high quality thumbnail."""
    parsed = urlparse(url)
    is_yt = "youtube.com" in parsed.netloc.lower() or "youtu.be" in parsed.netloc.lower()
    if not is_yt:
        return None

    video_id = None
    is_short = "/shorts/" in url.lower()

    watch_match = YOUTUBE_WATCH_PATTERN.search(url)
    short_match = YOUTUBE_SHORT_PATTERN.search(url)
    share_match = YOUTUBE_SHARE_PATTERN.search(url)

    if watch_match:
        video_id = watch_match.group(1)
    elif short_match:
        video_id = short_match.group(1)
    elif share_match:
        video_id = share_match.group(1)

    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None
    title = "YouTube Short" if is_short else "YouTube Video"
    author = "YouTube"

    # Fetch YouTube official oEmbed (no API key needed, always safe and fast)
    if is_safe_url(url):
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(oembed_url)
                if resp.status_code == 200:
                    yt_data = resp.json()
                    title = yt_data.get("title", title)
                    author = yt_data.get("author_name", "YouTube")
                    if not thumbnail_url and yt_data.get("thumbnail_url"):
                        thumbnail_url = yt_data.get("thumbnail_url")
        except Exception:
            pass

    return {
        "platform": "youtube",
        "is_reel": is_short,
        "media_id": video_id,
        "title": title,
        "description": f"Uploaded by {author}" if author != "YouTube" else "Watch on YouTube",
        "image_url": thumbnail_url,
        "site_name": "YouTube",
        "original_url": url,
    }


def get_general_url_metadata(url: str) -> Dict[str, Any]:
    """Fetch Open Graph and meta tags for general URLs with SSRF protection."""
    parsed = urlparse(url)
    domain = parsed.netloc

    data = {
        "platform": "general",
        "is_reel": False,
        "media_id": None,
        "title": domain,
        "description": f"Visit {domain}",
        "image_url": None,
        "site_name": domain,
        "original_url": url,
    }

    if not is_safe_url(url):
        return data

    try:
        with httpx.Client(timeout=4.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text[:350000], "html.parser")

                # Title
                og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
                if og_title and og_title.get("content"):
                    data["title"] = og_title["content"].strip()
                elif soup.title and soup.title.string:
                    data["title"] = soup.title.string.strip()

                # Description
                og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"name": "twitter:description"})
                if og_desc and og_desc.get("content"):
                    data["description"] = og_desc["content"].strip()

                # Image
                og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                if og_image and og_image.get("content"):
                    img_url = og_image["content"].strip()
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    elif img_url.startswith("/") and parsed.scheme and parsed.netloc:
                        img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                    data["image_url"] = img_url

                # Site name
                og_site = soup.find("meta", property="og:site_name")
                if og_site and og_site.get("content"):
                    data["site_name"] = og_site["content"].strip()

    except Exception:
        pass

    return data


def extract_and_generate_preview(content: str) -> (str, Optional[Dict[str, Any]]):
    """
    Parses content for URLs, determines message type, and produces preview metadata.
    Returns tuple: (message_type, preview_dict)
    """
    url = extract_first_url(content)
    if not url:
        return "text", None

    # Check Instagram
    ig_meta = get_instagram_metadata(url)
    if ig_meta:
        msg_type = "instagram_reel" if ig_meta.get("is_reel") else "link"
        return msg_type, ig_meta

    # Check YouTube
    yt_meta = get_youtube_metadata(url)
    if yt_meta:
        return "youtube", yt_meta

    # General URL
    general_meta = get_general_url_metadata(url)
    return "link", general_meta
