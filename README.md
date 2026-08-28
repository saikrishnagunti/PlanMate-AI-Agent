# 🎯 PlanMate: Autonomous Activity & Dining AI Agent

PlanMate is an autonomous conversational AI agent powered by **Gemini 3.6 Flash** designed to help users plan daily leisure activities, sports sessions, dining outings, and relaxation spots.

Instead of generating static or hallucinated suggestions, PlanMate evaluates real-time environmental context (live weather) and executes geospatial lookups via **OpenStreetMap (Nominatim)** to provide real venue names, mathematically accurate distances ($km$), and direct navigation links to **Google Maps**.

---

## 🏗️ Architecture & Execution Flow

PlanMate operates on an iterative **ReAct (Reason + Act)** tool-calling execution loop:

```text
                            ┌────────────────────────┐
                            │       User Query       │
                            └───────────┬────────────┘
                                        │
                                        ▼
                      ┌────────────────────────────────────┐
                      │    System Instructions & Guardrail │
                      │          (Scope Validation)        │
                      └─────────────────┬──────────────────┘
                                        │
                                        ▼
                      ┌────────────────────────────────────┐
                      │    Gemini 3.6 Flash Reasoning      │
                      │     (Tool Call Resolution Loop)    │
                      └─────────┬────────────────┬─────────┘
                                │                │
            ┌───────────────────┘                └───────────────────┐
            ▼                                                        ▼
┌───────────────────────────┐                            ┌───────────────────────────┐
│     get_live_weather      │                            │  search_places_with_maps  │
│    (wttr.in REST API)     │                            │    (OpenStreetMap / OSM)  │
│  - Checks Precipitation   │                            │  - Resolves Coordinates   │
│  - Validates Outdoor Suit │                            │  - Computes Haversine (km)│
└───────────┬───────────────┘                            │  - Builds Direct Maps Link│
            │                                            └───────────┬───────────────┘
            │                                                        │
            └───────────────────┬────────────────────────────────────┘
                                │
                                ▼
                      ┌────────────────────────────────────┐
                      │    Synthesized Final Response      │
                      │ (Weather Advisory + Venues + Links)│
                      └────────────────────────────────────┘
🚀 Key Technical HighlightsMulti-Turn Function Tooling: Uses structured function declarations (types.FunctionDeclaration, types.Tool) allowing the model to dynamically request and resolve real-time tools.Environmental Context Validation: Integrates live weather data via wttr.in. If precipitation or adverse weather is detected, the agent warns the user and suggests indoor alternatives (e.g., covered box turf, bowling, multiplex).Dynamic Geospatial Search: Queries OpenStreetMap Nominatim dynamically without hardcoded place dictionaries. Straight-line distance is computed using the Haversine Formula:$$d = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$Intent & Slang Normalizer: Maps natural language phrases (e.g., boxcricket, mandi, ekart, read a book, spa, biryani) to OpenStreetMap taxonomic tags.Strict Guardrails: Rejects out-of-domain requests (coding, trivia, homework) to maintain dedicated conversational focus.API Rate-Limit Handling: Implements exponential backoff wrappers to handle API rate limits and avoid abrupt terminations.📂 Project StructurePlaintext1st project/
│
├── .env                  # Private API credentials (Git-ignored)
├── .gitignore            # Secret & artifact exclusion rules
├── requirements.txt      # Python dependencies (google-genai, streamlit, requests, etc.)
├── README.md             # Project documentation
├── PlanMate.py           # Core CLI interactive agent loop
├── app.py                # Streamlit Web Application interface
└── localhost.pdf         # Local UI test exports/artifacts
🛠️ Installation & SetupClone the repository:Bashgit clone [https://github.com/saikrishnagunti/PlanMate-AI-Agent.git](https://github.com/saikrishnagunti/PlanMate-AI-Agent.git)
cd PlanMate-AI-Agent
Install dependencies:Bashpip install -r requirements.txt
Configure Environment Variables:Create a .env file in the root directory:Code snippetGEMINI_API_KEY=your_actual_gemini_api_key_here
Run the Agent:CLI Terminal Mode:Bashpython PlanMate.py
Streamlit Web Interface:Bashstreamlit run app.py
🧪 Sample Interactions1. Activity Recommendation with Live Weather & CoordinatesPlaintextYou: i am in miyapur, i want to read a book, find me a library near my location

⚙️ [TOOL CALL] Executing: get_live_weather({'city': 'Miyapur'})
⚙️ [TOOL CALL] Executing: search_places_with_maps({'category': 'relax', 'location': 'Miyapur', 'sub_activity': 'library'})

PlanMate:
Here are some library options around Miyapur, keeping in mind the current weather (29°C with patchy rain nearby):

1. JNTU Library (JNTUHCEH, Way to CRC)
   • Distance: ~3.6 km away
   • Directions: [Open in Google Maps](https://www.google.com/maps/search/?api=1&query=17.498,78.389)

2. CRC Library / Reading Hall (JNTUHCEH Area)
   • Distance: ~3.7 km away
   • Directions: [Open in Google Maps](https://www.google.com/maps/search/?api=1&query=17.499,78.390)

Since it might rain, remember to carry an umbrella!
2. Guardrail ContainmentPlaintextYou: Write a python script to sort an array.

PlanMate:
I am PlanMate, your personal day planner! Please choose an activity (Play, Eat, Relax) so I can help plan your day.
