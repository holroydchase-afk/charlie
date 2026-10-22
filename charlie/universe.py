"""Knowledge domains, the keywords that signal them, and a curated ticker universe.

The universe is deliberately small and quality-tilted: Munger's "circle of
competence" works best when the circle maps to a short list of businesses you can
actually follow. Each ticker carries *illustrative* fundamentals used only by the
mock data provider when live data is unavailable. They are rough, rounded, and
not a substitute for real filings.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Domain:
    key: str
    label: str
    keywords: tuple[str, ...]
    tickers: tuple[str, ...]
    etf: str
    blurb: str


@dataclass(frozen=True)
class TickerInfo:
    symbol: str
    name: str
    domain: str
    aliases: tuple[str, ...] = ()
    # Illustrative mock fundamentals (approximate, for offline demo only)
    price: float = 100.0
    vol: float = 0.30            # annualized volatility
    roic: float = 0.15
    gross_margin: float = 0.40
    op_margin: float = 0.15
    op_margin_stdev: float = 0.03
    fcf_margin: float = 0.10
    debt_to_equity: float = 0.6
    rev_growth: float = 0.06
    share_change: float = -0.01  # yearly share count change (negative = buybacks)
    pe: float = 22.0
    extra: dict = field(default_factory=dict)


DOMAINS: tuple[Domain, ...] = (
    Domain("software_cloud", "Software & Cloud",
           ("software", "saas", "cloud", "aws", "azure", "gcp", "kubernetes", "devops", "python",
            "java", "javascript", "typescript", "react", "api", "microservices", "salesforce", "crm",
            "erp", "sql", "database", "data engineering", "backend", "frontend", "full stack",
            "full-stack", "sre", "terraform", "docker", "agile", "scrum", "product manager"),
           ("MSFT", "CRM", "ADBE", "ORCL", "NOW", "INTU"), "IGV",
           "Recurring-revenue software businesses with high gross margins and switching costs."),
    Domain("ai_semis", "AI & Semiconductors",
           ("machine learning", "artificial intelligence", "deep learning", "gpu", "cuda", "semiconductor",
            "chip", "fpga", "asic", "verilog", "embedded", "llm", "pytorch", "tensorflow", "computer vision",
            "nlp", "data science", "hardware engineer", "silicon", "wafer", "lithography"),
           ("NVDA", "AVGO", "TSM", "ASML", "AMD", "QCOM"), "SMH",
           "The picks-and-shovels of computing; cyclical, but the leaders have deep moats."),
    Domain("cybersecurity", "Cybersecurity",
           ("security", "cybersecurity", "infosec", "soc", "siem", "penetration", "pentest", "zero trust",
            "iam", "identity", "firewall", "soc 2", "soc2", "vulnerability", "incident response", "cissp",
            "threat"),
           ("PANW", "CRWD", "FTNT", "ZS", "NET"), "CIBR",
           "Mission-critical spend that rarely gets cut, with sticky platforms."),
    Domain("internet_consumer", "Internet & Consumer Tech",
           ("e-commerce", "ecommerce", "marketplace", "social media", "digital marketing", "seo", "sem",
            "advertising", "ads", "growth marketing", "iphone", "ios", "android", "mobile app", "ux",
            "user experience", "content strategy", "influencer", "creator"),
           ("AAPL", "AMZN", "GOOGL", "META", "UBER", "BKNG"), "XLC",
           "Network effects and scale economies; you see these products every day."),
    Domain("payments_fintech", "Payments & Fintech",
           ("payments", "fintech", "credit card", "card network", "stripe", "lending", "underwriting", "kyc",
            "aml", "fraud", "merchant", "point of sale", "pos", "remittance", "crypto", "blockchain"),
           ("V", "MA", "AXP", "PYPL", "FI"), "IPAY",
           "Toll-road economics on every transaction; among Munger's favorite business models."),
    Domain("banks_finance", "Banking, Insurance & Asset Mgmt",
           ("investment banking", "finance", "accounting", "cpa", "audit", "private equity", "asset management",
            "financial analyst", "cfa", "wealth management", "insurance", "actuary", "actuarial", "bank",
            "banking", "treasury", "fp&a", "budgeting", "underwriter", "claims", "brokerage"),
           ("BRK.B", "JPM", "BLK", "SCHW", "PGR", "GS"), "XLF",
           "Financials live on trust and capital discipline. Berkshire is the original Munger vehicle."),
    Domain("healthcare", "Healthcare Services & Devices",
           ("nurse", "nursing", "hospital", "clinical", "physician", "healthcare", "health care", "patient",
            "ehr", "epic systems", "medical", "pharmacy", "pharmacist", "medicare", "medicaid", "surgical",
            "surgery", "radiology", "physical therapy", "dental", "emt", "medical device"),
           ("UNH", "ISRG", "ABT", "SYK", "HCA", "JNJ"), "XLV",
           "Demographics are a tailwind; devices and services with pricing power compound well."),
    Domain("biotech_pharma", "Pharma & Biotech",
           ("biotech", "pharma", "pharmaceutical", "drug discovery", "clinical trial", "fda", "molecular",
            "genomics", "crispr", "laboratory", "lab", "chemistry", "biology", "immunology", "oncology",
            "regulatory affairs", "gmp", "bioinformatics"),
           ("LLY", "ABBV", "MRK", "VRTX", "AMGN", "TMO"), "XBI",
           "Patents create temporary moats; pipeline knowledge is a real edge here."),
    Domain("retail_consumer", "Retail & Consumer Brands",
           ("retail", "store manager", "merchandising", "consumer goods", "cpg", "brand management", "fashion",
            "apparel", "grocery", "category manager", "buyer", "fitness", "gym", "sneakers", "athletic",
            "home improvement", "diy", "beauty", "cosmetics"),
           ("COST", "WMT", "HD", "NKE", "TJX", "LULU"), "XLY",
           "Peter Lynch's hunting ground: you can 'kick the tires' by walking into the store."),
    Domain("restaurants_food", "Restaurants, Food & Beverage",
           ("restaurant", "chef", "food service", "hospitality", "barista", "kitchen", "beverage", "bartender",
            "culinary", "catering", "franchise", "food science", "coffee"),
           ("MCD", "CMG", "SBUX", "KO", "PEP", "YUM"), "PBJ",
           "Brands with habits attached. Coca-Cola is a Berkshire classic."),
    Domain("energy", "Energy & Utilities",
           ("oil", "gas", "petroleum", "drilling", "pipeline", "refinery", "utilities", "utility", "solar",
            "wind", "renewable", "power grid", "electrician", "electrical engineer", "lineman", "nuclear",
            "battery storage", "energy"),
           ("XOM", "CVX", "NEE", "COP", "FSLR", "VST"), "XLE",
           "Commodity-driven and cyclical; operators who know the field see the cycle early."),
    Domain("industrials_aero", "Industrials, Aerospace & Defense",
           ("manufacturing", "mechanical engineer", "aerospace", "defense", "lean", "six sigma", "cnc",
            "machining", "factory", "construction", "civil engineer", "hvac", "welding", "plant manager",
            "military", "army", "navy", "air force", "marines", "veteran", "operations manager", "cad",
            "solidworks", "heavy equipment", "agriculture", "farming"),
           ("CAT", "DE", "HON", "GE", "LMT", "RTX"), "XLI",
           "Real-economy businesses; durable franchises in equipment and defense."),
    Domain("autos_ev", "Autos & EVs",
           ("automotive", "electric vehicle", "ev", "battery", "dealership", "mechanic", "autonomous",
            "self-driving", "powertrain", "car sales", "motorsport"),
           ("TSLA", "TM", "GM", "F"), "DRIV",
           "Capital-intensive and competitive; Munger owned BYD, but he was choosy."),
    Domain("transport_logistics", "Transportation & Logistics",
           ("logistics", "supply chain", "trucking", "freight", "warehouse", "shipping", "fleet", "airline",
            "pilot", "flight attendant", "rail", "distribution center", "procurement", "inventory"),
           ("UNP", "ODFL", "UPS", "FDX", "DAL"), "IYT",
           "Railroads are Berkshire's other moat (BNSF); you see volumes before Wall Street does."),
    Domain("media_gaming", "Media, Streaming & Gaming",
           ("gaming", "video games", "game developer", "unity", "unreal", "esports", "streaming", "film",
            "music", "content creator", "youtube", "twitch", "animation", "journalism", "publishing",
            "sports", "nfl", "nba"),
           ("NFLX", "DIS", "SPOT", "TTWO", "EA", "RBLX"), "SOCL",
           "Hit-driven, but platforms with subscriber scale have real pricing power."),
    Domain("real_estate", "Real Estate & Housing",
           ("real estate", "realtor", "property management", "mortgage", "reit", "leasing", "appraisal",
            "home builder", "homebuilder", "escrow", "facilities", "data center"),
           ("PLD", "AMT", "O", "EQIX", "DHI"), "VNQ",
           "Rate-sensitive; REITs pay you to wait while the real assets compound."),
    Domain("telecom_networking", "Telecom & Networking",
           ("telecom", "wireless", "5g", "network engineer", "networking", "cisco", "fiber", "ccna", "rf",
            "cable", "broadband"),
           ("TMUS", "CSCO", "VZ", "ANET"), "IYZ",
           "Utilities of the internet age; T-Mobile and Arista show what good execution looks like."),
)

DOMAIN_BY_KEY = {d.key: d for d in DOMAINS}


def _t(sym, name, domain, aliases=(), **kw) -> TickerInfo:
    return TickerInfo(sym, name, domain, tuple(aliases), **kw)


# Illustrative fundamentals: rounded approximations for demo/mock mode only.
TICKERS: tuple[TickerInfo, ...] = (
    # Software & Cloud
    _t("MSFT", "Microsoft", "software_cloud", ("microsoft", "azure", "linkedin", "github", "xbox"), price=430, vol=0.24, roic=0.30, gross_margin=0.69, op_margin=0.44, op_margin_stdev=0.03, fcf_margin=0.30, debt_to_equity=0.3, rev_growth=0.14, share_change=-0.005, pe=34),
    _t("CRM", "Salesforce", "software_cloud", ("salesforce", "slack", "tableau"), price=280, vol=0.32, roic=0.10, gross_margin=0.77, op_margin=0.19, op_margin_stdev=0.07, fcf_margin=0.31, debt_to_equity=0.2, rev_growth=0.09, share_change=-0.01, pe=30),
    _t("ADBE", "Adobe", "software_cloud", ("adobe", "photoshop", "figma"), price=420, vol=0.32, roic=0.32, gross_margin=0.89, op_margin=0.36, op_margin_stdev=0.02, fcf_margin=0.37, debt_to_equity=0.4, rev_growth=0.10, share_change=-0.03, pe=24),
    _t("ORCL", "Oracle", "software_cloud", ("oracle", "netsuite", "cerner"), price=190, vol=0.36, roic=0.14, gross_margin=0.71, op_margin=0.31, op_margin_stdev=0.03, fcf_margin=0.10, debt_to_equity=4.0, rev_growth=0.10, share_change=0.0, pe=36),
    _t("NOW", "ServiceNow", "software_cloud", ("servicenow",), price=900, vol=0.34, roic=0.15, gross_margin=0.79, op_margin=0.12, op_margin_stdev=0.04, fcf_margin=0.32, debt_to_equity=0.2, rev_growth=0.21, share_change=0.005, pe=60),
    _t("INTU", "Intuit", "software_cloud", ("intuit", "turbotax", "quickbooks", "credit karma", "mailchimp"), price=640, vol=0.30, roic=0.15, gross_margin=0.79, op_margin=0.24, op_margin_stdev=0.03, fcf_margin=0.29, debt_to_equity=0.3, rev_growth=0.13, share_change=-0.005, pe=36),
    # AI & Semis
    _t("NVDA", "NVIDIA", "ai_semis", ("nvidia",), price=180, vol=0.48, roic=0.70, gross_margin=0.75, op_margin=0.62, op_margin_stdev=0.15, fcf_margin=0.45, debt_to_equity=0.1, rev_growth=0.60, share_change=-0.005, pe=45),
    _t("AVGO", "Broadcom", "ai_semis", ("broadcom", "vmware"), price=330, vol=0.42, roic=0.14, gross_margin=0.77, op_margin=0.35, op_margin_stdev=0.06, fcf_margin=0.40, debt_to_equity=0.9, rev_growth=0.25, share_change=0.02, pe=40),
    _t("TSM", "Taiwan Semiconductor", "ai_semis", ("tsmc", "taiwan semiconductor"), price=280, vol=0.36, roic=0.28, gross_margin=0.58, op_margin=0.47, op_margin_stdev=0.04, fcf_margin=0.32, debt_to_equity=0.2, rev_growth=0.30, share_change=0.0, pe=25),
    _t("ASML", "ASML", "ai_semis", ("asml",), price=950, vol=0.36, roic=0.35, gross_margin=0.52, op_margin=0.34, op_margin_stdev=0.03, fcf_margin=0.25, debt_to_equity=0.2, rev_growth=0.12, share_change=-0.01, pe=32),
    _t("AMD", "AMD", "ai_semis", ("amd", "advanced micro devices", "xilinx"), price=230, vol=0.52, roic=0.05, gross_margin=0.52, op_margin=0.10, op_margin_stdev=0.08, fcf_margin=0.12, debt_to_equity=0.05, rev_growth=0.25, share_change=0.0, pe=45),
    _t("QCOM", "Qualcomm", "ai_semis", ("qualcomm", "snapdragon"), price=165, vol=0.36, roic=0.25, gross_margin=0.56, op_margin=0.28, op_margin_stdev=0.05, fcf_margin=0.28, debt_to_equity=0.6, rev_growth=0.08, share_change=-0.02, pe=16),
    # Cybersecurity
    _t("PANW", "Palo Alto Networks", "cybersecurity", ("palo alto networks", "palo alto"), price=200, vol=0.36, roic=0.10, gross_margin=0.74, op_margin=0.13, op_margin_stdev=0.04, fcf_margin=0.38, debt_to_equity=0.1, rev_growth=0.15, share_change=0.01, pe=50),
    _t("CRWD", "CrowdStrike", "cybersecurity", ("crowdstrike", "falcon"), price=480, vol=0.48, roic=0.01, gross_margin=0.75, op_margin=0.01, op_margin_stdev=0.05, fcf_margin=0.27, debt_to_equity=0.2, rev_growth=0.22, share_change=0.02, pe=110),
    _t("FTNT", "Fortinet", "cybersecurity", ("fortinet", "fortigate"), price=85, vol=0.40, roic=0.40, gross_margin=0.80, op_margin=0.30, op_margin_stdev=0.04, fcf_margin=0.33, debt_to_equity=0.3, rev_growth=0.13, share_change=-0.01, pe=34),
    _t("ZS", "Zscaler", "cybersecurity", ("zscaler",), price=290, vol=0.50, roic=0.0, gross_margin=0.78, op_margin=-0.02, op_margin_stdev=0.04, fcf_margin=0.27, debt_to_equity=1.0, rev_growth=0.23, share_change=0.02, pe=90),
    _t("NET", "Cloudflare", "cybersecurity", ("cloudflare",), price=200, vol=0.58, roic=-0.03, gross_margin=0.77, op_margin=-0.07, op_margin_stdev=0.04, fcf_margin=0.10, debt_to_equity=1.3, rev_growth=0.27, share_change=0.02, pe=200),
    # Internet & consumer tech
    _t("AAPL", "Apple", "internet_consumer", ("apple", "iphone", "ipad", "macbook", "airpods", "app store"), price=250, vol=0.26, roic=0.55, gross_margin=0.46, op_margin=0.31, op_margin_stdev=0.02, fcf_margin=0.26, debt_to_equity=1.5, rev_growth=0.05, share_change=-0.03, pe=33),
    _t("AMZN", "Amazon", "internet_consumer", ("amazon", "aws", "whole foods", "prime video", "kindle", "alexa"), price=225, vol=0.32, roic=0.16, gross_margin=0.49, op_margin=0.11, op_margin_stdev=0.04, fcf_margin=0.05, debt_to_equity=0.4, rev_growth=0.11, share_change=0.01, pe=36),
    _t("GOOGL", "Alphabet", "internet_consumer", ("google", "alphabet", "youtube", "android", "waymo", "gmail"), price=250, vol=0.30, roic=0.28, gross_margin=0.58, op_margin=0.32, op_margin_stdev=0.03, fcf_margin=0.20, debt_to_equity=0.1, rev_growth=0.13, share_change=-0.02, pe=25),
    _t("META", "Meta Platforms", "internet_consumer", ("meta platforms", "facebook", "instagram", "whatsapp", "oculus"), price=720, vol=0.36, roic=0.30, gross_margin=0.81, op_margin=0.42, op_margin_stdev=0.07, fcf_margin=0.29, debt_to_equity=0.3, rev_growth=0.20, share_change=-0.02, pe=27),
    _t("UBER", "Uber", "internet_consumer", ("uber", "uber eats"), price=95, vol=0.40, roic=0.10, gross_margin=0.39, op_margin=0.10, op_margin_stdev=0.06, fcf_margin=0.17, debt_to_equity=0.4, rev_growth=0.18, share_change=0.0, pe=16),
    _t("BKNG", "Booking Holdings", "internet_consumer", ("booking.com", "priceline", "kayak", "opentable"), price=5300, vol=0.28, roic=0.45, gross_margin=0.85, op_margin=0.33, op_margin_stdev=0.04, fcf_margin=0.33, debt_to_equity=-5.0, rev_growth=0.10, share_change=-0.05, pe=30),
    # Payments
    _t("V", "Visa", "payments_fintech", ("visa",), price=345, vol=0.20, roic=0.38, gross_margin=0.80, op_margin=0.67, op_margin_stdev=0.01, fcf_margin=0.55, debt_to_equity=0.5, rev_growth=0.10, share_change=-0.02, pe=31),
    _t("MA", "Mastercard", "payments_fintech", ("mastercard",), price=570, vol=0.21, roic=0.48, gross_margin=0.77, op_margin=0.58, op_margin_stdev=0.02, fcf_margin=0.50, debt_to_equity=2.5, rev_growth=0.12, share_change=-0.02, pe=36),
    _t("AXP", "American Express", "payments_fintech", ("american express", "amex"), price=330, vol=0.26, roic=0.13, gross_margin=0.60, op_margin=0.20, op_margin_stdev=0.03, fcf_margin=0.18, debt_to_equity=1.7, rev_growth=0.09, share_change=-0.03, pe=22),
    _t("PYPL", "PayPal", "payments_fintech", ("paypal", "venmo", "braintree"), price=70, vol=0.38, roic=0.13, gross_margin=0.46, op_margin=0.18, op_margin_stdev=0.03, fcf_margin=0.18, debt_to_equity=0.5, rev_growth=0.05, share_change=-0.06, pe=14),
    _t("FI", "Fiserv", "payments_fintech", ("fiserv", "clover"), price=130, vol=0.34, roic=0.08, gross_margin=0.60, op_margin=0.30, op_margin_stdev=0.03, fcf_margin=0.24, debt_to_equity=1.0, rev_growth=0.05, share_change=-0.04, pe=13),
    # Banks / finance
    _t("BRK.B", "Berkshire Hathaway", "banks_finance", ("berkshire", "geico", "bnsf"), price=490, vol=0.17, roic=0.10, gross_margin=0.30, op_margin=0.15, op_margin_stdev=0.04, fcf_margin=0.10, debt_to_equity=0.2, rev_growth=0.05, share_change=-0.005, pe=22),
    _t("JPM", "JPMorgan Chase", "banks_finance", ("jpmorgan", "jp morgan", "chase bank", "jpmorgan chase"), price=300, vol=0.24, roic=0.17, gross_margin=0.60, op_margin=0.38, op_margin_stdev=0.03, fcf_margin=0.20, debt_to_equity=1.3, rev_growth=0.06, share_change=-0.02, pe=15),
    _t("BLK", "BlackRock", "banks_finance", ("blackrock", "ishares"), price=1100, vol=0.24, roic=0.12, gross_margin=0.50, op_margin=0.37, op_margin_stdev=0.02, fcf_margin=0.25, debt_to_equity=0.3, rev_growth=0.12, share_change=0.02, pe=26),
    _t("SCHW", "Charles Schwab", "banks_finance", ("schwab", "charles schwab", "td ameritrade"), price=95, vol=0.30, roic=0.12, gross_margin=0.60, op_margin=0.45, op_margin_stdev=0.05, fcf_margin=0.20, debt_to_equity=0.8, rev_growth=0.15, share_change=-0.02, pe=20),
    _t("PGR", "Progressive", "banks_finance", ("progressive insurance",), price=250, vol=0.26, roic=0.30, gross_margin=0.20, op_margin=0.13, op_margin_stdev=0.04, fcf_margin=0.20, debt_to_equity=0.3, rev_growth=0.15, share_change=0.0, pe=15),
    _t("GS", "Goldman Sachs", "banks_finance", ("goldman sachs", "goldman"), price=780, vol=0.28, roic=0.12, gross_margin=0.50, op_margin=0.30, op_margin_stdev=0.06, fcf_margin=0.10, debt_to_equity=2.5, rev_growth=0.10, share_change=-0.03, pe=16),
    # Healthcare
    _t("UNH", "UnitedHealth", "healthcare", ("unitedhealth", "united healthcare", "optum"), price=340, vol=0.38, roic=0.12, gross_margin=0.20, op_margin=0.05, op_margin_stdev=0.02, fcf_margin=0.05, debt_to_equity=0.8, rev_growth=0.08, share_change=-0.01, pe=17),
    _t("ISRG", "Intuitive Surgical", "healthcare", ("intuitive surgical", "da vinci"), price=520, vol=0.30, roic=0.18, gross_margin=0.66, op_margin=0.29, op_margin_stdev=0.03, fcf_margin=0.25, debt_to_equity=0.0, rev_growth=0.18, share_change=0.0, pe=70),
    _t("ABT", "Abbott Laboratories", "healthcare", ("abbott", "freestyle libre"), price=130, vol=0.20, roic=0.12, gross_margin=0.56, op_margin=0.18, op_margin_stdev=0.02, fcf_margin=0.18, debt_to_equity=0.3, rev_growth=0.07, share_change=-0.005, pe=24),
    _t("SYK", "Stryker", "healthcare", ("stryker",), price=380, vol=0.22, roic=0.10, gross_margin=0.64, op_margin=0.24, op_margin_stdev=0.02, fcf_margin=0.17, debt_to_equity=0.6, rev_growth=0.10, share_change=0.005, pe=30),
    _t("HCA", "HCA Healthcare", "healthcare", ("hca",), price=420, vol=0.28, roic=0.16, gross_margin=0.40, op_margin=0.15, op_margin_stdev=0.02, fcf_margin=0.07, debt_to_equity=-20.0, rev_growth=0.07, share_change=-0.06, pe=17),
    _t("JNJ", "Johnson & Johnson", "healthcare", ("johnson & johnson", "j&j", "tylenol"), price=190, vol=0.18, roic=0.15, gross_margin=0.69, op_margin=0.25, op_margin_stdev=0.02, fcf_margin=0.20, debt_to_equity=0.5, rev_growth=0.05, share_change=-0.005, pe=17),
    # Pharma / biotech
    _t("LLY", "Eli Lilly", "biotech_pharma", ("eli lilly", "lilly", "mounjaro", "zepbound"), price=820, vol=0.34, roic=0.30, gross_margin=0.82, op_margin=0.40, op_margin_stdev=0.06, fcf_margin=0.15, debt_to_equity=2.0, rev_growth=0.35, share_change=0.0, pe=45),
    _t("ABBV", "AbbVie", "biotech_pharma", ("abbvie", "humira", "skyrizi", "botox"), price=220, vol=0.24, roic=0.12, gross_margin=0.70, op_margin=0.30, op_margin_stdev=0.06, fcf_margin=0.32, debt_to_equity=20.0, rev_growth=0.06, share_change=0.0, pe=19),
    _t("MRK", "Merck", "biotech_pharma", ("merck", "keytruda"), price=88, vol=0.24, roic=0.20, gross_margin=0.78, op_margin=0.35, op_margin_stdev=0.08, fcf_margin=0.27, debt_to_equity=0.7, rev_growth=0.03, share_change=-0.005, pe=10),
    _t("VRTX", "Vertex Pharmaceuticals", "biotech_pharma", ("vertex pharmaceuticals",), price=430, vol=0.28, roic=0.20, gross_margin=0.86, op_margin=0.38, op_margin_stdev=0.10, fcf_margin=0.30, debt_to_equity=0.1, rev_growth=0.10, share_change=0.0, pe=27),
    _t("AMGN", "Amgen", "biotech_pharma", ("amgen",), price=290, vol=0.24, roic=0.12, gross_margin=0.70, op_margin=0.28, op_margin_stdev=0.05, fcf_margin=0.30, debt_to_equity=7.0, rev_growth=0.08, share_change=0.0, pe=14),
    _t("TMO", "Thermo Fisher", "biotech_pharma", ("thermo fisher", "fisher scientific"), price=520, vol=0.26, roic=0.09, gross_margin=0.41, op_margin=0.18, op_margin_stdev=0.03, fcf_margin=0.16, debt_to_equity=0.7, rev_growth=0.04, share_change=-0.01, pe=23),
    # Retail
    _t("COST", "Costco", "retail_consumer", ("costco", "kirkland"), price=920, vol=0.20, roic=0.22, gross_margin=0.13, op_margin=0.037, op_margin_stdev=0.002, fcf_margin=0.03, debt_to_equity=0.3, rev_growth=0.07, share_change=0.0, pe=50),
    _t("WMT", "Walmart", "retail_consumer", ("walmart", "sam's club", "sams club"), price=100, vol=0.20, roic=0.14, gross_margin=0.25, op_margin=0.042, op_margin_stdev=0.004, fcf_margin=0.02, debt_to_equity=0.5, rev_growth=0.05, share_change=-0.005, pe=38),
    _t("HD", "Home Depot", "retail_consumer", ("home depot",), price=390, vol=0.22, roic=0.30, gross_margin=0.33, op_margin=0.13, op_margin_stdev=0.01, fcf_margin=0.10, debt_to_equity=8.0, rev_growth=0.03, share_change=-0.005, pe=26),
    _t("NKE", "Nike", "retail_consumer", ("nike", "jordan brand", "converse"), price=70, vol=0.36, roic=0.12, gross_margin=0.42, op_margin=0.08, op_margin_stdev=0.03, fcf_margin=0.06, debt_to_equity=0.8, rev_growth=-0.05, share_change=-0.01, pe=30),
    _t("TJX", "TJX Companies", "retail_consumer", ("tj maxx", "tjx", "marshalls", "homegoods"), price=140, vol=0.20, roic=0.25, gross_margin=0.30, op_margin=0.11, op_margin_stdev=0.01, fcf_margin=0.07, debt_to_equity=0.4, rev_growth=0.05, share_change=-0.02, pe=31),
    _t("LULU", "Lululemon", "retail_consumer", ("lululemon",), price=180, vol=0.46, roic=0.30, gross_margin=0.58, op_margin=0.22, op_margin_stdev=0.02, fcf_margin=0.12, debt_to_equity=0.0, rev_growth=0.04, share_change=-0.03, pe=12),
    # Restaurants / food
    _t("MCD", "McDonald's", "restaurants_food", ("mcdonald's", "mcdonalds"), price=300, vol=0.18, roic=0.18, gross_margin=0.57, op_margin=0.45, op_margin_stdev=0.02, fcf_margin=0.27, debt_to_equity=-12.0, rev_growth=0.03, share_change=-0.01, pe=26),
    _t("CMG", "Chipotle", "restaurants_food", ("chipotle",), price=42, vol=0.36, roic=0.25, gross_margin=0.27, op_margin=0.17, op_margin_stdev=0.02, fcf_margin=0.13, debt_to_equity=0.0, rev_growth=0.08, share_change=-0.01, pe=36),
    _t("SBUX", "Starbucks", "restaurants_food", ("starbucks",), price=85, vol=0.32, roic=0.12, gross_margin=0.25, op_margin=0.10, op_margin_stdev=0.03, fcf_margin=0.06, debt_to_equity=-3.0, rev_growth=0.01, share_change=0.0, pe=35),
    _t("KO", "Coca-Cola", "restaurants_food", ("coca-cola", "coca cola", "coke", "sprite", "dasani"), price=68, vol=0.16, roic=0.18, gross_margin=0.61, op_margin=0.30, op_margin_stdev=0.02, fcf_margin=0.20, debt_to_equity=1.5, rev_growth=0.04, share_change=0.0, pe=24),
    _t("PEP", "PepsiCo", "restaurants_food", ("pepsi", "pepsico", "frito-lay", "gatorade"), price=145, vol=0.18, roic=0.14, gross_margin=0.54, op_margin=0.14, op_margin_stdev=0.02, fcf_margin=0.08, debt_to_equity=2.4, rev_growth=0.01, share_change=0.0, pe=20),
    _t("YUM", "Yum! Brands", "restaurants_food", ("taco bell", "kfc", "pizza hut", "yum brands"), price=150, vol=0.20, roic=0.40, gross_margin=0.47, op_margin=0.32, op_margin_stdev=0.02, fcf_margin=0.20, debt_to_equity=-1.5, rev_growth=0.06, share_change=-0.01, pe=28),
    # Energy
    _t("XOM", "ExxonMobil", "energy", ("exxon", "exxonmobil", "mobil"), price=115, vol=0.24, roic=0.12, gross_margin=0.30, op_margin=0.12, op_margin_stdev=0.05, fcf_margin=0.09, debt_to_equity=0.15, rev_growth=-0.02, share_change=0.05, pe=15),
    _t("CVX", "Chevron", "energy", ("chevron", "texaco", "hess"), price=155, vol=0.24, roic=0.10, gross_margin=0.30, op_margin=0.11, op_margin_stdev=0.05, fcf_margin=0.08, debt_to_equity=0.2, rev_growth=-0.02, share_change=0.02, pe=17),
    _t("NEE", "NextEra Energy", "energy", ("nextera", "florida power & light", "fpl"), price=75, vol=0.26, roic=0.05, gross_margin=0.60, op_margin=0.30, op_margin_stdev=0.04, fcf_margin=0.05, debt_to_equity=1.6, rev_growth=0.05, share_change=0.01, pe=22),
    _t("COP", "ConocoPhillips", "energy", ("conocophillips", "conoco"), price=95, vol=0.30, roic=0.13, gross_margin=0.40, op_margin=0.22, op_margin_stdev=0.08, fcf_margin=0.14, debt_to_equity=0.35, rev_growth=0.0, share_change=0.02, pe=13),
    _t("FSLR", "First Solar", "energy", ("first solar",), price=200, vol=0.55, roic=0.12, gross_margin=0.42, op_margin=0.33, op_margin_stdev=0.12, fcf_margin=-0.05, debt_to_equity=0.05, rev_growth=0.20, share_change=0.0, pe=16),
    _t("VST", "Vistra", "energy", ("vistra",), price=190, vol=0.55, roic=0.10, gross_margin=0.30, op_margin=0.18, op_margin_stdev=0.10, fcf_margin=0.10, debt_to_equity=4.0, rev_growth=0.10, share_change=-0.04, pe=30),
    # Industrials
    _t("CAT", "Caterpillar", "industrials_aero", ("caterpillar",), price=470, vol=0.28, roic=0.24, gross_margin=0.35, op_margin=0.20, op_margin_stdev=0.03, fcf_margin=0.14, debt_to_equity=1.9, rev_growth=-0.02, share_change=-0.03, pe=22),
    _t("DE", "Deere & Co", "industrials_aero", ("john deere", "deere"), price=480, vol=0.26, roic=0.12, gross_margin=0.36, op_margin=0.18, op_margin_stdev=0.04, fcf_margin=0.10, debt_to_equity=2.9, rev_growth=-0.10, share_change=-0.02, pe=24),
    _t("HON", "Honeywell", "industrials_aero", ("honeywell",), price=215, vol=0.22, roic=0.14, gross_margin=0.38, op_margin=0.20, op_margin_stdev=0.02, fcf_margin=0.14, debt_to_equity=1.7, rev_growth=0.05, share_change=-0.01, pe=24),
    _t("GE", "GE Aerospace", "industrials_aero", ("general electric", "ge aerospace", "ge aviation"), price=290, vol=0.30, roic=0.14, gross_margin=0.37, op_margin=0.20, op_margin_stdev=0.05, fcf_margin=0.17, debt_to_equity=1.0, rev_growth=0.15, share_change=-0.02, pe=45),
    _t("LMT", "Lockheed Martin", "industrials_aero", ("lockheed", "lockheed martin"), price=480, vol=0.22, roic=0.20, gross_margin=0.11, op_margin=0.10, op_margin_stdev=0.02, fcf_margin=0.07, debt_to_equity=3.5, rev_growth=0.03, share_change=-0.03, pe=20),
    _t("RTX", "RTX (Raytheon)", "industrials_aero", ("raytheon", "rtx", "pratt & whitney", "collins aerospace"), price=160, vol=0.22, roic=0.08, gross_margin=0.20, op_margin=0.11, op_margin_stdev=0.04, fcf_margin=0.06, debt_to_equity=0.6, rev_growth=0.08, share_change=-0.01, pe=30),
    # Autos
    _t("TSLA", "Tesla", "autos_ev", ("tesla",), price=430, vol=0.60, roic=0.06, gross_margin=0.17, op_margin=0.06, op_margin_stdev=0.05, fcf_margin=0.04, debt_to_equity=0.1, rev_growth=-0.02, share_change=0.01, pe=200),
    _t("TM", "Toyota", "autos_ev", ("toyota", "lexus"), price=195, vol=0.26, roic=0.07, gross_margin=0.20, op_margin=0.10, op_margin_stdev=0.03, fcf_margin=0.03, debt_to_equity=1.0, rev_growth=0.05, share_change=-0.02, pe=9),
    _t("GM", "General Motors", "autos_ev", ("general motors", "chevrolet", "gmc", "cadillac", "cruise"), price=58, vol=0.34, roic=0.06, gross_margin=0.12, op_margin=0.07, op_margin_stdev=0.03, fcf_margin=0.06, debt_to_equity=1.8, rev_growth=0.02, share_change=-0.12, pe=7),
    _t("F", "Ford", "autos_ev", ("ford motor", "ford motor company"), price=11, vol=0.34, roic=0.04, gross_margin=0.10, op_margin=0.03, op_margin_stdev=0.03, fcf_margin=0.04, debt_to_equity=3.5, rev_growth=0.02, share_change=0.0, pe=12),
    # Transport
    _t("UNP", "Union Pacific", "transport_logistics", ("union pacific",), price=230, vol=0.22, roic=0.15, gross_margin=0.55, op_margin=0.40, op_margin_stdev=0.02, fcf_margin=0.20, debt_to_equity=2.0, rev_growth=0.02, share_change=-0.01, pe=20),
    _t("ODFL", "Old Dominion Freight", "transport_logistics", ("old dominion",), price=150, vol=0.34, roic=0.25, gross_margin=0.30, op_margin=0.25, op_margin_stdev=0.03, fcf_margin=0.14, debt_to_equity=0.0, rev_growth=-0.05, share_change=-0.02, pe=30),
    _t("UPS", "UPS", "transport_logistics", ("united parcel service",), price=90, vol=0.30, roic=0.12, gross_margin=0.20, op_margin=0.08, op_margin_stdev=0.02, fcf_margin=0.06, debt_to_equity=1.6, rev_growth=-0.02, share_change=0.0, pe=13),
    _t("FDX", "FedEx", "transport_logistics", ("fedex",), price=240, vol=0.30, roic=0.08, gross_margin=0.25, op_margin=0.07, op_margin_stdev=0.01, fcf_margin=0.05, debt_to_equity=1.3, rev_growth=0.0, share_change=-0.02, pe=14),
    _t("DAL", "Delta Air Lines", "transport_logistics", ("delta air lines", "delta airlines"), price=58, vol=0.40, roic=0.10, gross_margin=0.25, op_margin=0.10, op_margin_stdev=0.05, fcf_margin=0.05, debt_to_equity=1.2, rev_growth=0.03, share_change=0.0, pe=8),
    # Media
    _t("NFLX", "Netflix", "media_gaming", ("netflix",), price=1150, vol=0.34, roic=0.25, gross_margin=0.48, op_margin=0.29, op_margin_stdev=0.04, fcf_margin=0.20, debt_to_equity=0.6, rev_growth=0.15, share_change=-0.01, pe=45),
    _t("DIS", "Walt Disney", "media_gaming", ("disney", "espn", "hulu", "pixar", "marvel"), price=112, vol=0.28, roic=0.07, gross_margin=0.36, op_margin=0.14, op_margin_stdev=0.04, fcf_margin=0.10, debt_to_equity=0.4, rev_growth=0.04, share_change=-0.01, pe=18),
    _t("SPOT", "Spotify", "media_gaming", ("spotify",), price=680, vol=0.42, roic=0.15, gross_margin=0.31, op_margin=0.11, op_margin_stdev=0.05, fcf_margin=0.17, debt_to_equity=0.0, rev_growth=0.16, share_change=0.01, pe=80),
    _t("TTWO", "Take-Two Interactive", "media_gaming", ("take-two", "rockstar", "grand theft auto", "gta", "2k"), price=240, vol=0.32, roic=-0.05, gross_margin=0.55, op_margin=-0.05, op_margin_stdev=0.10, fcf_margin=0.0, debt_to_equity=0.6, rev_growth=0.10, share_change=0.03, pe=60),
    _t("EA", "Electronic Arts", "media_gaming", ("electronic arts", "ea sports", "madden", "fifa"), price=200, vol=0.22, roic=0.18, gross_margin=0.78, op_margin=0.20, op_margin_stdev=0.03, fcf_margin=0.27, debt_to_equity=0.2, rev_growth=0.03, share_change=-0.02, pe=40),
    _t("RBLX", "Roblox", "media_gaming", ("roblox",), price=120, vol=0.55, roic=-0.30, gross_margin=0.78, op_margin=-0.20, op_margin_stdev=0.05, fcf_margin=0.20, debt_to_equity=4.0, rev_growth=0.30, share_change=0.03, pe=-1),
    # Real estate
    _t("PLD", "Prologis", "real_estate", ("prologis",), price=115, vol=0.26, roic=0.05, gross_margin=0.75, op_margin=0.40, op_margin_stdev=0.04, fcf_margin=0.45, debt_to_equity=0.6, rev_growth=0.07, share_change=0.01, pe=30),
    _t("AMT", "American Tower", "real_estate", ("american tower",), price=200, vol=0.26, roic=0.07, gross_margin=0.73, op_margin=0.43, op_margin_stdev=0.03, fcf_margin=0.35, debt_to_equity=10.0, rev_growth=0.03, share_change=0.0, pe=40),
    _t("O", "Realty Income", "real_estate", ("realty income",), price=58, vol=0.20, roic=0.04, gross_margin=0.92, op_margin=0.45, op_margin_stdev=0.03, fcf_margin=0.60, debt_to_equity=0.7, rev_growth=0.08, share_change=0.08, pe=55),
    _t("EQIX", "Equinix", "real_estate", ("equinix",), price=850, vol=0.28, roic=0.06, gross_margin=0.48, op_margin=0.20, op_margin_stdev=0.02, fcf_margin=0.20, debt_to_equity=1.4, rev_growth=0.07, share_change=0.02, pe=80),
    _t("DHI", "D.R. Horton", "real_estate", ("d.r. horton", "dr horton"), price=165, vol=0.36, roic=0.15, gross_margin=0.23, op_margin=0.15, op_margin_stdev=0.04, fcf_margin=0.08, debt_to_equity=0.2, rev_growth=-0.05, share_change=-0.04, pe=13),
    # Telecom
    _t("TMUS", "T-Mobile US", "telecom_networking", ("t-mobile", "tmobile", "sprint"), price=240, vol=0.22, roic=0.09, gross_margin=0.63, op_margin=0.23, op_margin_stdev=0.03, fcf_margin=0.20, debt_to_equity=1.7, rev_growth=0.05, share_change=-0.03, pe=22),
    _t("CSCO", "Cisco", "telecom_networking", ("cisco", "webex", "splunk", "meraki"), price=68, vol=0.22, roic=0.15, gross_margin=0.64, op_margin=0.23, op_margin_stdev=0.03, fcf_margin=0.24, debt_to_equity=0.6, rev_growth=0.06, share_change=-0.01, pe=26),
    _t("VZ", "Verizon", "telecom_networking", ("verizon",), price=42, vol=0.20, roic=0.07, gross_margin=0.60, op_margin=0.22, op_margin_stdev=0.03, fcf_margin=0.14, debt_to_equity=1.6, rev_growth=0.01, share_change=0.0, pe=10),
    _t("ANET", "Arista Networks", "telecom_networking", ("arista",), price=140, vol=0.50, roic=0.35, gross_margin=0.64, op_margin=0.42, op_margin_stdev=0.04, fcf_margin=0.45, debt_to_equity=0.0, rev_growth=0.25, share_change=0.0, pe=50),
)

TICKER_BY_SYMBOL = {t.symbol: t for t in TICKERS}


def tickers_for_domain(domain_key: str) -> list[TickerInfo]:
    return [t for t in TICKERS if t.domain == domain_key]


def lookup(symbol: str) -> TickerInfo | None:
    return TICKER_BY_SYMBOL.get(symbol.upper().replace("-", ".").replace("/", "."))
