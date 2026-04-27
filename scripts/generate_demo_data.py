from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from services.startup_service import bootstrap_demo_state, store_demo_metrics


def generate_demo_activity() -> None:
    bootstrap_demo_state(force=False)
    rows = []
    for day in range(30):
        date = datetime.now(timezone.utc).date() - timedelta(days=29 - day)
        consultations = random.randint(5, 50)
        panchakarma_bookings = random.randint(1, 10)
        product_orders = random.randint(10, 100)
        new_patients = random.randint(3, 25)
        daily_active_users = random.randint(90, 300) + day * 18
        rows.append(
            {
                "date": date.isoformat(),
                "consultations": consultations,
                "panchakarma_bookings": panchakarma_bookings,
                "product_orders": product_orders,
                "new_patients": new_patients,
                "daily_active_users": daily_active_users,
                "kits_sold": max(1, product_orders // 8),
                "interaction_checks": random.randint(8, 45),
                "community_posts": random.randint(1, 10),
                "referral_signups": random.randint(1, 14),
            }
        )
    store_demo_metrics(rows)
    print("Demo data generated successfully.")


if __name__ == "__main__":
    generate_demo_activity()
