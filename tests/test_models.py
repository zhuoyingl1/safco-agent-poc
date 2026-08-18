from safco_agent.models import ExtractionStatus, Price, ProductRecord


def test_product_record_has_stable_id() -> None:
    record = ProductRecord(
        parent_product_name="Safco Nitrilex",
        brand="Safco",
        sku="12345",
        category_path=["Dental Supplies", "Gloves", "Nitrile gloves"],
        product_url="https://www.safcodental.com/product/safco-nitrilex-reg-nitrile-gloves",
        price=Price(raw="From $6.49", amount="6.49"),
        extraction_status=ExtractionStatus.COMPLETE,
    )

    assert len(record.product_id) == 64
    assert record.price is not None
    assert record.price.currency == "USD"

