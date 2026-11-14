"""v0.4.0 research-round router tests. Pins the expanded routing table built
from the ranked top-20 business tasks AI agent users actually ask for, plus
the collision cases the expansion must not break."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools  # noqa: E402


def route(task, domain=None):
    args = {"task": task}
    if domain is not None:
        args["domain"] = domain
    out = json.loads(tools.ceo_route(args))
    assert out["status"] == "success", out
    return out


class ResearchRoundRouting(unittest.TestCase):
    """New terms from the research ranking route to the right seat."""

    def test_writing_and_email_go_to_chief_of_staff(self):
        self.assertEqual(route("Draft an email to the client about the delay")["routed_to"], "Chief of Staff")
        self.assertEqual(route("Write a summary of the meeting notes")["routed_to"], "Chief of Staff")
        self.assertEqual(route("Summarize the research for the team")["routed_to"], "Chief of Staff")

    def test_coding_goes_to_cto(self):
        self.assertEqual(route("Debug the checkout crash on the site")["routed_to"], "CTO")
        self.assertEqual(route("Write code for the new API endpoint")["routed_to"], "CTO")
        self.assertEqual(route("Refactor the server code, it keeps throwing errors")["routed_to"], "CTO")

    def test_content_goes_to_cmo(self):
        self.assertEqual(route("Write a blog post announcing the launch")["routed_to"], "CMO")
        self.assertEqual(route("Draft captions for the new posts")["routed_to"], "CMO")
        self.assertEqual(route("Set up the ads funnel and landing page")["routed_to"], "CMO")

    def test_deals_go_to_cro(self):
        self.assertEqual(route("Close the sales deal with the prospect")["routed_to"], "CRO")
        self.assertEqual(route("Follow up with the lead about the proposal")["routed_to"], "CRO")
        self.assertEqual(route("Open a support ticket about the churn complaint")["routed_to"], "CRO")

    def test_finance_terms_go_to_cfo(self):
        self.assertEqual(route("Forecast Q3 runway and burn rate")["routed_to"], "CFO")
        self.assertEqual(route("Reconcile the bank statements and receipts")["routed_to"], "CFO")
        self.assertEqual(route("Close the quarter and update the dashboard metrics")["routed_to"], "CFO")
        self.assertEqual(route("Close Q4")["routed_to"], "CFO")

    def test_ops_terms_go_to_coo(self):
        self.assertEqual(route("Clear my inbox and check the calendar")["routed_to"], "COO (Hermes)")
        self.assertEqual(route("Extract the numbers from this document")["routed_to"], "COO (Hermes)")
        self.assertEqual(route("Set up monitoring alerts for the project timeline")["routed_to"], "COO (Hermes)")

    def test_people_terms_go_to_chief_of_staff(self):
        self.assertEqual(route("Interview three candidates this week")["routed_to"], "Chief of Staff")
        self.assertEqual(route("Screen resumes and send the job offer")["routed_to"], "Chief of Staff")

    def test_fundraising_goes_to_ceo(self):
        self.assertEqual(route("Raise a seed round from investors")["routed_to"], "CEO")
        self.assertEqual(route("Review the term sheet and update the cap table")["routed_to"], "CEO")
        self.assertEqual(route("Brainstorm the product roadmap and goals")["routed_to"], "CEO")

    def test_legal_terms_go_to_clo(self):
        self.assertEqual(route("Review the supplier agreement and signature clause")["routed_to"], "CLO")
        self.assertEqual(route("Check the copyright and patent filing")["routed_to"], "CLO")


class CollisionCases(unittest.TestCase):
    """Expansion must not break the v0.4.0 P0 fixes or create new misroutes."""

    def test_deal_with_contract_mention_stays_cro(self):
        # CRO matches sales + deal + close (3 terms) vs CLO contract (1).
        out = route("Close the sales deal, contract attached")
        self.assertEqual(out["routed_to"], "CRO")
        self.assertIn("CLO", out["also_consult"])

    def test_close_the_books_stays_cfo(self):
        self.assertEqual(route("Close the books for October")["routed_to"], "CFO")

    def test_contract_review_stays_clo(self):
        self.assertEqual(route("Review the supplier contract")["routed_to"], "CLO")

    def test_laptops_still_not_ops(self):
        out = route("Review the proposal for new laptops")
        self.assertNotEqual(out["routed_to"], "COO (Hermes)")

    def test_write_code_beats_write(self):
        # "write" is Chief of Staff, "code" + "api" are CTO (2 vs 1).
        self.assertEqual(route("Write code for the API")["routed_to"], "CTO")

    def test_explicit_domain_still_wins(self):
        self.assertEqual(route("Close the sales deal", domain="legal")["routed_to"], "CLO")
        self.assertEqual(route("Review the contract", domain="sales")["routed_to"], "CRO")
        self.assertEqual(route("Draft the investor update", domain="email")["routed_to"], "Chief of Staff")
        self.assertEqual(route("Fix the bug", domain="fundraising")["routed_to"], "CEO")


if __name__ == "__main__":
    unittest.main()
