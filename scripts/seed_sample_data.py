from __future__ import annotations

from services.startup_service import bootstrap_demo_state, get_demo_inventory_snapshot
from scripts.generate_demo_data import generate_demo_activity


def main() -> None:
    bootstrap_demo_state(force=True)
    generate_demo_activity()
    inventory = get_demo_inventory_snapshot()
    print("Sample startup demo data seeded.")
    print(
        f"Doctors: {inventory['verified_doctors']}, "
        f"Centers: {inventory['panchakarma_centers']}, "
        f"Products: {inventory['products']}, "
        f"Journeys: {inventory['patient_journeys']}"
    )


if __name__ == "__main__":
    main()
