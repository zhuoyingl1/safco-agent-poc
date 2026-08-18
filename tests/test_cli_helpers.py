from safco_agent.cli import _product_candidates_from_discovery


def test_product_candidates_take_limit_per_category() -> None:
    payload = {
        "categories": [
            {
                "product_urls": [
                    {
                        "url": "https://www.safcodental.com/product/a",
                        "text": "A",
                        "source_page_url": "https://www.safcodental.com/catalog/gloves",
                        "source_category_key": "gloves",
                        "source_category_name": "Dental Exam Gloves",
                    },
                    {
                        "url": "https://www.safcodental.com/product/b",
                        "text": "B",
                        "source_page_url": "https://www.safcodental.com/catalog/gloves",
                        "source_category_key": "gloves",
                        "source_category_name": "Dental Exam Gloves",
                    },
                ]
            },
            {
                "product_urls": [
                    {
                        "url": "https://www.safcodental.com/product/c",
                        "text": "C",
                        "source_page_url": "https://www.safcodental.com/catalog/sutures-surgical-products",
                        "source_category_key": "sutures_surgical",
                        "source_category_name": "Sutures & surgical products",
                    },
                ]
            },
        ]
    }

    candidates = _product_candidates_from_discovery(
        payload,
        max_products=None,
        max_products_per_category=1,
    )

    assert [candidate.source_category_key for candidate in candidates] == [
        "gloves",
        "sutures_surgical",
    ]

