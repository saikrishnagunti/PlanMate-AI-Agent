# 🎯 PlanMate: Autonomous Activity & Dining AI Agent

PlanMate is an autonomous lifestyle and daily planning conversational AI agent powered by **Google Gemini 2.5 Flash**. It helps users discover leisure activities, sports sessions, dining spots, and relaxation spaces without hallucinated venues or stale information.

Instead of guessing locations, PlanMate evaluates real-time meteorological conditions (**wttr.in**) and executes targeted category searches linked directly to verified places on **Google Maps**.

---

## 🏗️ Architecture & ReAct Workflow

PlanMate operates on an iterative **ReAct (Reasoning + Acting)** tool execution loop:

```text
                            ┌────────────────────────┐
                            │       User Query       │
                            └───────────┬────────────┘
                                        │
                                        ▼
                      ┌────────────────────────────────────┐
                      │    System Instructions & Firewall  │
                      │       (Scope & Domain Guardrails)  │
                      └─────────────────┬──────────────────┘
                                        │
                                        ▼
                      ┌────────────────────────────────────┐
                      │    Gemini 2.5 Flash Reasoning      │
                      │  (Parallel Tool Dispatch Decision) │
                      └─────────┬────────────────┬─────────┘
                                │                │
            ┌───────────────────┘                └───────────────────┐
            ▼                                                        ▼
┌───────────────────────────┐                            ┌───────────────────────────┐
│     get_live_weather      │                            │  search_places_with_maps  │
│    (wttr.in REST API)     │                            │ (Targeted Google Maps API)│
│  - Real-time Temp & Cond  │                            │  - Keyword Taxonomy       │
│  - Precipitation Checks   │                            │  - Clean Deep-Links       │
│  - Outdoor Suitability    │                            │  - Zero Venue Invention   │
└───────────┬───────────────┘                            └───────────┬───────────────┘
            │                                                        │
            └───────────────────┬────────────────────────────────────┘
                                │
                                ▼
                      ┌────────────────────────────────────┐
                      │    Synthesized Final Response      │
                      │  (Weather Block + Verified Links)  │
                      └────────────────────────────────────┘
```

---

## 🚀 Key Technical Highlights

* **Parallel Tool Dispatching**: Triggers both `get_live_weather` and `search_places_with_maps` concurrently in the initial model turn, cutting token overhead and API hops by 50%.

* **Strict Grounding & Anti-Hallucination**: Eliminates fake venue hallucinations by constraining recommendations to verified Google Maps search intents rather than ungrounded shop names.

* **Real-Time Weather Grounding**: Evaluates live weather conditions via `wttr.in`. If precipitation or adverse weather is present, the agent alerts the user and pivots outdoor plans to indoor options.

* **Conversational Locality Anchoring**: Preserves user-declared localities (e.g., Manikonda, Madhapur, Kondapur) across follow-up turns without geographic amnesia.

* **Keyword Normalizer**: Maps ~80 user intents and colloquial phrases (`boxcricket`, `futsal`, `mandi`, `gokarting`, `spa`, `sushi`) into targeted query terms.

* **Rate-Limit Backoff Engine**: Automatically intercepts HTTP 429 quota exhaustion errors, parses Google's exact retry delay, and renders an active countdown timer before resuming execution.

* **Domain Firewall**: Deflects out-of-scope requests (coding, homework, politics) using an explicit refusal prompt.

---

## 📂 Project Structure

```text
PlanMate-AI-Agent/
│
├── .env                  # Private Gemini API credentials (Git-ignored)
├── .gitignore            # Secret & artifact exclusion rules
├── requirements.txt      # Python runtime dependencies
├── README.md             # Project documentation
├── PlanMate.py           # CLI interactive terminal REPL
└── app.py                # Streamlit web application interface
```

---

## 🛠️ Prerequisites & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/saikrishnagunti/PlanMate-AI-Agent.git](https://github.com/saikrishnagunti/PlanMate-AI-Agent.git)
cd PlanMate-AI-Agent
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

---

## 💻 Running the Application

### Web UI (Streamlit Dashboard)
```bash
streamlit run app.py
```

### Terminal CLI (Interactive REPL)
```bash
python PlanMate.py
```

---

## 🧪 Sample Interactions

### 1. Activity & Dining Outing with Live Weather Grounding
```text
You: I am in Kondapur now, I want to play gokarting and eat frankie for supper at 5:00 PM

PlanMate:
⛅ **Weather Update**
- **Temperature:** 32°C
- **Condition:** Cloudy
- **Humidity:** 37%
- **Verdict:** Pleasant cloudy weather, perfect for track racing and grabbing a quick evening bite around 5:00 PM.

---

📍 **Recommended Options**
- **Top rated Gokarting spots in Kondapur**
  * **Details:** Discover high-octane racing circuits and professional go-karting tracks around your location.
  * **Directions:** [Open in Google Maps](https://www.google.com/maps/search/?api=1&query=go+karting+circuit+track+near+Kondapur+Hyderabad)

- **Top rated Frankie spots in Kondapur**
  * **Details:** Popular street food joints and eateries serving delicious, wrapped rolls and frankies.
  * **Directions:** [Open in Google Maps](https://www.google.com/maps/search/?api=1&query=frankie+roll+wrap+near+Kondapur+Hyderabad)
```

### 2. Follow-up Turn with Locality Memory
```text
You: Change in plan, I want to eat sushi instead of frankie

PlanMate:
⛅ **Weather Update**
- **Temperature:** 32°C
- **Condition:** Cloudy
- **Humidity:** 37%
- **Verdict:** Great weather conditions for heading out to a restaurant in Kondapur.

---

📍 **Recommended Options**
- **Top rated Sushi spots in Kondapur**
  * **Details:** Fine dining restaurants and cafes serving fresh sushi and authentic Japanese cuisine.
  * **Directions:** [Open in Google Maps](https://www.google.com/maps/search/?api=1&query=sushi+bar+restaurant+near+Kondapur+Hyderabad)
```

### 3. Out-of-Domain Guardrail Deflection
```text
You: Write a python script to sort an array.

PlanMate:
I am PlanMate, your personal day planner! Please choose an activity (Play, Eat, Relax) so I can help plan your day.
```

---

## 📄 License

MIT License. Developed for open-source AI agent research and development.