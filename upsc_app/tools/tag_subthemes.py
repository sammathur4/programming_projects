#!/usr/bin/env python3
"""
tag_subthemes.py — fills the empty `sub_theme` column in the mains question bank.

Why: 29 master themes, each asked in every one of 14 years, so recurrence at that
level predicts nothing. The repeating unit is one level down.

Dispatch is by **paper**, not by master_theme, because paper is the one label that
comes from the exam itself. It had to be: master_theme is wrong for a large block
of GS1 rows (43 GS1 rows are tagged "Science & Technology", 36 "International
Relations"). `suspected_master_theme.csv` lists every impossible pair.

Label sources, in order:
  1. sociology papers  -> the existing `subject` column (28 clean values)
  2. nature=="Case Study" -> "Case Study"
  3. the RULES table for that paper (first match wins, specific before general)
  4. "General <paper>"  -> counted and printed, never hidden

Writes (never edits the source CSV):
  strategy/qbank/mains_subthemed.csv
  strategy/qbank/subtheme_recurrence.csv
  strategy/qbank/suspected_master_theme.csv
  strategy/qbank/subtheme_coverage.txt

Run:  .venv/bin/python upsc_app/tools/tag_subthemes.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "final_pyq_data" / "UPSC IAS PYQs - mains_2013_2026_corrected.csv"
PRELIMS_CSV = Path(__file__).resolve().parents[2] / "data" / "final_pyq_data" / "UPSC IAS PYQs - prelims_2013_2026.csv"
OUT = Path(__file__).resolve().parents[1] / "strategy" / "qbank"

CASE_STUDY = r"\bcase\b|you are (a|an)|you have been appointed|your (friend|colleague|subordinate|neighbour)|situation.*you|an? (officer|ceo|collector|secretary) "

RULES: dict[str, list[tuple[str, str]]] = {}

# ---------------------------------------------------------------- GS1
RULES["gs1"] = [
    ("Freedom Struggle & National Movement",
     r"freedom struggle|national movement|non.cooperation|civil disobedience|quit india|swaraj|revolutionar|colonial|british|mutiny|partition|indian national congress|home rule|khilafat|gandhi.{0,40}(movement|satyagraha|harijan)|rowlatt|dandi|dalhousie|governor general|subhash chandra bose|moderates|extremists|ambedkar|independence"),
    ("Socio-Religious Reform Movements",
     r"reform movement|brahmo|arya samaj|ramakrishna|vivekananda|social reform|\bsati\b|widow remarri|aligarh|theosoph|young bengal"),
    ("Ancient & Medieval India",
     r"harappan|indus valley|vedic|maurya|gupta empire|ashoka|buddhis|jainis|sangam|mughal|sultanate|chola|vijayanagar|bhakti|sufi|medieval|ancient india|pali|punch.marked|battle of|panipat|taxila|nagar|ayodhya|numismatic|gandhara|dynasty|empire|traveller|inscription|coin"),
    ("World History",
     r"french revolution|american revolution|industrial revolution|world war|renaissance|cold war|imperialism|suez|russian revolution|lenin|colonialism|bipolar|non.aligned|economic depression|mercantilism|africa was|european competition|decolonis|decoloniz|malay peninsula"),
    ("Post-Independence India",
     r"post.independen|integration of|linguistic reorganisation|five year plan|emergency 1975|tashkent|jai jawan|jai kisan|slogan|constituent assembly|linguistic state|new state|aspirational district"),
    ("Art, Architecture & Culture",
     r"architect|temple|sculpture|painting|mural|shikhara|stupa|rock.cut|dance|music|raga|theatre|literature|poet|inscription|heritage|monument|cultural element|art form|numismatic|gandhara|sculpture"),
    ("Physical Geography & Geomorphology",
     r"plate tectonic|continental drift|earthquake|volcan|glacier|erosion|mountain|landform|sediment|fold|island|ocean current|river system|physiograph|rock|mineral|desert|landslide|latitude|western ghat|salinity|circum.pacific|geophysical|water stress|flood|earth"),
    ("Climatology & Monsoon",
     r"monsoon|cyclone|rainfall|el nino|la nina|jet stream|weather|temperature|climatic|climate"),
    ("Oceanography & Coasts",
     r"\bocean\b|coast|tide|sea level|coral|mangrove|tsunami|arctic|sea\b|salinity|dead zone|marine"),
    ("Resources, Agriculture & Industry Location",
     r"resource|mining|soil|crop|irrigation|industry|green revolution|tea garden|plantation|industrial corridor|blue revolution|pisciculture|pulses|cultivation|iron and steel"),
    ("Population, Urbanisation & Migration",
     r"population|urbaniz|urbanis|migration|census|settlement|demograph|urban|slum"),
    ("Caste & Stratification", r"caste|dalit|untouchab|stratification"),
    ("Women & Gender", r"women|gender|patriarch|femin|sex ratio|female"),
    ("Family, Marriage & Kinship", r"family|marriage|kinship|divorce|joint family"),
    ("Globalisation & Social Change", r"globalis|globaliz|liberalis|social change|modernis|moderniz|global identity|local identity"),
    ("Social Movements, Diversity & Communalism", r"movement|communal|regionalis|secularis|diversity|pluralis|tribal|ethnic|customs and traditions|identity"),
    ("Society & Social Structure", r"society|social structure|social institution|social norm|social mobility|inequal"),
]

# ---------------------------------------------------------------- GS2
RULES["gs2"] = [
    ("India-China", r"china|chinese|sino|south china sea"),
    ("India-Pakistan", r"pakistan|\bpok\b|\bloc\b|indus water"),
    ("India-United States", r"united states|\busa\b|\bu\.s\.|america|washington"),
    ("India & Neighbours (SAARC)", r"nepal|bangladesh|sri lanka|bhutan|myanmar|afghanistan|maldives|\bsaarc\b|neighbour"),
    ("India & Southeast Asia / Indo-Pacific", r"asean|south.east asia|southeast asia|indo.pacific|act east|look east|vietnam|indonesia|japan|korea|australia"),
    ("India & West Asia / Africa / Central Asia", r"west asia|middle east|africa|central asia|iran|israel|saudi|gulf|egypt|turkey"),
    ("UN & Multilateral Reform", r"united nation|security council|\bunsc\b|ecosoc|unesco|peacekeep|multilateral|global institution"),
    ("WTO, Trade & Economic Diplomacy", r"\bwto\b|trade agreement|\bfta\b|tariff|doha|protectionis|world trade|trade war"),
    ("Global Groupings & Institutions", r"brics|\bg20\b|\bquad\b|\bsco\b|bimstec|\bimf\b|world bank|new development bank|aiib|oecd|commonwealth"),
    ("Indian Diaspora", r"diaspora|overseas indian|pravasi|\bnri\b"),
    ("Energy Security & Strategic Resources", r"energy security|oil|gas pipeline|opec|uranium|strategic petroleum"),
    ("Maritime Security & Blue Economy", r"maritime|sea lane|\bnavy\b|piracy|indian ocean|blue economy"),
    ("Terrorism & Security Cooperation", r"terror|terroris|counter.terror|extremis|\bisis\b|radicalis"),
    ("Fundamental Rights", r"fundamental right|article (1[2-9]|2\d|3[0-5])\b|right to (equality|freedom|life|privacy|education|religion|constitutional remedies)|writ|habeas corpus|mandamus|judicial review|freedom of speech"),
    ("DPSP & Fundamental Duties", r"directive principle|article (3[6-9]|4\d|5[01])\b|fundamental dut"),
    ("Preamble & Basic Structure", r"preamble|basic structure|kesavananda|coelho|constitutional morality"),
    ("Federalism & Centre-State Relations", r"federal|centre.state|union.state|article (2[4-9]|3[56])\b|inter.state|gst council|asymmetric|harmonious construction|federal supremacy"),
    ("Parliament & Legislative Procedure", r"parliament|lok sabha|rajya sabha|joint session|ordinance|speaker|parliamentary committee|public accounts committee|estimates committee|privilege|money bill|article 10[5-9]|article 11\d"),
    ("Judiciary & Judicial Review", r"judiciar|judicial|supreme court|high court|article (12[4-9]|2[1-3]\d)\b|tribunal|collegium|\bnjac\b|chief justice"),
    ("President, Governor & Executive", r"president|governor|prime minister|cabinet|council of minister|commut|pardon|vice.president|article (5[2-9]|6\d|7\d)\b|lieutenant governor"),
    ("Constitutional & Statutory Bodies", r"\bcag\b|comptroller|election commission|finance commission|\bupsc\b|attorney.general|\bnhrc\b|\bncsc\b|\bncst\b|national commission|article (14[89]|3[12]5)\b|quasi.judicial|statutory body"),
    ("Elections & Electoral Reform", r"election|\bevm\b|voter|representation of people|constituency|electoral|anti.defection"),
    ("Political Parties & Pressure Groups", r"political part|party system|pressure group|coalition|interest group|farmers. organisation"),
    ("Local Government & Panchayati Raj", r"panchayat|local self.govern|municipal|73rd|74th|article 24[0-3]\b|gram sabha"),
    ("Constitutional Amendment", r"amendment act|article 368|one hundred"),
    ("Emergency & Union Territories", r"emergency|article 35[2-9]\b|article 360|union territory|article 239|article 370|temporary provision"),
    ("Secularism & Uniform Civil Code", r"secular|uniform civil code|article 25"),
    ("Citizenship", r"citizenship"),
    ("Civil Services & Bureaucracy", r"civil service|bureaucra|\bias\b|\bips\b|all india service|administrative reform|cadre|public administration"),
    ("Transparency, RTI & Accountability", r"\brti\b|right to information|transparenc|accountab|whistleblow|lokpal|lokayukta|grievance|integrity index"),
    ("E-Governance & Digital Governance", r"e.governance|\bict\b|digital india|digital governance|aadhaar"),
    ("Regulatory Bodies & Autonomy", r"regulator|regulatory|independent and autonomous|\btrai\b|\bsebi\b|competition commission"),
    ("NGOs, SHGs & Civil Society", r"\bngo|self.help group|\bshg\b|civil society|non.state actor|people.s participation|community participation"),
    ("Corporate Governance & Business Ethics", r"corporate governance|satyam|board of directors|business ethic|corporate social"),
    ("Government Schemes & Service Delivery", r"scheme|yojana|mission|programme|beneficiar|service delivery|citizen.s charter"),
    ("Poverty & Hunger", r"poverty|hunger|below poverty|\bbpl\b|starv|food security|nutrition"),
    ("Health & Universal Health Coverage", r"health|hospital|medical|disease|immunis|immuniz|ayushman|\bphc\b|vaccin"),
    ("Education & Skill Development", r"education|school|literacy|skill india|university|\biit|iim\b|higher education"),
    ("Women & Gender Justice", r"women|gender|female|maternal|patriarch|girl|gender budget"),
    ("SC/ST/OBC & Minorities", r"scheduled caste|scheduled tribe|dalit|adivasi|\bobc\b|backward class|minorit|reservation|vulnerable section"),
    ("Children, Elderly & Disability", r"disabilit|disabled|elderly|juvenile|transgender|child labour|child policy|child right"),
    ("Welfare Schemes, DBT & Subsidies", r"welfare|\bdbt\b|direct benefit|subsid|pension|ration|mgnrega|public distribution|social security"),
    ("Human Development & Demography", r"human development|demographic dividend|census|\bhdi\b|manpower"),
]

# ---------------------------------------------------------------- GS3
RULES["gs3"] = [
    ("Left Wing Extremism", r"left wing|naxal|maoist|\blwe\b"),
    ("Terrorism & Radicalisation", r"terror|radicalis|\bisis\b|jihad|mob violence|unlawful activities"),
    ("Border Management", r"border|illegal migration|transborder|infiltration|economic corridor|cpec"),
    ("Cyber & Non-Traditional Security", r"cyber|social media.*security|cyberspace|data security|digital armed"),
    ("Insurgency & Regional Security", r"insurgen|north.east|jammu and kashmir|kashmir|jamaat"),
    ("Defence & Security Forces", r"armed forces|\bafspa\b|\barmy\b|military|surgical strike|hot pursuit|opium"),
    ("Disaster Risk Reduction & Preparedness", r"disaster risk|\bdrr\b|preparedness|hazard|vulnerabilit|early warning|disaster"),
    ("Space Technology", r"\bspace\b|satellite|isro|chandrayaan|gaganyaan|launch vehicle|remote sensing|\bgps\b|navic|space station"),
    ("Biotechnology & Health Technology", r"biotech|genetic|\bgene\b|\bdna\b|stem cell|vaccine|clon|gm crop|crispr|antibiotic|pandemic|covid"),
    ("IT, AI & Digital Technology", r"artificial intelligence|machine learning|internet|blockchain|5g|quantum|cloud|data protection|semiconductor"),
    ("Nuclear Technology", r"nuclear|reactor|fission|fusion|thorium|atomic"),
    ("Defence Technology", r"missile|drone|\buav\b|hypersonic|radar|submarine|aircraft carrier"),
    ("Nanotechnology & Materials", r"nanotech|\bnano\b|graphene|superconduct"),
    ("Scientific Research & Institutions", r"research|scientist|laborator|bose|einstein|nobel|scientific"),
    ("IPR & Traditional Knowledge", r"intellectual property|patent|\bipr\b|traditional knowledge|\btkdl\b|geographical indication"),
    ("Climate Change & Negotiations", r"climate change|\bcop\b|unfccc|paris agreement|kyoto|carbon|emission|net zero|global warming"),
    ("Biodiversity & Wildlife Conservation", r"biodivers|wildlife|species|tiger|elephant|endangered|protected area|biosphere|ramsar|wetland"),
    ("Pollution & Waste Management", r"pollution|waste|plastic|air quality|effluent|sewage|e.waste|sand mining"),
    ("Forests & Land Use", r"forest|deforest|afforest|tree cover"),
    ("Water Resources & Rivers", r"river|water resource|groundwater|aquifer|\bdam\b|interlink|clean ganga|watershed|jal shakti|water.use"),
    ("Environmental Law & Institutions", r"environment protection act|\beia\b|environmental impact|\bngt\b|pollution control|clearance"),
    ("Renewable Energy & Transition", r"renewable|solar|wind energy|hydrogen|biofuel|clean energy|energy transition"),
    ("Agriculture, MSP & Farmers", r"agricultur|farming|farmer|\bmsp\b|minimum support|crop|irrigation|horticultur|livestock|land holding|fertilis|fertiliz|organic farm|cropping"),
    ("Food Processing & Supply Chain", r"food processing|supply chain|cold chain|mandi|\bapmc\b|procurement|warehous|processing|food grain distribution|public distribution"),
    ("Land Reform & Land Acquisition", r"land reform|land acquisition|land ceiling|tenancy|land record|landholding"),
    ("Inflation & Monetary Policy", r"inflation|monetary policy|\brbi\b|reserve bank|repo rate|\bcpi\b|\bwpi\b|deflation"),
    ("Banking & Financial Sector", r"\bbank|npa|credit|financial inclusion|insurance|capital market|micro.?finance|nbfc"),
    ("Fiscal Policy, Budget & Taxation", r"budget|fiscal|\btax\b|\bgst\b|deficit|finance bill|cess|\bcgt\b"),
    ("Industry, Manufacturing & MSME", r"manufacturing|industrial|\bmake in india|\bfactory|\bsez\b|industrial policy|\bmsme\b|special economic zone"),
    ("Infrastructure & PPP", r"infrastructure|\bppp\b|public.private|railway|airport|\bport\b|highway|urban transport|telecom"),
    ("Employment & Informal Sector", r"employment|unemploy|employability|\bjob\b|labour|informal sector|gig\b|workforce|savings rate"),
    ("Trade, FDI & External Sector", r"\bfdi\b|foreign direct|export|import|current account|balance of payment|trade deficit|currency|globalis|globaliz"),
    ("Growth, GDP & Inclusive Growth", r"\bgdp\b|growth rate|economic growth|per capita|inclusive growth|jobless growth"),
    ("Urbanisation & Smart Cities", r"urban|smart city|slum|metropol|housing|solid waste"),
    ("Social Justice & Welfare Delivery", r"welfare|social justice|vulnerable|marginalis|inequal"),
]

# ---------------------------------------------------------------- GS4
RULES["gs4"] = [
    ("Case Study", CASE_STUDY),
    ("Ethical Theories & Thinkers", r"theory|utilitarian|kant|aristotle|virtue|deontolog|consequentialis|thinker|philosoph|rawls|mill\b"),
    ("Quotations & Personalities", r"quotation|quote|personality|inspired|epitomis|exemplar|great leader"),
    ("Environmental Ethics", r"environmental ethic|animal right|ecological ethic|nature.*ethic"),
    ("Ethics in International Relations & Business", r"international relation|business ethic|corporate eth|corporate social|ngo.*fund|foreign funding"),
    ("Probity, Corruption & Conflict of Interest", r"corrupt|probity|conflict of interest|bribe|scam|nepotism|whistle"),
    ("Emotional Intelligence & Attitude", r"emotional intelligence|attitude|aptitude|motivation|empathy|compassion|anger|emotion|stress|fear|greed"),
    ("Values in Public Service", r"public service|public servant|civil servant|integrity|objectivity|impartiality|neutrality|public administration|governance|patriotism|discipline|transparency|accountability"),
    ("Codes, Laws & Institutional Ethics", r"code of conduct|code of ethic|conduct rule|lokpal|prevention of corruption|ccs rule|law\b.*\bethic|ethic\b.*\blaw\b"),
    ("Ethics & Human Values", r"ethic|moral|value|happiness|conscience|forgiveness|honesty|truth|character|human being|means.*ends|equitable|distribution of wealth|wealth"),
]

# ---------------------------------------------------------------- PRELIMS
# Keyed by the existing `section` label. Prelims stems are 1-2 sentences, so cues
# must be concrete nouns, not argument words.
P_ENV = [
    ("Climate Change & Negotiations", r"climate change|carbon (?:emission|credit|sink|tax|neutral|sequestration)|net zero|unfccc|\bcop\b|global warming|greenhouse|emission (?:of|trading|target|intensity)"),
    ("Biodiversity & Wildlife Conservation", r"biodivers|wildlife|species|tiger|elephant|extinct|endangered|protected area|national park|sanctuary|biosphere|migratory|animal|mammal|bird|\bfish|reptile|insect|amphibian|flora|fauna|tortoise|lizard|monkey|macaque|sea cow|sea horse"),
    ("Pollution & Waste Management", r"pollution|waste|plastic|air quality|effluent|sewage|e.waste|pm ?2\.5|ozone|stubble"),
    ("Forests & Land Use", r"forest|deforest|afforest|tree cover|grassland"),
    ("Water Resources & Rivers", r"river|groundwater|aquifer|wetland|ramsar|watershed|dam\b|irrigation canal|lake|water quality"),
    ("Environmental Law & Institutions", r"environment protection act|environmental impact|\bngt\b|pollution control board|\bcpcb\b|clearance|convention on"),
    ("Renewable Energy & Transition", r"renewable|solar|wind energy|hydrogen|biofuel|clean energy|energy transition|geothermal|tidal"),
]
P_SCI = [
    ("Space Technology", r"space|satellite|isro|chandrayaan|gaganyaan|launch vehicle|remote sensing|orbit|apsara|navic|gaganyaan"),
    ("Biotechnology & Health Technology", r"biotech|genetic|\bgene\b|\bdna\b|\brna\b|stem cell|vaccine|crispr|antibiotic|bacteria|virus|enzyme|clon|gm crop|biosimilar|respiration|photosynthesis|digestion|\bblood\b|\bcell\b|tissue|hormone|vitamin|protein|metabolis"),
    ("Nuclear Technology", r"nuclear|reactor|fission|fusion|thorium|uranium|radioisotope|atomic energy"),
    ("IT, AI & Digital Technology", r"artificial intelligence|machine learning|cyber|internet|blockchain|5g|quantum|semiconductor|cloud|algorithm|social media|digital"),
    ("Defence Technology", r"missile|drone|\buav\b|hypersonic|radar|submarine|stealth|aircraft carrier|ballistic"),
    ("Nanotechnology & Materials", r"nanotech|\bnano\b|graphene|superconduct|metamaterial|new material"),
    ("IPR & Traditional Knowledge", r"intellectual property|patent|\bipr\b|traditional knowledge|geographical indication|gi tag"),
    ("Basic Physics & Chemistry", r"\blight\b|\bsound\b|\bheat\b|magnet|electric|\bforce\b|\bmotion\b|pressure|refraction|reflection|rainbow|\batom|molecul|\bacid|\bbase\b|\bmetal|alloy|\bdensity|friction|ball bearing|surface tension|viscosity|conductor"),
]
P_POLITY = [
    ("Fundamental Rights", r"fundamental right|article (1[2-9]|2\d|3[0-5])\b|right to (equality|freedom|life|privacy|education|religion)|writ|habeas corpus|mandamus"),
    ("DPSP & Fundamental Duties", r"directive principle|article (3[6-9]|4\d|5[01])\b|fundamental dut"),
    ("Preamble & Basic Structure", r"preamble|basic structure|kesavananda"),
    ("Federalism & Centre-State Relations", r"federal|centre.state|union.state|article (2[4-9]|3[56])\b|inter.state|gst council|governor.{0,30}state"),
    ("Parliament & Legislative Procedure", r"parliament|lok sabha|rajya sabha|joint sitting|ordinance|speaker|money bill|article 10[5-9]|article 11\d|parliamentary committee|question hour|zero hour"),
    ("Judiciary & Judicial Review", r"judiciar|supreme court|high court|article (12[4-9]|2[1-3]\d)\b|tribunal|collegium|chief justice|judicial review|public interest litigation|\bpil\b"),
    ("President, Governor & Executive", r"president|governor|prime minister|cabinet|council of minister|pardon|article (5[2-9]|6\d|7\d)\b|vice.president|attorney.general"),
    ("Constitutional & Statutory Bodies", r"\bcag\b|comptroller|election commission|finance commission|\bupsc\b|\bnhrc\b|\bncsc\b|\bncst\b|\bncm\b|\bngt\b|statutory body|article (14[89]|3[12]5)\b"),
    ("Elections & Electoral Reform", r"election|\bevm\b|voter|representation of people|constituency|electoral bond|anti.defection|article 32[49]\b"),
    ("Political Parties & Pressure Groups", r"political part|party system|pressure group|coalition|interest group"),
    ("Local Government & Panchayati Raj", r"panchayat|local self.govern|municipal|73rd|74th|article 24[0-3]\b|gram sabha"),
    ("Constitutional Amendment", r"amendment act|article 368|one hundred"),
    ("Emergency & Union Territories", r"emergency|article 35[2-9]\b|article 360|union territory|article 239|article 370"),
    ("Secularism & Uniform Civil Code", r"secular|uniform civil code|article 25|religious denomination"),
    ("Citizenship", r"citizenship|naturalis|overseas citizen"),
    ("Civil Services & Bureaucracy", r"civil service|bureaucra|all india service|administrative reform"),
    ("Transparency, RTI & Accountability", r"\brti\b|right to information|transparenc|lokpal|lokayukta|whistleblow"),
    ("E-Governance & Digital Governance", r"e.governance|digital india|aadhaar|digital public infrastructure|\bupi\b"),
    ("Regulatory Bodies & Autonomy", r"regulator|regulatory|\btrai\b|\bsebi\b|\brbi\b.{0,20}regulat|competition commission"),
    ("NGOs, SHGs & Civil Society", r"\bngo|self.help group|\bshg\b|civil society|community participation"),
    ("Government Schemes & Service Delivery", r"scheme|yojana|mission|programme|beneficiar|subsidy|pension"),
]
P_ECON = [
    ("Inflation & Monetary Policy", r"inflation|monetary policy|reserve bank|\brbi\b|repo rate|reverse repo|\bcpi\b|\bwpi\b|deflation|liquidity|money supply|currency"),
    ("Fiscal Policy, Budget & Taxation", r"budget|fiscal|\btax\b|\bgst\b|direct tax|indirect tax|deficit|finance bill|cess|surcharge|revenue expenditure|capital expenditure"),
    ("Banking & Financial Sector", r"\bbank|npa|credit|financial inclusion|insurance|capital market|micro.?finance|\bnbfc\b|debenture|mutual fund|bond market"),
    ("Agriculture, MSP & Farmers", r"agricultur|farming|farmer|\bmsp\b|minimum support|crop|irrigation|horticultur|livestock|fertilis|fertiliz|organic farm|cropping|seed|pesticide|agri"),
    ("Food Processing & Supply Chain", r"food processing|supply chain|cold chain|mandi|\bapmc\b|procurement|warehous|food grain"),
    ("Industry, Manufacturing & MSME", r"manufacturing|industrial|\bmake in india|\bsez\b|industrial policy|\bmsme\b|steel|cement|cement industry"),
    ("Infrastructure & PPP", r"infrastructure|\bppp\b|public.private|railway|airport|\bport\b|highway|power sector|telecom|metro rail"),
    ("Employment & Informal Sector", r"employment|unemploy|labour|informal sector|gig|workforce|mgnrega|minimum wage"),
    ("Trade, FDI & External Sector", r"\bfdi\b|foreign direct|exports?|imports?|current account|balance of payment|trade deficit|foreign exchange|tariff|wto"),
    ("Land Reform & Land Acquisition", r"land reform|land acquisition|land ceiling|tenancy|land record|landholding"),
    ("Urbanisation & Smart Cities", r"urban|smart city|slum|metropol|housing|real estate"),
    ("Growth, GDP & Inclusive Growth", r"\bgdp\b|growth rate|economic growth|per capita|inclusive growth|national income|poverty line"),
]
P_GEO = [
    ("Physical Geography & Geomorphology", r"plate tectonic|earthquake|volcan|glacier|erosion|landform|sediment|fold mountain|rock|mineral|geolog|karst|loess|rotation|revolution|\baxis\b|season|daytime|solstice|equinox|earth.s"),
    ("Climatology & Monsoon", r"monsoon|cyclone|rainfall|el nino|la nina|jet stream|weather|temperature|climatic|humidity|pressure belt"),
    ("Oceanography & Coasts", r"\bocean\b|coast|tide|sea level|coral|mangrove|tsunami|salinity|current|benguela|gulf stream"),
    ("Resources, Agriculture & Industry Location", r"resource|mining|soil|crop|irrigation|industry|plantation|forest type|vegetation"),
    ("Population, Urbanisation & Migration", r"population|urbaniz|census|migration|settlement|demograph|sex ratio|literacy"),
    ("Regional Geography & Mapping", r"\bmap\b|latitude|longitude|region|location|river system|physiograph|state.{0,20}borders|tropic"),
]
P_HIST = [
    ("Ancient & Medieval India", r"harappan|indus valley|vedic|maurya|gupta|ashoka|buddhis|jainis|sangam|mughal|sultanate|chola|vijayanagar|bhakti|sufi|medieval|ancient|pali|prakrit|numismatic|inscription|stupa|rock.cut"),
    ("Freedom Struggle & National Movement", r"freedom struggle|national movement|non.cooperation|civil disobedience|quit india|swaraj|revolutionar|colonial|british|mutiny|partition|congress|gandhi|tilak|bose|rowlatt|dandi|home rule"),
    ("Socio-Religious Reform Movements", r"reform movement|brahmo|arya samaj|ramakrishna|vivekananda|social reform|\bsati\b|widow|aligarh|theosoph|satyashodhak"),
    ("Tribes & Communities", r"\btribe|tribal|adivasi|indigenous|\bcommunity\b"),
    ("Art, Architecture & Culture", r"architect|temple|sculpture|painting|mural|shikhara|dance|music|raga|theatre|literature|poet|heritage|monument|festival|classical"),
    ("World History", r"french revolution|american revolution|industrial revolution|world war|renaissance|cold war|imperialism|suez|lenin|colonialism"),
    ("Post-Independence India", r"post.independen|constituent assembly|linguistic reorganisation|five year plan|integration of"),
]
P_IR = [
    ("India-China", r"china|chinese|sino"),
    ("India-Pakistan", r"pakistan|\bpok\b|\bloc\b"),
    ("India-United States", r"united states|\busa\b|\bu\.s\.|america"),
    ("India & Neighbours (SAARC)", r"nepal|bangladesh|sri lanka|bhutan|myanmar|afghanistan|maldives|\bsaarc\b|neighbour"),
    ("India & Southeast Asia / Indo-Pacific", r"asean|south.east asia|indo.pacific|act east|vietnam|indonesia|japan|korea|australia"),
    ("India & West Asia / Africa / Central Asia", r"west asia|middle east|africa|central asia|iran|israel|saudi|gulf|egypt|turkey"),
    ("UN & Multilateral Reform", r"united nation|security council|\bunsc\b|ecosoc|unesco|peacekeep|multilateral|\bwho\b|\bunep\b"),
    ("WTO, Trade & Economic Diplomacy", r"\bwto\b|trade agreement|\bfta\b|tariff|doha|world trade"),
    ("Global Groupings & Institutions", r"brics|\bg20\b|\bquad\b|\bsco\b|bimstec|\bimf\b|world bank|aiib|\boecd\b|commonwealth|asean"),
    ("Indian Diaspora", r"diaspora|overseas indian|pravasi|\bnri\b"),
    ("Maritime Security & Blue Economy", r"maritime|sea lane|piracy|indian ocean|blue economy|exclusive economic zone|\beez\b"),
    ("Terrorism & Security Cooperation", r"terror|terroris|extremis|radicalis|money laundering|financing of terror"),
    ("Energy Security & Strategic Resources", r"energy security|oil|gas pipeline|opec|uranium|strategic petroleum|rare earth"),
]

PRELIMS_FAMILY = {
    "Environment & Ecology": P_ENV,
    "Science & Technology": P_SCI,
    "Polity & Governance": P_POLITY,
    "Economy": P_ECON,
    "Geography": P_GEO,
    "Modern History": P_HIST,
    "Ancient History": P_HIST,
    "Medieval History": P_HIST,
    "History": P_HIST,
    "Art & Culture": P_HIST,
    "International Relations": P_IR,
}
# current-affairs rows have no subject label of their own: content decides
P_GLOBAL = P_SCI + P_ENV + P_POLITY + P_IR + P_ECON + P_HIST + P_GEO

# paper -> label for the fallback bucket
PAPER_LABEL = {
    "gs1": "General GS1",
    "gs2": "General GS2",
    "gs3": "General GS3",
    "gs4": "General GS4",
    "essay": "Essay",
}
SOCIOLOGY = ("sociology1", "sociology2")

# a master theme that cannot appear in that paper -> the row is mislabelled
ALLOWED = {
    "gs1": {"Modern & World History", "Indian Culture & Heritage", "Indian Society & Social Change",
            "Geography", "Environment & Climate", "Women & Gender", "Economy & Inclusive Growth",
            "Social Justice & Inclusion", "Urbanization", "International Relations"},
    "gs2": {"Polity & Constitution", "Governance & Accountability", "International Relations",
            "Social Justice & Inclusion", "Ethics, Integrity & Aptitude"},
    "gs3": {"Economy & Inclusive Growth", "Agriculture & Food Systems", "Science & Technology",
            "Environment & Climate", "Internal Security", "Disaster Management",
            "Social Justice & Inclusion", "Geography"},
    "gs4": {"Ethics, Integrity & Aptitude", "Social Justice & Inclusion"},
}


def tag(row) -> tuple[str, str]:
    if row.paper in SOCIOLOGY and isinstance(row.subject, str) and row.subject.strip():
        return row.subject.strip(), "subject_column"
    if str(row.nature) == "Case Study":
        return "Case Study", "nature_column"
    q = str(row.question or "").lower()
    for name, pat in RULES.get(row.paper, []):
        if re.search(pat, q):
            return name, "rule"
    return PAPER_LABEL.get(row.paper, f"General {row.paper}"), "fallback"


def tag_prelims(row) -> tuple[str, str]:
    q = str(row.question or "").lower()
    family = PRELIMS_FAMILY.get(str(row.section).strip(), P_GLOBAL)
    for name, pat in family:
        if re.search(pat, q):
            return name, "rule"
    # unattributed current affairs: try everything before giving up
    if family is not P_GLOBAL:
        for name, pat in P_GLOBAL:
            if re.search(pat, q):
                return name, "rule_global"
    return "General " + str(row.section).strip(), "fallback"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(DATA).fillna({"subject": ""})
    tagged = m.apply(tag, axis=1, result_type="expand")
    m["sub_theme"], m["sub_theme_method"] = tagged[0], tagged[1]
    m.to_csv(OUT / "mains_subthemed.csv", index=False)

    # rows whose master_theme cannot belong to their paper
    sub = m[m.paper.isin(ALLOWED)]
    bad = sub[~sub.apply(lambda r: r.master_theme in ALLOWED[r.paper], axis=1)]
    bad[["id", "year", "paper", "master_theme", "subject", "question"]].to_csv(
        OUT / "suspected_master_theme.csv", index=False
    )

    gs = m[~m.paper.isin(SOCIOLOGY)]
    rec = (
        gs.groupby("sub_theme").year.agg(years="nunique", hits="size", first="min", last="max")
        .reset_index().sort_values(["years", "hits"], ascending=False)
    )
    rec["gap_since_last"] = 2026 - rec.last
    rec.to_csv(OUT / "subtheme_recurrence.csv", index=False)

    # ---- prelims, same vocabulary so the two papers can be joined ----
    p = pd.read_csv(PRELIMS_CSV)
    pt = p.apply(tag_prelims, axis=1, result_type="expand")
    p["sub_theme"], p["sub_theme_method"] = pt[0], pt[1]
    p.to_csv(OUT / "prelims_subthemed.csv", index=False)
    prec = (
        p.groupby("sub_theme").year.agg(years="nunique", hits="size", first="min", last="max")
        .reset_index().sort_values(["years", "hits"], ascending=False)
    )
    prec["gap_since_last"] = 2026 - prec.last
    prec.to_csv(OUT / "prelims_subtheme_recurrence.csv", index=False)

    # sub-themes asked in BOTH papers -> one study effort, two papers
    cross = (
        prec.merge(rec, on="sub_theme", suffixes=("_prelims", "_mains"))
        .loc[:, ["sub_theme", "years_prelims", "hits_prelims", "years_mains", "hits_mains",
                 "last_prelims", "last_mains"]]
        .sort_values(["years_prelims", "years_mains"], ascending=False)
    )
    cross.to_csv(OUT / "cross_paper_subthemes.csv", index=False)

    lines = [
        f"MAINS  rows {len(m)} | distinct sub_themes {m.sub_theme.nunique()}",
        m.sub_theme_method.value_counts().to_string(),
        f"  rows with a master_theme impossible for their paper: {len(bad)}",
        "",
        f"PRELIMS rows {len(p)} | distinct sub_themes {p.sub_theme.nunique()}",
        p.sub_theme_method.value_counts().to_string(),
        "",
        f"sub-themes asked in both papers: {len(cross)}",
        "",
        "== recurring GS sub-themes (mains) ==",
        rec.head(40).to_string(index=False),
        "",
        "== recurring sub-themes (prelims) ==",
        prec[~prec.sub_theme.str.startswith("General")].head(40).to_string(index=False),
        "",
        "== fallback buckets ==",
        m[m.sub_theme_method == "fallback"].sub_theme.value_counts().to_string(),
        p[p.sub_theme_method == "fallback"].sub_theme.value_counts().to_string(),
    ]
    text = "\n".join(lines)
    (OUT / "subtheme_coverage.txt").write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
