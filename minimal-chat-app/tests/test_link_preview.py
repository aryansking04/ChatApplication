from app.services.link_preview import (
    extract_first_url,
    is_safe_url,
    get_instagram_metadata,
    get_youtube_metadata,
    extract_and_generate_preview
)


def test_extract_first_url():
    assert extract_first_url("check this out: https://instagram.com/reel/12345/ super cool") == "https://instagram.com/reel/12345/"
    assert extract_first_url("no link here") is None
    assert extract_first_url("https://example.com/page?test=1&b=2") == "https://example.com/page?test=1&b=2"


def test_ssrf_protection():
    # Loopback & local addresses must be blocked
    assert is_safe_url("http://127.0.0.1/admin") is False
    assert is_safe_url("http://localhost:8000/secret") is False
    assert is_safe_url("http://0.0.0.0/") is False
    assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False  # Cloud metadata
    assert is_safe_url("file:///etc/passwd") is False  # Non-http scheme
    assert is_safe_url("gopher://evil.com") is False
    assert is_safe_url("http://192.168.1.1/") is False
    assert is_safe_url("http://10.0.0.1/") is False


def test_instagram_reel_parsing():
    url = "https://www.instagram.com/reel/Cx9_abcdef/"
    meta = get_instagram_metadata(url)
    assert meta is not None
    assert meta["platform"] == "instagram"
    assert meta["is_reel"] is True
    assert meta["media_id"] == "Cx9_abcdef"
    assert meta["site_name"] == "Instagram"


def test_instagram_post_parsing():
    url = "https://www.instagram.com/p/B9xYz123/"
    meta = get_instagram_metadata(url)
    assert meta is not None
    assert meta["platform"] == "instagram"
    assert meta["is_reel"] is False
    assert meta["media_id"] == "B9xYz123"


def test_youtube_video_parsing():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    meta = get_youtube_metadata(url)
    assert meta is not None
    assert meta["platform"] == "youtube"
    assert meta["media_id"] == "dQw4w9WgXcQ"
    assert "dQw4w9WgXcQ" in meta["image_url"]


def test_extract_and_generate_preview_pipeline():
    msg_type, preview = extract_and_generate_preview("Hey, look at this reel https://www.instagram.com/reel/C8_zY123/")
    assert msg_type == "instagram_reel"
    assert preview["media_id"] == "C8_zY123"
    assert preview["is_reel"] is True

    msg_type2, preview2 = extract_and_generate_preview("No links in this text message")
    assert msg_type2 == "text"
    assert preview2 is None
