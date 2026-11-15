from agent.config import load_config
from agent.nodes.compliance import apply_rules

RULES = load_config()["compliance"]["rules"]


def test_phone_numbers_scrubbed_but_dates_and_amounts_survive():
    text, v = apply_rules("Call +92 300 1234567 or 0300-1234567.", RULES)
    assert "1234567" not in text and {x.rule for x in v} == {"contact_phone"}
    kept, v = apply_rules("Slots: 2026-11-09T11:00 and 2026-11-10T12:00; budget 1,200 USD for 14 days.", RULES)
    assert "2026-11-09T11:00" in kept and "2026-11-10T12:00" in kept and not v


def test_email_scrubbed_guarantee_sentence_dropped_offplatform_blocks():
    text, v = apply_rules("Mail me at a.b@example.com. I guarantee results. Happy to help.", RULES)
    assert "example.com" not in text and "guarantee" not in text and "Happy to help" in text
    _, v = apply_rules("Let's use WhatsApp.", RULES)
    assert [(x.rule, x.action) for x in v] == [("off_platform", "block")]
