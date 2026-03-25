# AuditGPT

**AuditGPT** is an AI-powered forensic financial auditing tool designed to detect financial anomalies, scrutinize management vs. auditor sentiment, and provide a comprehensive fraud risk assessment for listed companies in India.

By uniting traditional forensic accounting models (like the Beneish M-Score) with Google's advanced Gemini AI capabilities, AuditGPT empowers analysts and researchers to perform deep-dive financial health checks instantly.

## Key Features

- **Fraud Risk Detection**: Leverages the Beneish M-Score to detect potential earnings manipulation and summarizes overall risk into a simplified 0-100 score.
- **AI Sentiment Analysis**: Deep dives into Management Discussion and Analysis (MD&A) and Auditor reports to identify mismatches—detecting cases where management is overly optimistic while auditors express caution.
- **Related Party Transaction (RPT) Monitoring**: Flags suspicious YoY jumps in related party transactions to uncover potential governance issues.
- **Insider Tracker**: Monitor promoter and insider buying/selling activities for suspicious trends.
- **Financial Anomaly Mapping**: Visually track anomalies in key metrics (Revenue vs OCF, Debt buildup) alongside a holistic "red flag" timeline.
- **Peer Benchmarking**: Compare a company's metrics directly against industry averages.

## Tech Stack

- **Backend**: Python, Flask
- **AI Integration**: Google Gemini AI (`google-generativeai`)
- **Frontend**: HTML5, Tailwind CSS, Chart.js
- **Data Gathering**: Yahoo Finance / Custom CSV mappings

## Getting Started

### Prerequisites

- Python 3.9+
- A Google Gemini API Key

### Installation

1. Clone this repository to your local machine:
   ```bash
   git clone <your-repository-url>
   cd Auditgpt
   ```

2. Set up a virtual environment and activate it:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On Mac/Linux
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory and add your Gemini API Key:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### Running the App

Start the Flask development server:
```bash
python main.py
```

The application will be running at `http://127.0.0.1:5000/`.

## Disclaimer

**For educational and research purposes only.** This software does not provide financial advice. The models and data are indicative and should not be used as the sole basis for investment decisions.
