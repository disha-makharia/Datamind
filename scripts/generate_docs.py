"""
Generate NovaMart "company documents" (PDFs) for the RAG agent.
Each document explains one of the patterns hidden in the dummy data.

Run:  python scripts/generate_docs.py
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
DOCS_DIR.mkdir(exist_ok=True)
styles = getSampleStyleSheet()

DOCUMENTS = {
    "NovaMart_Q3_2025_Business_Review.pdf": ("NovaMart Q3 2025 Business Review", [
        ("Summary", "Q3 2025 (July to September) was a mixed quarter for NovaMart. Overall revenue "
         "grew year on year, driven by the South region and the Grocery and Beauty categories. "
         "However, Electronics revenue in the West region fell sharply, by roughly half compared "
         "with Q2 2025."),
        ("West region Electronics decline", "On 7 July 2025, heavy monsoon rainfall flooded the "
         "Bhiwandi distribution centre near Mumbai, which supplies all West region stores "
         "(Andheri, Thane, Kothrud, SG Highway) and online orders shipped to West region "
         "customers. Around 40 percent of Electronics inventory held at Bhiwandi, mainly Smart "
         "TVs, phones and laptops, was damaged. From 8 July to 20 September 2025 most Electronics "
         "SKUs were out of stock in the West. Customers shifted spending to Grocery, Beauty and "
         "Fashion, which were supplied from a separate warehouse in Taloja and were unaffected."),
        ("Mitigation", "From mid-August the supply chain team routed part of the Electronics "
         "replenishment from the Hyderabad distribution centre, which reduced but did not remove "
         "stock-outs. Full operations at Bhiwandi resumed on 21 September 2025. An insurance claim "
         "has been filed for the damaged stock. Operations has approved raised racking and flood "
         "barriers at Bhiwandi before the 2026 monsoon."),
        ("South region", "South continued the strong growth that began after the two new stores "
         "opened in February 2025 (see the South Expansion Update)."),
        ("NovaSound X2 Earbuds", "The return rate for NovaSound X2 Earbuds fell back towards "
         "normal levels in Q3 after the battery fix introduced in July 2025 (see the Product "
         "Quality and Returns Memo)."),
        ("Outlook for Q4", "Q4 performance is expected to depend heavily on the Festive Dhamaka "
         "2025 campaign planned for 15 October to 15 November 2025, with West Electronics "
         "inventory fully rebuilt ahead of the festive season."),
    ]),
    "NovaMart_Festive_Dhamaka_2025_Campaign_Report.pdf": ("Festive Dhamaka 2025 - Campaign Report", [
        ("Campaign overview", "Festive Dhamaka 2025 ran from 15 October to 15 November 2025 across "
         "TV, online and in-store channels in all regions, timed around Diwali. The total budget was "
         "INR 85 lakh, the largest marketing investment in NovaMart's history."),
        ("Offer structure", "Electronics and Fashion carried discounts of 15 to 25 percent. The "
         "biggest offers were on Smart TVs, the Nova Laptop Air 14, phones, Banarasi silk sarees "
         "and the Festive Lehenga Choli. Other categories ran at normal pricing."),
        ("Results", "Daily order volume during the campaign was close to double the normal run "
         "rate. Electronics and Fashion drove most of the increase. October and November 2025 "
         "became the two highest revenue months of the year. The West region recovered fully "
         "from the Q3 warehouse disruption, as Bhiwandi inventory had been rebuilt."),
        ("Comparison with 2024", "The 2024 Diwali Utsav campaign (20 October to 10 November 2024, "
         "budget INR 55 lakh) focused only on Electronics with discounts of 10 to 20 percent. "
         "Festive Dhamaka 2025 was longer, broader and delivered a significantly larger uplift."),
        ("Learnings", "Deep discounts lowered gross margin per order during the campaign, so the "
         "finance team recommends capping Electronics discounts at 20 percent in 2026 except for "
         "clearance stock. Online orders grew faster than in-store orders during the campaign."),
    ]),
    "NovaMart_Product_Quality_and_Returns_Memo_2025.pdf": ("Product Quality and Returns Memo - 2025", [
        ("Purpose", "This memo summarises product quality issues that affected returns in 2025 and "
         "restates NovaMart's return policy."),
        ("NovaSound X2 Earbuds battery defect", "NovaSound X2 Earbuds launched on 1 March 2025 and "
         "sold strongly. From late March, customers began returning units with complaints that the "
         "battery drained quickly or the earbuds stopped charging. Investigation traced the issue "
         "to a faulty battery cell batch, B-0325, from a single supplier. Between April and June "
         "2025 the return rate for this product rose to roughly 30 percent, against a normal "
         "Electronics return rate of about 3 percent."),
        ("Corrective action", "In July 2025 NovaMart switched to a new battery supplier and released "
         "firmware version 1.4, which improved charging behaviour on existing units. Units from the "
         "affected batch were replaced free of charge. Returns for the product fell to normal "
         "levels from August 2025."),
        ("Return policy", "Electronics can be returned within 10 days of purchase if defective or "
         "damaged. Fashion items can be returned within 30 days for size or colour issues. Grocery "
         "items can only be returned for damaged packaging or expired products. Refunds are issued "
         "to the original payment method within 7 working days; Cash on Delivery orders are "
         "refunded by bank transfer."),
        ("Fashion returns", "Fashion has the highest structural return rate, around 7 percent, "
         "mostly due to size issues. The merchandising team is adding size charts to all product "
         "pages in 2026."),
    ]),
    "NovaMart_South_Expansion_Update_2025.pdf": ("South Region Expansion Update - 2025", [
        ("New stores", "NovaMart opened two new stores in the South region in February 2025: "
         "NovaMart Whitefield in Bengaluru (mall format, opened 10 February 2025) and NovaMart "
         "T Nagar in Chennai (high-street format, opened 24 February 2025). Chennai was a new city "
         "for NovaMart."),
        ("Rationale", "Market research showed that South region customers were travelling long "
         "distances to the Koramangala and Banjara Hills stores, and online penetration in "
         "Bengaluru was high. The new stores were expected to lift South order volume by 25 to 30 "
         "percent."),
        ("Early performance", "Since opening, South region order volume has grown faster than any "
         "other region, and South overtook West as NovaMart's largest region by order count in "
         "2025. The South Store Opening Offers campaign (10 February to 15 March 2025, INR 9 lakh) "
         "supported the launches."),
        ("Next steps", "A third South store in Kochi is under evaluation for 2026."),
    ]),
    "NovaMart_Pricing_and_Discount_Policy.pdf": ("Pricing and Discount Policy", [
        ("Scope", "This policy applies to all NovaMart stores and the online channel."),
        ("Standard discounts", "Store managers may offer up to 10 percent discount without approval. "
         "Discounts between 10 and 25 percent require approval from the regional category manager "
         "and are normally limited to approved campaigns. Discounts above 25 percent are not "
         "permitted except for clearance stock approved by the Chief Commercial Officer."),
        ("Seasonal campaigns", "Summer Cool Deals (April and May) offer 5 to 15 percent on Home and "
         "Kitchen products such as ceiling fans, air fryers and RO water purifiers, when seasonal "
         "demand for these products is highest."),
        ("Price changes", "List prices are reviewed every quarter. Cost price changes above 5 "
         "percent trigger an immediate review."),
    ]),
}

for filename, (title, sections) in DOCUMENTS.items():
    doc = SimpleDocTemplate(str(DOCS_DIR / filename), pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title=title, author="NovaMart Pvt Ltd (fictional)")
    story = [Paragraph(title, styles["Title"]),
             Paragraph("NovaMart Pvt Ltd - Internal document (fictional, for DataMind demo)", styles["Italic"]),
             Spacer(1, 0.5 * cm)]
    for heading, text in sections:
        story += [Paragraph(heading, styles["Heading2"]), Paragraph(text, styles["BodyText"]),
                  Spacer(1, 0.3 * cm)]
    doc.build(story)
    print("wrote", filename)
