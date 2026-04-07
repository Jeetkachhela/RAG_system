# Kanan.co Static Knowledge Base & FAQ Data

COMPANY_FAQ = [
    {
        "question": "What services does Kanan.co offer?",
        "answer": "Kanan.co (Kanan International) offers study abroad consultancy, university application support, student visa guidance, test preparation (IELTS, TOEFL, GRE, PTE, GMAT), education loan assistance, and travel/accommodation help."
    },
    {
        "question": "Which countries can I apply to?",
        "answer": "Kanan.co provides guidance for major study destinations including the USA, Canada, UK, Australia, Germany, France, Ireland, and the Netherlands."
    },
    {
        "question": "Does Kanan.co provide online coaching?",
        "answer": "Yes, Kanan uses advanced EdTech tools to offer comprehensive online coaching for standardized tests like IELTS, PTE, and TOEFL, including mock tests and analytics."
    },
    {
        "question": "Who are the founders of Kanan.co?",
        "answer": "Kanan International was founded in 1996 by Manish Shah and Sonal Shah in Vadodara, Gujarat."
    }
]

LEADERSHIP_TEAM = [
    {"name": "Manish Shah", "role": "Founder and Managing Director"},
    {"name": "Sonal Shah", "role": "Co-founder & Director (USA Department)"},
    {"name": "Anil Goyal", "role": "Head, Canada Department"},
    {"name": "Chirag Parmar", "role": "Quality and Service Department"},
    {"name": "Jitendra Katiya", "role": "Admission Department (Agent Network)"},
    {"name": "Sudhanshu Bajpai", "role": "Project Head (Kanan Prep)"},
    {"name": "Kishori Modi", "role": "Head, USA Department"},
    {"name": "Priyanka Patel", "role": "Head, UK Department"},
    {"name": "Hardik Vadgama", "role": "Agent Division (North zone/Canada)"},
    {"name": "Mukesh Machhi", "role": "Agent Division (West zone/Canada)"},
    {"name": "Hiren Sheth", "role": "Accounts Department"},
    {"name": "Hirenkumar Hasmukhlal Sheth", "role": "Whole-time Director"}
]

def get_kb_context(query: str) -> str:
    """Quickly searches the static KB for matches to reduce API calls."""
    query_lower = query.lower()
    matches = []
    
    # Check FAQs
    for faq in COMPANY_FAQ:
        if any(word in query_lower for word in faq["question"].lower().split()):
            matches.append(f"FAQ: {faq['question']}\nAns: {faq['answer']}")

    # Check Leadership
    for person in LEADERSHIP_TEAM:
        if person["name"].lower() in query_lower:
            matches.append(f"Person: {person['name']} is the {person['role']} at Kanan.co.")
            
    return "\n---\n".join(matches) if matches else ""
