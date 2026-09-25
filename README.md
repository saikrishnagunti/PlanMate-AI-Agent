# PlanMate AI

PlanMate is a Hyderabad-focused Streamlit dashboard for discovering nearby activities, dining, and relaxation options. It combines browser location, manual map exploration, live weather, and Gemini-powered venue research in a LangGraph workflow.

The app favors no result over an invented venue. Recommendations are accepted only when the returned locality, activity, and distance satisfy the validation rules, including the six-kilometre search radius.

## Features

- Browser geolocation with an explicit ON/OFF control.
- Manual locality, address, map URL, or latitude/longitude selection.
- Nearby-area navigation without enabling browser tracking.
- Live Open-Meteo weather context for the selected coordinates.
- DuckDuckGo-grounded Gemini venue research with locality and distance filtering.
- Google Maps links for accepted venues and a general map exploration option.
- Streamlit interface with a bundled browser-location component.

## Project Structure

```text
PlanMate/
├── app.py                         # Streamlit dashboard
├── cli_test.py                    # Optional terminal CLI
├── requirements.txt               # Python dependencies
├── src/
│   ├── agents/                    # LangGraph nodes and graph
│   ├── components/frontend/build/ # Browser geolocation component
│   └── tools/                     # Weather, distance, and venue search
├── styles/main.css                # Dashboard styling
└── assets/                        # UI avatars
```

## Requirements

- Python 3.10 or newer
- A Gemini API key
- A browser that supports the Geolocation API for live location

## Setup

```bash
git clone https://github.com/saikrishnagunti/PlanMate-AI-Agent.git PlanMate
cd PlanMate
python -m venv .venv
```

Activate the environment, then install dependencies:

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root. Keep it private and never commit it:

```env
GEMINI_API_KEY=your_gemini_api_key
```

For Streamlit Cloud, add `GEMINI_API_KEY` under **App settings > Secrets** instead of creating a `.env` file. The app will still start without the key, but venue recommendations will remain unavailable until it is configured.

## Run

Start the web dashboard:

```bash
streamlit run app.py
```

Open the local URL shown by Streamlit, normally `http://localhost:8501`. Live location requires granting permission in the browser; manual location selection remains available when tracking is OFF.

Run the optional terminal client:

```bash
python cli_test.py
```

## Data and privacy

Location is used to resolve a selected Hyderabad area, fetch weather, and constrain venue discovery. Browser coordinates are requested only when live tracking is enabled. Nominatim, Open-Meteo, DuckDuckGo, Google Gemini, and Google Maps are external services used by the application.

The application does not promise that third-party listings are permanently current. Always confirm availability, hours, pricing, and travel conditions with the venue before leaving.

## Validation

Before pushing changes, run:

```bash
python -m compileall app.py cli_test.py src
```

## License

MIT License.