"""
Cloudinary helpers — upload and delete images.

Falls back gracefully (returns None / skips) when CLOUDINARY_CLOUD_NAME
is not set, so local development works without any credentials.
"""
import os
import logging

logger = logging.getLogger(__name__)

_REQUIRED = ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")


def is_configured() -> bool:
    return all(os.environ.get(k) for k in _REQUIRED)


def _configure():
    import cloudinary
    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def upload_image(local_path: str, folder: str = "smartxray") -> str | None:
    """
    Upload a local image file to Cloudinary.
    Returns the HTTPS URL, or None if Cloudinary is not configured / upload fails.
    """
    if not is_configured():
        return None
    try:
        _configure()
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            local_path,
            folder=folder,
            resource_type="image",
            overwrite=True,
        )
        url = result.get("secure_url")
        logger.info("Cloudinary upload OK → %s", url)
        return url
    except Exception:
        logger.exception("Cloudinary upload failed for %s", local_path)
        return None


def upload_file(local_path: str, folder: str = "smartxray") -> str | None:
    """
    Upload any file (PDF, etc.) to Cloudinary using resource_type='raw'.
    Returns the HTTPS URL, or None if not configured / upload fails.
    """
    if not is_configured():
        return None
    try:
        _configure()
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            local_path,
            folder=folder,
            resource_type="raw",
            overwrite=True,
        )
        url = result.get("secure_url")
        logger.info("Cloudinary file upload OK → %s", url)
        return url
    except Exception:
        logger.exception("Cloudinary file upload failed for %s", local_path)
        return None


def delete_image(path_or_url: str) -> None:
    """
    Delete an image from Cloudinary given its secure_url or public_id.
    Silently skips if not configured or the path is a local relative path.
    """
    if not is_configured() or not path_or_url:
        return
    if not path_or_url.startswith("http"):
        return  # local path — nothing to clean up in Cloudinary
    try:
        _configure()
        import cloudinary.uploader
        # Extract public_id from the secure URL
        # URL: https://res.cloudinary.com/{cloud}/image/upload/v{ver}/{folder}/{name}.{ext}
        if "/upload/" not in path_or_url:
            return
        after_upload = path_or_url.split("/upload/", 1)[1]
        # Strip optional version segment (v1234567890/)
        if after_upload.startswith("v") and "/" in after_upload:
            after_upload = after_upload.split("/", 1)[1]
        public_id = after_upload.rsplit(".", 1)[0]  # remove extension
        cloudinary.uploader.destroy(public_id)
        logger.info("Cloudinary delete OK → %s", public_id)
    except Exception:
        logger.warning("Cloudinary delete failed for %s", path_or_url)
