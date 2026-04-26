from app.models import Doctor
from models.subscription import ClinicSubscription, SubscriptionPlan, SubscriptionStatus


def test_subscription_uses_new_schema_columns(db_session):
    doctor = Doctor(
        username="schema_subscriber",
        full_name="Schema Subscriber",
        password_hash="not-a-real-hash",
    )
    db_session.add(doctor)
    db_session.flush()

    subscription = ClinicSubscription(
        user_id=doctor.id,
        plan_id=SubscriptionPlan.BASIC,
        status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(subscription)
    db_session.commit()

    loaded = (
        db_session.query(ClinicSubscription)
        .filter(ClinicSubscription.user_id == doctor.id)
        .one()
    )
    assert loaded.user_id == doctor.id
    assert loaded.plan_id == SubscriptionPlan.BASIC
    assert loaded.status == SubscriptionStatus.ACTIVE
