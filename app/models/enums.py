import enum


class LeadType(str, enum.Enum):
    no_website_candidate = "no_website_candidate"
    weak_website_candidate = "weak_website_candidate"
    website_exists_not_target = "website_exists_not_target"
    invalid_or_risky = "invalid_or_risky"


class LeadSourceType(str, enum.Enum):
    google_places = "google_places"
    company_website = "company_website"
    manual_entry = "manual_entry"
    licensed_provider = "licensed_provider"
    public_register = "public_register"


class EnrichmentStatus(str, enum.Enum):
    discovered = "discovered"
    place_only = "place_only"
    no_website = "no_website"
    website_found = "website_found"
    website_analyzed = "website_analyzed"
    manual_review_required = "manual_review_required"
    verified = "verified"
    rejected = "rejected"


class CompanyStatus(str, enum.Enum):
    discovered = "discovered"
    needs_review = "needs_review"
    verified = "verified"
    rejected = "rejected"
    contacted = "contacted"
    suppressed = "suppressed"


class LeadPriority(str, enum.Enum):
    high_priority = "high_priority"
    medium_priority = "medium_priority"
    low_priority = "low_priority"
    blocked = "blocked"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class ContactReviewStatus(str, enum.Enum):
    needs_review = "needs_review"
    verified = "verified"
    rejected = "rejected"
