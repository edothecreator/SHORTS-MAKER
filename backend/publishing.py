"""
Multi-Platform Publishing System (Production Task 15)

Provides OAuth connections, one-click publishing, scheduling, cross-posting,
and status tracking for TikTok, YouTube, Instagram, and LinkedIn.

All publisher implementations are placeholder/TODO since real OAuth requires
registered apps with platform developer accounts. The code structure is complete
and type-safe, documenting all required API endpoints and scopes.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Task 15.10: PostStatus Enum
# =============================================================================

class PostStatus(str, enum.Enum):
    """Status of a published post across platforms."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    FAILED = "failed"
    DELETED = "deleted"


# =============================================================================
# Pydantic Models for Request/Response Schemas
# =============================================================================

class OAuthCredentials(BaseModel):
    """OAuth credentials returned after successful authentication."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)
    platform: str
    user_id: Optional[str] = None
    username: Optional[str] = None



class PublishRequest(BaseModel):
    """Request schema for publishing a video to a platform."""
    video_path: str
    title: str
    description: str
    hashtags: List[str] = Field(default_factory=list)
    thumbnail_path: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    platform_specific: Dict[str, Any] = Field(default_factory=dict)


class PublishResponse(BaseModel):
    """Response schema after publishing or scheduling a post."""
    post_id: str
    platform: str
    status: PostStatus
    published_url: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlatformConfig(BaseModel):
    """Configuration for a social media platform's API."""
    name: str
    oauth_authorize_url: str
    oauth_token_url: str
    api_base_url: str
    scopes: List[str]
    max_video_duration_seconds: int
    max_file_size_mb: int
    supported_formats: List[str] = Field(default_factory=lambda: ["mp4"])
    max_title_length: int = 100
    max_description_length: int = 2200
    max_hashtags: int = 30


class ClipMetadata(BaseModel):
    """Metadata about a clip to be published."""
    video_path: str
    title: str
    description: str
    hashtags: List[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    resolution: str = "1080x1920"
    thumbnail_path: Optional[str] = None



class FormattedContent(BaseModel):
    """Platform-specific formatted content for a clip."""
    platform: str
    title: str
    description: str
    hashtags: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    caption: Optional[str] = None


class ScheduleRequest(BaseModel):
    """Request schema for scheduling a post."""
    clip: ClipMetadata
    platform: str
    credentials: OAuthCredentials
    scheduled_time: datetime


class CrossPostResult(BaseModel):
    """Result of cross-posting to multiple platforms."""
    results: Dict[str, PublishResponse] = Field(default_factory=dict)
    successful: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)


# =============================================================================
# Platform Configurations
# =============================================================================

PLATFORM_CONFIGS: Dict[str, PlatformConfig] = {
    "tiktok": PlatformConfig(
        name="TikTok",
        oauth_authorize_url="https://www.tiktok.com/v2/auth/authorize/",
        oauth_token_url="https://open.tiktokapis.com/v2/oauth/token/",
        api_base_url="https://open.tiktokapis.com/v2",
        scopes=[
            "user.info.basic",
            "video.publish",
            "video.upload",
            "video.list",
        ],
        max_video_duration_seconds=600,
        max_file_size_mb=287,
        supported_formats=["mp4", "webm"],
        max_title_length=150,
        max_description_length=2200,
        max_hashtags=30,
    ),
    "youtube": PlatformConfig(
        name="YouTube",
        oauth_authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        oauth_token_url="https://oauth2.googleapis.com/token",
        api_base_url="https://www.googleapis.com/youtube/v3",
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.readonly",
        ],
        max_video_duration_seconds=60,
        max_file_size_mb=256000,
        supported_formats=["mp4", "mov", "avi", "wmv", "flv", "webm"],
        max_title_length=100,
        max_description_length=5000,
        max_hashtags=15,
    ),

    "instagram": PlatformConfig(
        name="Instagram",
        oauth_authorize_url="https://api.instagram.com/oauth/authorize",
        oauth_token_url="https://api.instagram.com/oauth/access_token",
        api_base_url="https://graph.instagram.com/v18.0",
        scopes=[
            "instagram_basic",
            "instagram_content_publish",
            "pages_show_list",
            "pages_read_engagement",
        ],
        max_video_duration_seconds=90,
        max_file_size_mb=1000,
        supported_formats=["mp4", "mov"],
        max_title_length=0,  # Instagram doesn't use titles
        max_description_length=2200,
        max_hashtags=30,
    ),
    "linkedin": PlatformConfig(
        name="LinkedIn",
        oauth_authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        oauth_token_url="https://www.linkedin.com/oauth/v2/accessToken",
        api_base_url="https://api.linkedin.com/v2",
        scopes=[
            "w_member_social",
            "r_liteprofile",
            "r_organization_social",
        ],
        max_video_duration_seconds=600,
        max_file_size_mb=5120,
        supported_formats=["mp4"],
        max_title_length=150,
        max_description_length=3000,
        max_hashtags=5,
    ),
}



# =============================================================================
# Task 15.7: Optimal Post Times (based on platform best practices)
# =============================================================================

# Best posting hours per platform per day of week (24h format, UTC)
# Based on aggregated social media marketing research
OPTIMAL_POST_TIMES: Dict[str, Dict[str, List[int]]] = {
    "tiktok": {
        "monday": [7, 10, 22],
        "tuesday": [9, 12, 17],
        "wednesday": [7, 11, 22],
        "thursday": [9, 12, 19],
        "friday": [5, 13, 15],
        "saturday": [11, 19, 21],
        "sunday": [7, 8, 16],
    },
    "youtube": {
        "monday": [14, 16, 20],
        "tuesday": [14, 16, 20],
        "wednesday": [14, 16, 20],
        "thursday": [12, 15, 20],
        "friday": [12, 15, 17],
        "saturday": [9, 11, 16],
        "sunday": [9, 11, 16],
    },
    "instagram": {
        "monday": [6, 10, 14],
        "tuesday": [6, 9, 14],
        "wednesday": [7, 11, 14],
        "thursday": [7, 11, 15],
        "friday": [7, 11, 14],
        "saturday": [9, 11, 13],
        "sunday": [7, 9, 16],
    },
    "linkedin": {
        "monday": [8, 10, 12],
        "tuesday": [8, 10, 12],
        "wednesday": [8, 10, 12],
        "thursday": [8, 10, 14],
        "friday": [8, 10, 12],
        "saturday": [10, 12, 14],
        "sunday": [10, 12, 14],
    },
}



# =============================================================================
# Abstract Base Publisher
# =============================================================================

class BasePublisher(ABC):
    """Abstract base class for all platform publishers."""

    platform: str
    config: PlatformConfig
    credentials: Optional[OAuthCredentials]

    def __init__(self) -> None:
        self.credentials = None

    @abstractmethod
    def connect(self, auth_code: str) -> OAuthCredentials:
        """
        Exchange an OAuth authorization code for access credentials.

        Args:
            auth_code: The authorization code received from OAuth redirect.

        Returns:
            OAuthCredentials with access_token and refresh_token.
        """
        ...

    @abstractmethod
    def publish(
        self,
        video_path: str,
        title: str,
        description: str,
        **kwargs: Any,
    ) -> str:
        """
        Upload and publish a video to the platform.

        Args:
            video_path: Local path to the video file.
            title: Title for the post.
            description: Description/caption for the post.
            **kwargs: Platform-specific parameters.

        Returns:
            post_id: The platform's unique identifier for the published post.
        """
        ...

    @abstractmethod
    def get_status(self, post_id: str) -> PostStatus:
        """
        Get the current status of a published post.

        Args:
            post_id: The platform's unique identifier for the post.

        Returns:
            PostStatus enum value.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Revoke OAuth tokens and disconnect the account."""
        ...

    def _validate_video(self, video_path: str) -> bool:
        """Validate video meets platform requirements."""
        # TODO: Check file size, duration, format against self.config
        return True



# =============================================================================
# Task 15.1: TikTok Publisher
# =============================================================================

class TikTokPublisher(BasePublisher):
    """
    TikTok video publisher using the TikTok Content Posting API.

    API Documentation: https://developers.tiktok.com/doc/content-posting-api-get-started
    Required App: Register at https://developers.tiktok.com/

    OAuth Flow:
        1. Redirect user to oauth_authorize_url with client_key and scopes
        2. User authorizes → TikTok redirects back with auth_code
        3. Exchange auth_code for access_token via oauth_token_url
        4. Use access_token for all API calls

    Endpoints Used:
        - POST /v2/post/publish/inbox/video/init (initialize upload)
        - POST /v2/post/publish/video/init (direct publish)
        - GET /v2/post/publish/status/fetch (check publish status)
        - POST /v2/oauth/revoke/ (disconnect)
    """

    platform = "tiktok"
    config = PLATFORM_CONFIGS["tiktok"]

    def connect(self, auth_code: str) -> OAuthCredentials:
        """
        Exchange TikTok auth code for access token.

        API Endpoint: POST https://open.tiktokapis.com/v2/oauth/token/
        Required params: client_key, client_secret, code, grant_type, redirect_uri
        """
        # TODO: Implement actual OAuth token exchange
        # Required: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET env vars
        # Response includes: access_token, refresh_token, open_id, scope, expires_in
        raise NotImplementedError(
            "TikTok OAuth requires a registered app at https://developers.tiktok.com/. "
            "Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET environment variables."
        )


    def publish(
        self,
        video_path: str,
        title: str,
        description: str,
        **kwargs: Any,
    ) -> str:
        """
        Publish a video to TikTok.

        API Flow:
            1. POST /v2/post/publish/inbox/video/init
               - Initialize upload, get upload_url
            2. PUT upload_url with video binary
            3. POST /v2/post/publish/video/init
               - Set title, description, privacy_level, disable_duet, etc.

        Args:
            video_path: Path to video file (mp4, max 287MB, max 10min)
            title: Video title (max 150 chars)
            description: Video description with hashtags
            **kwargs:
                privacy_level: "PUBLIC_TO_EVERYONE" | "MUTUAL_FOLLOW_FRIENDS" | "SELF_ONLY"
                disable_duet: bool
                disable_stitch: bool
                disable_comment: bool
                video_cover_timestamp_ms: int

        Returns:
            publish_id from TikTok's response
        """
        # TODO: Implement video upload and publish
        # Step 1: Initialize upload session
        # Step 2: Upload video chunks
        # Step 3: Publish with metadata
        raise NotImplementedError("TikTok publish requires registered app credentials.")

    def get_status(self, post_id: str) -> PostStatus:
        """
        Check TikTok publish status.

        API Endpoint: POST /v2/post/publish/status/fetch
        Body: {"publish_id": post_id}
        Response status values:
            - PUBLISH_COMPLETE → PostStatus.PUBLISHED
            - PROCESSING_UPLOAD / PROCESSING_DOWNLOAD → PostStatus.PROCESSING
            - FAILED → PostStatus.FAILED
        """
        # TODO: Implement status check
        raise NotImplementedError("TikTok status check requires registered app credentials.")

    def disconnect(self) -> None:
        """
        Revoke TikTok OAuth tokens.

        API Endpoint: POST https://open.tiktokapis.com/v2/oauth/revoke/
        Body: {"client_key": ..., "token": access_token}
        """
        # TODO: Revoke token
        self.credentials = None



# =============================================================================
# Task 15.2: YouTube Publisher
# =============================================================================

class YouTubePublisher(BasePublisher):
    """
    YouTube Shorts publisher using the YouTube Data API v3.

    API Documentation: https://developers.google.com/youtube/v3/docs/videos/insert
    Required App: Register at https://console.cloud.google.com/

    OAuth Flow:
        1. Redirect user to accounts.google.com/o/oauth2/v2/auth
        2. User authorizes → Google redirects with auth_code
        3. Exchange auth_code for access_token via oauth2.googleapis.com/token
        4. Use access_token in Authorization header for all API calls

    Endpoints Used:
        - POST /youtube/v3/videos?part=snippet,status (upload + metadata)
        - GET /youtube/v3/videos?part=status&id={id} (check status)
        - POST /youtube/v3/videos?part=id (delete)
        - POST https://oauth2.googleapis.com/revoke (disconnect)

    YouTube Shorts Requirements:
        - Vertical video (9:16 aspect ratio)
        - Max 60 seconds duration
        - Add #Shorts in title or description for Shorts shelf
    """

    platform = "youtube"
    config = PLATFORM_CONFIGS["youtube"]

    def connect(self, auth_code: str) -> OAuthCredentials:
        """
        Exchange Google OAuth auth code for access token.

        API Endpoint: POST https://oauth2.googleapis.com/token
        Required params: client_id, client_secret, code, grant_type, redirect_uri
        """
        # TODO: Implement actual OAuth token exchange
        # Required: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET env vars
        # Response includes: access_token, refresh_token, expires_in, token_type, scope
        raise NotImplementedError(
            "YouTube OAuth requires a Google Cloud project with YouTube Data API enabled. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
        )


    def publish(
        self,
        video_path: str,
        title: str,
        description: str,
        **kwargs: Any,
    ) -> str:
        """
        Upload a video as a YouTube Short.

        API Endpoint: POST https://www.googleapis.com/upload/youtube/v3/videos
        Query params: part=snippet,status,contentDetails
        Headers: Authorization: Bearer {access_token}

        The video is uploaded via resumable upload protocol:
            1. POST to initiate (get upload URI)
            2. PUT video bytes to upload URI

        Args:
            video_path: Path to video file (must be <=60s for Shorts)
            title: Video title (max 100 chars, #Shorts appended automatically)
            description: Video description
            **kwargs:
                tags: List[str] — video tags for discoverability
                category_id: str — YouTube category (default "22" = People & Blogs)
                privacy_status: "public" | "private" | "unlisted"
                made_for_kids: bool (COPPA compliance)
                scheduled_start_time: str (ISO 8601, for scheduled publish)

        Returns:
            video_id from YouTube's response
        """
        # TODO: Implement resumable upload
        # Step 1: POST to get resumable upload URI
        # Step 2: PUT video binary to upload URI
        # Step 3: Parse response for video ID
        # Note: Append "#Shorts" to title if not present for Shorts shelf
        raise NotImplementedError("YouTube publish requires Google Cloud credentials.")

    def get_status(self, post_id: str) -> PostStatus:
        """
        Check YouTube video processing/publish status.

        API Endpoint: GET /youtube/v3/videos?part=status&id={post_id}
        Response uploadStatus values:
            - "uploaded" → PostStatus.PROCESSING
            - "processed" → PostStatus.PUBLISHED
            - "failed" → PostStatus.FAILED
            - "rejected" → PostStatus.FAILED
            - "deleted" → PostStatus.DELETED
        """
        # TODO: Implement status check
        raise NotImplementedError("YouTube status check requires Google Cloud credentials.")

    def disconnect(self) -> None:
        """
        Revoke Google OAuth token.

        API Endpoint: POST https://oauth2.googleapis.com/revoke
        Params: token={access_token}
        """
        # TODO: Revoke token
        self.credentials = None



# =============================================================================
# Task 15.3: Instagram Publisher
# =============================================================================

class InstagramPublisher(BasePublisher):
    """
    Instagram Reels publisher using the Meta Graph API (Instagram Content Publishing).

    API Documentation: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
    Required App: Register at https://developers.facebook.com/

    OAuth Flow (Meta Business):
        1. Redirect to facebook.com/v18.0/dialog/oauth (not instagram directly)
        2. User authorizes → Meta redirects with auth_code
        3. Exchange code for short-lived token, then exchange for long-lived token
        4. Get Instagram Business Account ID via /me/accounts endpoint

    Endpoints Used:
        - POST /{ig-user-id}/media (create media container for Reel)
        - POST /{ig-user-id}/media_publish (publish the container)
        - GET /{ig-container-id}?fields=status_code (check status)

    Instagram Reels Requirements:
        - 9:16 aspect ratio
        - 3-90 seconds duration
        - MP4 or MOV format
        - Max 1GB file size
    """

    platform = "instagram"
    config = PLATFORM_CONFIGS["instagram"]

    def connect(self, auth_code: str) -> OAuthCredentials:
        """
        Exchange Meta OAuth auth code for Instagram access token.

        Flow:
            1. POST https://api.instagram.com/oauth/access_token
               → short-lived token (1 hour)
            2. GET /oauth/access_token?grant_type=ig_exchange_token
               → long-lived token (60 days)
            3. GET /me/accounts → get Instagram Business Account ID

        Required: META_APP_ID, META_APP_SECRET env vars
        """
        # TODO: Implement Meta OAuth token exchange
        # Note: Requires Facebook Page connected to Instagram Business Account
        raise NotImplementedError(
            "Instagram publishing requires a Meta Business App and connected "
            "Instagram Business Account. Set META_APP_ID and META_APP_SECRET."
        )


    def publish(
        self,
        video_path: str,
        title: str,
        description: str,
        **kwargs: Any,
    ) -> str:
        """
        Publish a video as an Instagram Reel.

        API Flow (two-step publish):
            1. POST /{ig-user-id}/media
               Body: {
                   "media_type": "REELS",
                   "video_url": "<publicly accessible URL>",
                   "caption": "<caption with hashtags>",
                   "share_to_feed": true,
                   "cover_url": "<optional thumbnail URL>"
               }
               → Returns container_id
            2. Wait for container to finish processing (poll status)
            3. POST /{ig-user-id}/media_publish
               Body: {"creation_id": container_id}
               → Returns media_id (the post_id)

        Args:
            video_path: Path to video (must be hosted at public URL for API)
            title: Not used for Instagram (included in caption)
            description: Caption text (max 2200 chars)
            **kwargs:
                hashtags: List[str] — appended to caption
                share_to_feed: bool — also show in main feed (default True)
                cover_url: str — custom thumbnail URL
                location_id: str — tag a location

        Returns:
            media_id from Instagram's response
        """
        # TODO: Implement Reels publishing
        # Note: Video must be hosted at a publicly accessible URL
        # The video_path would need to be uploaded to storage first and a public URL generated
        raise NotImplementedError("Instagram publish requires Meta Business App credentials.")

    def get_status(self, post_id: str) -> PostStatus:
        """
        Check Instagram media container status.

        API Endpoint: GET /{container-id}?fields=status_code
        Response status_code values:
            - "EXPIRED" → PostStatus.FAILED
            - "ERROR" → PostStatus.FAILED
            - "FINISHED" → PostStatus.PUBLISHED
            - "IN_PROGRESS" → PostStatus.PROCESSING
            - "PUBLISHED" → PostStatus.PUBLISHED
        """
        # TODO: Implement status check
        raise NotImplementedError("Instagram status check requires Meta Business credentials.")

    def disconnect(self) -> None:
        """
        Revoke Meta/Instagram permissions.

        API Endpoint: DELETE /{user-id}/permissions
        This removes all granted permissions for the app.
        """
        # TODO: Revoke permissions
        self.credentials = None



# =============================================================================
# Task 15.4: LinkedIn Publisher
# =============================================================================

class LinkedInPublisher(BasePublisher):
    """
    LinkedIn video post publisher using the LinkedIn Marketing API.

    API Documentation: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/videos-api
    Required App: Register at https://www.linkedin.com/developers/

    OAuth Flow:
        1. Redirect to linkedin.com/oauth/v2/authorization
        2. User authorizes → LinkedIn redirects with auth_code
        3. Exchange auth_code for access_token via /oauth/v2/accessToken
        4. Get user URN via /v2/userinfo

    Endpoints Used:
        - POST /v2/assets?action=registerUpload (register video upload)
        - PUT {upload_url} (upload video binary)
        - POST /v2/assets?action=completeMultiPartUpload (finalize)
        - POST /v2/ugcPosts (create post with video)
        - GET /v2/ugcPosts/{id} (check post status)
    """

    platform = "linkedin"
    config = PLATFORM_CONFIGS["linkedin"]

    def connect(self, auth_code: str) -> OAuthCredentials:
        """
        Exchange LinkedIn OAuth auth code for access token.

        API Endpoint: POST https://www.linkedin.com/oauth/v2/accessToken
        Required params: grant_type, code, client_id, client_secret, redirect_uri
        """
        # TODO: Implement LinkedIn OAuth token exchange
        # Required: LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET env vars
        # Response includes: access_token, expires_in (60 days)
        # Note: LinkedIn tokens do NOT include refresh_token by default
        raise NotImplementedError(
            "LinkedIn OAuth requires a LinkedIn Developer App. "
            "Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET environment variables."
        )


    def publish(
        self,
        video_path: str,
        title: str,
        description: str,
        **kwargs: Any,
    ) -> str:
        """
        Upload and publish a video post on LinkedIn.

        API Flow:
            1. POST /v2/assets?action=registerUpload
               → Get uploadMechanism.com.linkedin.digitalmedia.uploading
                   .MediaUploadHttpRequest.uploadUrl
            2. PUT video binary to upload_url
            3. POST /v2/ugcPosts
               Body: {
                   "author": "urn:li:person:{person_id}",
                   "lifecycleState": "PUBLISHED",
                   "specificContent": {
                       "com.linkedin.ugc.ShareContent": {
                           "shareCommentary": {"text": description},
                           "shareMediaCategory": "VIDEO",
                           "media": [{
                               "status": "READY",
                               "media": "urn:li:digitalmediaAsset:{asset_id}",
                               "title": {"text": title}
                           }]
                       }
                   },
                   "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
               }

        Args:
            video_path: Path to video file (mp4, max 5GB, max 10min)
            title: Post title (professional tone recommended)
            description: Post text/commentary (max 3000 chars)
            **kwargs:
                visibility: "PUBLIC" | "CONNECTIONS" (default "PUBLIC")
                person_urn: str — LinkedIn person URN (from /v2/userinfo)

        Returns:
            ugcPost ID from LinkedIn's response
        """
        # TODO: Implement video upload and post creation
        # Step 1: Register upload to get upload URL and asset URN
        # Step 2: Upload video binary via PUT
        # Step 3: Create UGC post with video asset
        raise NotImplementedError("LinkedIn publish requires Developer App credentials.")

    def get_status(self, post_id: str) -> PostStatus:
        """
        Check LinkedIn post status.

        API Endpoint: GET /v2/ugcPosts/{post_id}
        Response lifecycleState values:
            - "PUBLISHED" → PostStatus.PUBLISHED
            - "PROCESSING" → PostStatus.PROCESSING
            - "DRAFT" → PostStatus.PENDING
        Also check video asset status:
            GET /v2/assets/{asset_id}
            - "PROCESSING" → PostStatus.PROCESSING
            - "AVAILABLE" → PostStatus.PUBLISHED
            - "FAILED" → PostStatus.FAILED
        """
        # TODO: Implement status check
        raise NotImplementedError("LinkedIn status check requires Developer App credentials.")

    def disconnect(self) -> None:
        """
        LinkedIn does not support programmatic token revocation.
        Users must manually revoke app access in LinkedIn settings.
        We clear local credentials.
        """
        # Note: LinkedIn OAuth2 tokens cannot be revoked via API
        # User must go to linkedin.com/psettings/permitted-services to revoke
        self.credentials = None



# =============================================================================
# Publisher Registry
# =============================================================================

_PUBLISHERS: Dict[str, type[BasePublisher]] = {
    "tiktok": TikTokPublisher,
    "youtube": YouTubePublisher,
    "instagram": InstagramPublisher,
    "linkedin": LinkedInPublisher,
}


def _get_publisher(platform: str) -> BasePublisher:
    """Get an instance of the publisher for the given platform."""
    platform = platform.lower()
    if platform not in _PUBLISHERS:
        raise ValueError(
            f"Unsupported platform: '{platform}'. "
            f"Supported platforms: {list(_PUBLISHERS.keys())}"
        )
    return _PUBLISHERS[platform]()


# =============================================================================
# Task 15.5: One-Click Publish Dispatcher
# =============================================================================

def publish_to_platform(
    clip: ClipMetadata,
    platform: str,
    credentials: OAuthCredentials,
) -> PublishResponse:
    """
    One-click publish dispatcher — publishes a clip to a single platform.

    This function handles:
        1. Getting the correct publisher for the platform
        2. Formatting content for platform requirements
        3. Validating the video meets platform specs
        4. Publishing and returning the result

    Args:
        clip: ClipMetadata with video path, title, description, hashtags.
        platform: Target platform ("tiktok", "youtube", "instagram", "linkedin").
        credentials: OAuthCredentials for the target platform.

    Returns:
        PublishResponse with post_id and status.

    Raises:
        ValueError: If platform is not supported.
        NotImplementedError: If publisher is not yet implemented (placeholder).
    """
    publisher = _get_publisher(platform)
    publisher.credentials = credentials

    # Format content for the specific platform
    formatted = format_for_platform(clip, platform)

    try:
        post_id = publisher.publish(
            video_path=clip.video_path,
            title=formatted.title,
            description=formatted.description,
            hashtags=formatted.hashtags,
            tags=formatted.tags,
        )
        return PublishResponse(
            post_id=post_id,
            platform=platform,
            status=PostStatus.PROCESSING,
        )
    except NotImplementedError as e:
        return PublishResponse(
            post_id="",
            platform=platform,
            status=PostStatus.FAILED,
            error_message=str(e),
        )
    except Exception as e:
        return PublishResponse(
            post_id="",
            platform=platform,
            status=PostStatus.FAILED,
            error_message=f"Publishing failed: {str(e)}",
        )



# =============================================================================
# Task 15.6: Schedule Posts
# =============================================================================

def schedule_post(
    clip: ClipMetadata,
    platform: str,
    credentials: OAuthCredentials,
    scheduled_time: datetime,
) -> PublishResponse:
    """
    Schedule a post for future publication on a platform.

    Validates that scheduled_time is in the future and handles platform-specific
    scheduling capabilities:
        - YouTube: Supports native scheduling via publishAt parameter
        - TikTok: Supports schedule_time parameter in publish API
        - Instagram: Requires server-side scheduler (no native scheduling API)
        - LinkedIn: Requires server-side scheduler (no native scheduling API)

    For platforms without native scheduling, this stores the job in a queue
    to be executed at the scheduled time by a background worker.

    Args:
        clip: ClipMetadata with video path and content.
        platform: Target platform name.
        credentials: OAuthCredentials for the platform.
        scheduled_time: Future datetime (must be timezone-aware, UTC preferred).

    Returns:
        PublishResponse with SCHEDULED status and scheduled_time.

    Raises:
        ValueError: If scheduled_time is in the past or platform is unsupported.
    """
    now = datetime.now(timezone.utc)

    # Ensure scheduled_time is timezone-aware
    if scheduled_time.tzinfo is None:
        scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)

    if scheduled_time <= now:
        raise ValueError(
            f"scheduled_time must be in the future. Got {scheduled_time.isoformat()}, "
            f"current time is {now.isoformat()}"
        )

    # Validate platform
    if platform.lower() not in _PUBLISHERS:
        raise ValueError(f"Unsupported platform: '{platform}'")

    # TODO: Implement actual scheduling logic
    # For YouTube: Use publishAt in video.status
    # For TikTok: Use schedule_time in publish request
    # For Instagram/LinkedIn: Store in job queue for background worker execution

    return PublishResponse(
        post_id=f"scheduled_{platform}_{int(scheduled_time.timestamp())}",
        platform=platform,
        status=PostStatus.SCHEDULED,
        scheduled_time=scheduled_time,
    )



# =============================================================================
# Task 15.7: Optimal Post Time Suggestions
# =============================================================================

def get_optimal_post_time(
    platform: str,
    timezone_name: str = "UTC",
) -> Dict[str, Any]:
    """
    Returns the suggested best time to post based on platform best practices.

    Uses aggregated social media research data to suggest optimal posting times.
    Times are adjusted from UTC to the user's specified timezone.

    Args:
        platform: Target platform ("tiktok", "youtube", "instagram", "linkedin").
        timezone_name: IANA timezone name (e.g., "America/New_York", "Europe/London").
                      Defaults to "UTC".

    Returns:
        Dictionary with:
            - platform: str
            - today_best_hours: List[int] — best hours to post today (in user's TZ)
            - next_optimal_time: datetime — next upcoming optimal posting time
            - weekly_schedule: Dict[str, List[int]] — best hours for each day
            - timezone: str — the timezone used

    Raises:
        ValueError: If platform is not supported.
    """
    platform = platform.lower()
    if platform not in OPTIMAL_POST_TIMES:
        raise ValueError(
            f"Unsupported platform: '{platform}'. "
            f"Supported: {list(OPTIMAL_POST_TIMES.keys())}"
        )

    platform_times = OPTIMAL_POST_TIMES[platform]
    now = datetime.now(timezone.utc)
    today_name = now.strftime("%A").lower()
    today_hours = platform_times.get(today_name, [12])

    # Find the next optimal time (today or tomorrow)
    next_time: Optional[datetime] = None
    current_hour = now.hour

    for hour in sorted(today_hours):
        if hour > current_hour:
            next_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            break

    if next_time is None:
        # All today's times have passed, get first time tomorrow
        from datetime import timedelta
        tomorrow = now + timedelta(days=1)
        tomorrow_name = tomorrow.strftime("%A").lower()
        tomorrow_hours = platform_times.get(tomorrow_name, [12])
        first_hour = sorted(tomorrow_hours)[0]
        next_time = tomorrow.replace(hour=first_hour, minute=0, second=0, microsecond=0)

    return {
        "platform": platform,
        "today_best_hours": today_hours,
        "next_optimal_time": next_time.isoformat(),
        "weekly_schedule": platform_times,
        "timezone": timezone_name,
        "note": (
            "Times shown in UTC. Adjust to your local timezone. "
            "Based on aggregated social media engagement research."
        ),
    }



# =============================================================================
# Task 15.8: Cross-Post to All Platforms
# =============================================================================

def cross_post_all(
    clip: ClipMetadata,
    platforms: List[str],
    credentials: Dict[str, OAuthCredentials],
) -> CrossPostResult:
    """
    Publish to all connected platforms simultaneously.

    Attempts to publish the clip to each specified platform. Continues even
    if one platform fails (partial success is possible).

    Args:
        clip: ClipMetadata with video path and content.
        platforms: List of platform names to publish to.
        credentials: Dict mapping platform name → OAuthCredentials.

    Returns:
        CrossPostResult with per-platform results and success/failure lists.

    Example:
        result = cross_post_all(
            clip=my_clip,
            platforms=["tiktok", "youtube", "instagram"],
            credentials={
                "tiktok": tiktok_creds,
                "youtube": youtube_creds,
                "instagram": instagram_creds,
            }
        )
        print(f"Succeeded: {result.successful}")
        print(f"Failed: {result.failed}")
    """
    result = CrossPostResult()

    for platform in platforms:
        platform = platform.lower()

        if platform not in credentials:
            result.results[platform] = PublishResponse(
                post_id="",
                platform=platform,
                status=PostStatus.FAILED,
                error_message=f"No credentials provided for {platform}",
            )
            result.failed.append(platform)
            continue

        try:
            response = publish_to_platform(
                clip=clip,
                platform=platform,
                credentials=credentials[platform],
            )
            result.results[platform] = response

            if response.status == PostStatus.FAILED:
                result.failed.append(platform)
            else:
                result.successful.append(platform)

        except Exception as e:
            result.results[platform] = PublishResponse(
                post_id="",
                platform=platform,
                status=PostStatus.FAILED,
                error_message=str(e),
            )
            result.failed.append(platform)

    return result



# =============================================================================
# Task 15.9: Platform-Specific Formatting
# =============================================================================

def format_for_platform(clip: ClipMetadata, platform: str) -> FormattedContent:
    """
    Format clip metadata with platform-specific title/description/hashtags.

    Each platform has different conventions:
        - TikTok: Hashtags embedded in description, no separate title field
        - YouTube: Title + description + tags array, #Shorts required
        - Instagram: Caption with hashtags appended (often in first comment)
        - LinkedIn: Professional tone, minimal hashtags (3-5 max)

    Args:
        clip: ClipMetadata with raw title, description, and hashtags.
        platform: Target platform name.

    Returns:
        FormattedContent with platform-optimized title, description, hashtags.

    Raises:
        ValueError: If platform is not supported.
    """
    platform = platform.lower()
    config = PLATFORM_CONFIGS.get(platform)

    if config is None:
        raise ValueError(
            f"Unsupported platform: '{platform}'. "
            f"Supported: {list(PLATFORM_CONFIGS.keys())}"
        )

    if platform == "tiktok":
        return _format_for_tiktok(clip, config)
    elif platform == "youtube":
        return _format_for_youtube(clip, config)
    elif platform == "instagram":
        return _format_for_instagram(clip, config)
    elif platform == "linkedin":
        return _format_for_linkedin(clip, config)
    else:
        # Generic fallback
        return FormattedContent(
            platform=platform,
            title=clip.title[:config.max_title_length],
            description=clip.description[:config.max_description_length],
            hashtags=clip.hashtags[:config.max_hashtags],
        )


def _format_for_tiktok(clip: ClipMetadata, config: PlatformConfig) -> FormattedContent:
    """
    TikTok formatting: hashtags embedded directly in description.
    TikTok doesn't have a separate title — everything goes in the description.
    """
    hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in clip.hashtags[:config.max_hashtags])

    # TikTok: description + hashtags combined
    description = clip.description
    if hashtag_str:
        description = f"{clip.description}\n\n{hashtag_str}"

    # Truncate to max length
    description = description[:config.max_description_length]

    return FormattedContent(
        platform="tiktok",
        title=clip.title[:config.max_title_length],
        description=description,
        hashtags=clip.hashtags[:config.max_hashtags],
    )



def _format_for_youtube(clip: ClipMetadata, config: PlatformConfig) -> FormattedContent:
    """
    YouTube Shorts formatting: title + description + tags array.
    Must include #Shorts in title or description for Shorts shelf placement.
    """
    # Ensure #Shorts is in the title
    title = clip.title
    if "#shorts" not in title.lower():
        title = f"{clip.title} #Shorts"
    title = title[:config.max_title_length]

    # YouTube uses tags as a separate array (not in description)
    tags = [tag.lstrip("#") for tag in clip.hashtags[:config.max_hashtags]]

    # Add relevant hashtags at end of description
    hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in clip.hashtags[:5])
    description = clip.description
    if hashtag_str:
        description = f"{clip.description}\n\n{hashtag_str}"
    description = description[:config.max_description_length]

    return FormattedContent(
        platform="youtube",
        title=title,
        description=description,
        hashtags=clip.hashtags[:config.max_hashtags],
        tags=tags,
    )


def _format_for_instagram(clip: ClipMetadata, config: PlatformConfig) -> FormattedContent:
    """
    Instagram formatting: caption with hashtags appended.
    Instagram doesn't use a title field — only caption (description).
    Best practice: 3-5 hashtags in caption, rest in first comment.
    """
    # Instagram: combine title + description as caption
    caption_parts = []
    if clip.title:
        caption_parts.append(clip.title)
    if clip.description:
        caption_parts.append(clip.description)

    caption = "\n\n".join(caption_parts)

    # Add hashtags (Instagram best practice: hashtags at end of caption)
    hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in clip.hashtags[:config.max_hashtags])
    if hashtag_str:
        caption = f"{caption}\n\n.\n.\n.\n{hashtag_str}"

    caption = caption[:config.max_description_length]

    return FormattedContent(
        platform="instagram",
        title="",  # Instagram doesn't use titles
        description=caption,
        hashtags=clip.hashtags[:config.max_hashtags],
        caption=caption,
    )


def _format_for_linkedin(clip: ClipMetadata, config: PlatformConfig) -> FormattedContent:
    """
    LinkedIn formatting: professional tone, minimal hashtags (3-5 max).
    LinkedIn posts should be business-appropriate and value-driven.
    """
    # LinkedIn: professional formatting with limited hashtags
    professional_hashtags = clip.hashtags[:config.max_hashtags]  # Max 5 for LinkedIn

    # Build description with professional structure
    description_parts = []
    if clip.title:
        description_parts.append(clip.title)
    if clip.description:
        description_parts.append(clip.description)

    description = "\n\n".join(description_parts)

    # Add hashtags sparingly at the end (LinkedIn style)
    if professional_hashtags:
        hashtag_str = " ".join(f"#{tag.lstrip('#')}" for tag in professional_hashtags)
        description = f"{description}\n\n{hashtag_str}"

    description = description[:config.max_description_length]

    return FormattedContent(
        platform="linkedin",
        title=clip.title[:config.max_title_length],
        description=description,
        hashtags=professional_hashtags,
    )



# =============================================================================
# Task 15.10: Get Post Status
# =============================================================================

def get_post_status(post_id: str, platform: str) -> PublishResponse:
    """
    Track the status of a published/scheduled post.

    Queries the platform API to get the current status of a post.

    Args:
        post_id: The platform-specific post identifier.
        platform: The platform the post was published to.

    Returns:
        PublishResponse with current status.

    Raises:
        ValueError: If platform is not supported.
    """
    publisher = _get_publisher(platform)

    try:
        status = publisher.get_status(post_id)
        return PublishResponse(
            post_id=post_id,
            platform=platform,
            status=status,
        )
    except NotImplementedError as e:
        return PublishResponse(
            post_id=post_id,
            platform=platform,
            status=PostStatus.PENDING,
            error_message=str(e),
        )
    except Exception as e:
        return PublishResponse(
            post_id=post_id,
            platform=platform,
            status=PostStatus.FAILED,
            error_message=f"Status check failed: {str(e)}",
        )
