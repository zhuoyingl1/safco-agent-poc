from safco_agent.agents.category_discovery import CategoryDiscoveryAgent
from safco_agent.agents.navigator import NavigatorAgent
from safco_agent.agents.page_classifier import PageClassifierAgent, PageType
from safco_agent.browser import LinkCandidate, PageSnapshot
from safco_agent.config import SeedCategory


def test_category_discovery_keeps_child_catalog_links() -> None:
    agent = CategoryDiscoveryAgent()

    result = agent.discover_from_links(
        "https://www.safcodental.com/catalog/gloves",
        [
            ("Nitrile gloves", "https://www.safcodental.com/catalog/gloves/nitrile-gloves"),
            ("Nitrile duplicate", "https://www.safcodental.com/catalog/gloves/nitrile-gloves?x=1#top"),
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


def test_navigator_collects_product_links_and_skips_global_clearance() -> None:
    navigator = NavigatorAgent()
    seed = SeedCategory(
        key="gloves",
        name="Dental Exam Gloves",
        url="https://www.safcodental.com/catalog/gloves",
    )
    snapshot = PageSnapshot(
        requested_url="https://www.safcodental.com/catalog/gloves",
        final_url="https://www.safcodental.com/catalog/gloves",
        title="Dental Exam Gloves | Safco Dental Supply",
        h1="Dental Exam Gloves",
        body_sample="Dental Exam Gloves",
        body_text="Dental Exam Gloves",
        links=[
            LinkCandidate(text="Clearance", href="https://www.safcodental.com/product/clearance-item"),
            LinkCandidate(text="GloveUp As low as $28.99", href="https://www.safcodental.com/product/gloveup-sup-reg-sup?promo=1"),
            LinkCandidate(text="Duplicate", href="https://www.safcodental.com/product/gloveup-sup-reg-sup#details"),
            LinkCandidate(text="Nitrile Gloves", href="https://www.safcodental.com/catalog/gloves/nitrile-gloves"),
        ],
    )

    result = navigator.collect_product_links(snapshot, seed)

    assert [candidate.url for candidate in result] == [
        "https://www.safcodental.com/product/gloveup-sup-reg-sup"
    ]
