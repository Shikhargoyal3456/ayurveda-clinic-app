import pytest


pytestmark = pytest.mark.asyncio


async def test_supplier_crud(admin_client):
    # SUPPLIER-FULL-1: Admin can create, list, read, update, and order from suppliers.
    client = admin_client["client"]

    list_response = await client.get("/admin/suppliers")
    assert list_response.status_code == 200
    assert len(list_response.json()["suppliers"]) >= 2

    create_response = await client.post(
        "/admin/supplier/register",
        json={
            "id": "sup_test_crud",
            "name": "Test Supplier",
            "phone": "9999999999",
            "location": "Delhi",
            "categories": ["general", "rare"],
            "whatsapp": "9999999999",
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["success"] is True

    detail_response = await client.get("/admin/supplier/sup_test_crud")
    assert detail_response.status_code == 200
    assert detail_response.json()["supplier"]["name"] == "Test Supplier"

    update_response = await client.put(
        "/admin/supplier/sup_test_crud",
        json={"name": "Updated Supplier", "categories": ["tablets"]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["supplier"]["name"] == "Updated Supplier"
    assert update_response.json()["supplier"]["categories"] == ["tablets"]

    order_response = await client.post(
        "/admin/supplier/sup_test_crud/order",
        json={"medicine": "Paracetamol", "quantity": 25, "category": "tablets"},
    )
    assert order_response.status_code == 200
    assert order_response.json()["success"] is True
    assert order_response.json()["order"]["supplier_id"] == "sup_test_crud"

    delete_response = await client.delete("/admin/supplier/sup_test_crud")
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True
    assert delete_response.json()["supplier"]["is_active"] is False


async def test_inventory_restock_triggers_supplier_order(admin_client):
    # SUPPLIER-FULL-1: Low stock automatically selects the best matching active supplier.
    client = admin_client["client"]

    await client.post(
        "/admin/supplier/register",
        json={
            "id": "sup_tablets_restock",
            "name": "AA Tablet Restock Supplier",
            "categories": ["tablets"],
        },
    )

    from services import inventory_service
    from services.supplier_service import get_supplier_orders

    inventory_service._INVENTORY["Paracetamol"] = {"stock": 11}
    before_count = len(get_supplier_orders())
    inventory_service.reduce_stock("Paracetamol", 3)
    orders = get_supplier_orders()

    assert len(orders) == before_count + 1
    assert orders[-1]["medicine"] == "Paracetamol"
    assert orders[-1]["quantity"] == 50
    assert orders[-1]["supplier_id"] == "sup_tablets_restock"
