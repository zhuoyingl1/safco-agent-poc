import json

from safco_agent.agents.product_extractor import ProductExtractorAgent
from safco_agent.browser import PageSnapshot
from safco_agent.models import ExtractionStatus


def test_product_extractor_expands_json_ld_variants() -> None:
    snapshot = PageSnapshot(
        requested_url="https://www.safcodental.com/product/aurelia-reg-amazing-reg",
        final_url="https://www.safcodental.com/product/aurelia-reg-amazing-reg",
        title="Aurelia Amazing",
        h1="Aurelia Amazing",
        links=[],
        body_sample="Aurelia Amazing From $20.99",
        body_text="Aurelia Amazing From $20.99",
        json_ld=[
            json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "ProductGroup",
                    "url": "https://www.safcodental.com/product/aurelia-reg-amazing-reg",
                    "name": "Aurelia Amazing",
                    "description": "Powder-free nitrile exam gloves. Thickness: at palm 2.0 mils; 300 gloves per box.",
                    "sku": "DRCBM",
                    "image": [
                        "https://www.safcodental.com/media/catalog/product/d/r/drcbm.jpg"
                    ],
                    "brand": {"@type": "Brand", "name": "Supermax"},
                    "category": "Dental Supplies > Dental Exam Gloves > Nitrile gloves",
                    "productGroupID": "DRCBM",
                    "hasVariant": [
                        {
                            "@type": "Product",
                            "@id": "https://www.safcodental.com/product/aurelia-reg-amazing-reg#variant-4871102",
                            "name": "Aurelia Amazing gloves x-small 300/box",
                            "sku": "4871102",
                            "offers": {
                                "@type": "Offer",
                                "price": "20.99",
                                "priceCurrency": "USD",
                                "availability": "https://schema.org/InStock",
                            },
                        }
                    ],
                }
            )
        ],
    )

    records = ProductExtractorAgent().extract(
        snapshot,
        source_category_url="https://www.safcodental.com/catalog/gloves",
    )

    assert len(records) == 1
    record = records[0]
    assert record.parent_product_name == "Aurelia Amazing"
    assert record.variant_name == "Aurelia Amazing gloves x-small 300/box"
    assert record.brand == "Supermax"
    assert record.sku == "4871102"
    assert record.category_path == [
        "Dental Supplies",
        "Dental Exam Gloves",
        "Nitrile gloves",
    ]
    assert record.price is not None
    assert record.price.amount is not None
    assert str(record.price.amount) == "20.99"
    assert record.availability == "InStock"
    assert record.unit_pack_size == "300/box"
    assert record.specifications["thickness"] == "at palm 2.0 mils"
    assert record.extraction_status == ExtractionStatus.COMPLETE


def test_product_extractor_falls_back_without_json_ld() -> None:
    snapshot = PageSnapshot(
        requested_url="https://www.safcodental.com/product/example",
        final_url="https://www.safcodental.com/product/example",
        title="Example Product",
        h1="Example Product",
        links=[],
        body_sample="Example Product From $12.34",
        body_text="Example Product From $12.34",
        json_ld=[],
    )

    records = ProductExtractorAgent().extract(snapshot)

    assert len(records) == 1
    assert records[0].parent_product_name == "Example Product"
    assert records[0].price is not None
    assert str(records[0].price.amount) == "12.34"
    assert records[0].errors == ["product JSON-LD not found"]
