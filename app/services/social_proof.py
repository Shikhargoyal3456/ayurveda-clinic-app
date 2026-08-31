from __future__ import annotations

from services.startup_service import get_social_proof_activity


class SocialProofGenerator:
    def get_random_testimonial(self) -> str:
        return get_social_proof_activity()

    def get_recent_activity(self) -> str:
        return get_social_proof_activity()
