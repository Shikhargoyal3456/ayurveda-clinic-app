from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.database import commit_with_retry
from models.user import Gender, PatientProfile, User, UserProfile


MAX_USER_PROFILES = 6
DEFAULT_AVATAR = "👤"
RELATIONSHIP_AVATARS = {
    "self": "👤",
    "myself": "👤",
    "spouse": "👩",
    "wife": "👩",
    "husband": "👨",
    "father": "👴",
    "mother": "👵",
    "son": "👦",
    "daughter": "👧",
    "grandfather": "👴",
    "grandmother": "👵",
    "baby": "👶",
    "other": "👤",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def profile_avatar_for_relationship(relationship: str, explicit_avatar: str | None = None) -> str:
    avatar = (explicit_avatar or "").strip()
    if avatar:
        return avatar
    return RELATIONSHIP_AVATARS.get((relationship or "").strip().lower(), DEFAULT_AVATAR)


def active_profiles_for_user(db: Session, user_id: int) -> list[UserProfile]:
    return (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id, UserProfile.is_active.is_(True))
        .order_by(UserProfile.is_primary.desc(), UserProfile.last_accessed.desc(), UserProfile.id.asc())
        .all()
    )


def primary_profile_for_user(db: Session, user_id: int) -> UserProfile | None:
    return (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id, UserProfile.is_active.is_(True))
        .order_by(UserProfile.is_primary.desc(), UserProfile.id.asc())
        .first()
    )


def ensure_default_profile(db: Session, user: User) -> UserProfile:
    existing = primary_profile_for_user(db, user.id)
    if existing is not None:
        return existing
    patient_profile = db.get(PatientProfile, user.id)
    profile = UserProfile(
        user_id=user.id,
        profile_name=(user.full_name or "Myself").strip() or "Myself",
        profile_avatar=DEFAULT_AVATAR,
        relationship="Self",
        date_of_birth=patient_profile.date_of_birth if patient_profile else None,
        gender=patient_profile.gender if patient_profile else None,
        blood_group=patient_profile.blood_group if patient_profile else None,
        medical_conditions=patient_profile.medical_conditions if patient_profile else None,
        allergies=patient_profile.allergies if patient_profile else None,
        is_primary=True,
        is_active=True,
        last_accessed=utc_now(),
    )
    db.add(profile)
    commit_with_retry(db)
    db.refresh(profile)
    return profile


def profile_to_payload(profile: UserProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "profile_name": profile.profile_name,
        "relationship": profile.relationship,
        "avatar_emoji": profile_avatar_for_relationship(profile.relationship, profile.profile_avatar),
        "pin_code": bool(profile.pin_code),
        "is_primary": bool(profile.is_primary),
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "blood_group": profile.blood_group or "",
        "medical_conditions": profile.medical_conditions or "",
        "allergies": profile.allergies or "",
    }


def set_active_profile_session(request, profile: UserProfile) -> None:
    request.session["active_profile_id"] = int(profile.id)
    request.session["active_profile_name"] = profile.profile_name
    request.session["active_profile_avatar"] = profile_avatar_for_relationship(profile.relationship, profile.profile_avatar)
    request.session["active_profile_relationship"] = profile.relationship


def clear_active_profile_session(request) -> None:
    for key in ["active_profile_id", "active_profile_name", "active_profile_avatar", "active_profile_relationship", "pending_profile_id"]:
        request.session.pop(key, None)


def touch_profile(db: Session, profile: UserProfile) -> None:
    profile.last_accessed = utc_now()
    commit_with_retry(db)


def get_user_profile(db: Session, user_id: int, profile_id: int) -> UserProfile | None:
    return (
        db.query(UserProfile)
        .filter(UserProfile.id == profile_id, UserProfile.user_id == user_id, UserProfile.is_active.is_(True))
        .first()
    )


def resolve_active_profile(request, db: Session, user: User) -> UserProfile | None:
    profiles = active_profiles_for_user(db, user.id)
    if not profiles:
        return ensure_default_profile(db, user)
    active_profile_id = request.session.get("active_profile_id")
    if active_profile_id:
        profile = get_user_profile(db, user.id, int(active_profile_id))
        if profile is not None:
            return profile
    if len(profiles) == 1:
        set_active_profile_session(request, profiles[0])
        touch_profile(db, profiles[0])
        return profiles[0]
    primary = next((profile for profile in profiles if profile.is_primary), profiles[0])
    return primary


def count_active_profiles(db: Session, user_id: int) -> int:
    return len(active_profiles_for_user(db, user_id))


def set_primary_profile(db: Session, user_id: int, profile: UserProfile) -> None:
    for item in active_profiles_for_user(db, user_id):
        item.is_primary = item.id == profile.id
    commit_with_retry(db)


def save_profile_pin(raw_pin: str | None) -> str | None:
    normalized = "".join(char for char in (raw_pin or "") if char.isdigit())
    if not normalized:
        return None
    return hash_password(normalized)


def profile_pin_matches(profile: UserProfile, raw_pin: str) -> bool:
    if not profile.pin_code:
        return True
    cleaned = "".join(char for char in raw_pin if char.isdigit())
    if not cleaned:
        return False
    try:
        return verify_password(cleaned, profile.pin_code)
    except Exception:
        return profile.pin_code == cleaned


def parse_gender(value: str | None) -> Gender | None:
    cleaned = (value or "").strip().lower()
    if cleaned in {item.value for item in Gender}:
        return Gender(cleaned)
    return None
