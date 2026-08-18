from safco_agent.agents.category_discovery import CategoryDiscoveryAgent
from safco_agent.agents.page_classifier import PageClassifierAgent, PageType


def test_category_discovery_keeps_child_catalog_links() -> None:
    agent = CategoryDiscoveryAgent()

    result = agent.discover_from_links(
        "https://www.safcodental.com/catalog/gloves",
        [
            ("Nitrile gloves", "https://www.safcodental.com/catalog/gloves/nitrile-gloves"),
            ("GloveUp", "https://www.safcodental.com/product/gloveup-sup-reg-sup"),
            ("Other", "https://www.safcodental.com/catalog/anesthetics"),
        ],
    )

    assert [category.name for category in result] == ["Nitrile gloves"]


def test_page_classifier_product_url_wins() -> None:
    classifier = PageClassifierAgent()

    page_type = classifier.classify(
        "https://www.safcodental.com/product/gloveup-sup-reg-sup",
        "GloveUp From $28.99 Description",
    )

    assert page_type == PageType.PRODUCT

