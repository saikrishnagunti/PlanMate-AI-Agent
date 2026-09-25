from typing import TypedDict, List, Dict, Any, Optional

class Venue(TypedDict):
    name: str
    distance: str
    travel_time: str
    status: str
    cost: str
    amenities: str
    highlights: str
    directions_link: str

class PlanMateState(TypedDict):
    user_query: str
    location_input: str
    locality: str
    lat: float
    lon: float
    category: str
    sub_activity: str
    weather_data: Dict[str, Any]
    candidate_venues: List[Venue]
    all_places_link: str
    retry_count: int
    validation_status: str
    critic_notes: str
    final_response: str
    error: Optional[str]