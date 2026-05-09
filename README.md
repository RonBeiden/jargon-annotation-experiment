# 📝 Jargon Level Annotation Experiment

A **Streamlit web application** for collecting human annotations on the difficulty/jargon level of scientific abstracts. Built as part of an MSc thesis investigating readability in scientific writing (*"Gobbledygook: Identification of Jargon Levels in Scientific Articles"*).

## Overview

The experiment asks annotators to assess how difficult scientific abstracts are to understand, using **three complementary annotation methods** in a single session:

| Method | What the annotator does | Output |
|--------|------------------------|--------|
| **A — Direct Classification** | Select the minimum academic level needed to understand the abstract | High School / BSc / MSc / PhD |
| **B — Continuous Scoring** | Rate difficulty on a slider | Integer 0–100 |
| **C — Pairwise Comparison** | Compare two abstracts side-by-side and pick the harder one | Left / Right / Tie + justification |

Each annotator completes all three methods on **different sets of abstracts**, ensuring no one sees the same abstract twice across methods (preventing anchoring bias).

## Experimental Design

### Latin Square Counterbalancing

15 annotators are split into 3 groups. Each group applies each method to a **different** abstract set:

| | Set 1 (20 abstracts) | Set 2 (20 abstracts) | Set 3 (20 abstracts) |
|---|---|---|---|
| **Group 1** (IDs 1–5) | Classify (A) | Score (B) | Pairwise (C) |
| **Group 2** (IDs 6–10) | Score (B) | Pairwise (C) | Classify (A) |
| **Group 3** (IDs 11–15) | Pairwise (C) | Classify (A) | Score (B) |

Block presentation order is also counterbalanced across 6 permutations to control for fatigue and learning effects.

### Abstract Data

The dataset contains **60 real abstracts** from **Nature** and **Science** journals, filtered to Computer Science topics. Abstracts were fetched programmatically from the [OpenAlex API](https://openalex.org/) and span publication years from 1922 to 2024.

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/RonBeiden/jargon-annotation-experiment.git
cd jargon-annotation-experiment
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Deployment (Streamlit Cloud — Free)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Select this repository, branch `main`, main file `app.py`
3. (Optional) Add Google Sheets secrets in the dashboard for automatic response collection
4. Share the generated URL with annotators

## Data Storage Options

| Option | Setup needed | How it works |
|--------|-------------|--------------|
| **CSV Download** (default) | None | Annotator downloads their responses as a CSV at the end |
| **Google Sheets** (recommended) | Service account + secrets | Responses auto-save to a shared Google Sheet in real time |

### Google Sheets Setup

<details>
<summary>Click to expand setup instructions</summary>

1. Create a Google Cloud project and enable the Sheets + Drive APIs
2. Create a Service Account and download the JSON key
3. Create a Google Sheet and share it with the service account email (Editor access)
4. Add secrets to `.streamlit/secrets.toml` (local) or the Streamlit Cloud dashboard:

```toml
sheet_name = "Annotation Responses"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-sa@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

</details>

## Output Schema

Each response row contains:

| Column | Description |
|--------|-------------|
| `annotator_id` | Assigned annotator number (1–15) |
| `education` | Annotator's education level |
| `field` | Annotator's field of study |
| `group` | Latin square group (1–3) |
| `block_number` | Block order (1–3) |
| `method` | A, B, or C |
| `abstract_id` | Abstract ID (or left abstract for pairwise) |
| `abstract_id_2` | Right abstract ID (pairwise only) |
| `response` | The annotation value |
| `justification` | Free-text reasoning |

## Customizing Abstracts

Replace `abstracts.json` with your own data. Required format:

```json
[
  {
    "id": 1,
    "title": "Abstract Title",
    "discipline": "Computer Science",
    "set_number": 1,
    "text": "The abstract text..."
  }
]
```

- Each abstract needs a unique integer `id`
- `set_number` must be 1, 2, or 3 (balanced: 20 per set for 60 abstracts)
- Additional metadata fields (`journal`, `year`, `doi`) are optional

## Project Structure

```
├── app.py              # Streamlit application (main entry point)
├── abstracts.json      # 60 real abstracts from Nature & Science
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## License

This project is part of academic research. Feel free to use and adapt for your own annotation experiments.
