import streamlit as st
import pandas as pd
import json
import os
import csv
import io
from datetime import datetime
from itertools import combinations
import random

# ─── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Jargon Level Annotation",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Constants ────────────────────────────────────────────────────────────────

# Latin square: which method applies to which abstract set, by group
LATIN_SQUARE = {
    1: {1: "A", 2: "B", 3: "C"},
    2: {1: "B", 2: "C", 3: "A"},
    3: {1: "C", 2: "A", 3: "B"},
}

# 6 possible block orderings (counterbalanced)
BLOCK_ORDERINGS = [
    ["A", "B", "C"],
    ["A", "C", "B"],
    ["B", "A", "C"],
    ["B", "C", "A"],
    ["C", "A", "B"],
    ["C", "B", "A"],
]

METHOD_INFO = {
    "A": {
        "name": "Direct Classification",
        "icon": "🏷️",
        "color": "#1565c0",
        "instruction": (
            "For each abstract below, select the **minimum academic level** "
            "needed to fully understand it.\n\n"
            "- **High School** — a motivated high-school student could follow it\n"
            "- **BSc** — requires undergraduate-level science knowledge\n"
            "- **MSc** — requires graduate-level specialization\n"
            "- **PhD** — requires deep expert knowledge in the specific field"
        ),
    },
    "B": {
        "name": "Continuous Scoring (0–100)",
        "icon": "📊",
        "color": "#e65100",
        "instruction": (
            "For each abstract, rate its difficulty on a scale from "
            "**0** (trivial, anyone can understand) to **100** "
            "(incomprehensible, extremely specialized).\n\n"
            "Use the full range. A newspaper article might be 5–15; "
            "a highly technical physics paper might be 85–95."
        ),
    },
    "C": {
        "name": "Pairwise Comparison",
        "icon": "⚖️",
        "color": "#2e7d32",
        "instruction": (
            "You will see **two abstracts side by side**. Decide which one is "
            "**harder to understand**.\n\n"
            "- Choose **Left** or **Right** if one is clearly harder\n"
            "- Choose **Tie** only if they feel equally difficult\n"
            "- Briefly explain your reasoning (1–2 sentences)"
        ),
    },
}

CLASSIFICATION_LEVELS = [
    "High School",
    "BSc (Undergraduate)",
    "MSc (Master's)",
    "PhD (Doctoral)",
]

EDUCATION_OPTIONS = [
    "BSc (final year)",
    "MSc student",
    "PhD candidate",
    "Post-doc / Faculty",
]

FIELD_OPTIONS = [
    "Biology",
    "Physics",
    "Chemistry",
    "Medicine",
    "Computer Science",
    "Earth Sciences",
    "Engineering",
    "Mathematics",
    "Other",
]

N_PAIRWISE = 4  # number of pairwise comparisons per annotator
GROUP_SIZE = 5  # annotators per group


# ─── Data Loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_abstracts():
    path = os.path.join(os.path.dirname(__file__), "abstracts.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


def get_abstracts_for_set(df, set_number):
    return df[df["set_number"] == set_number].reset_index(drop=True)


def generate_pairs(abstracts_df, n_pairs, seed):
    ids = abstracts_df["id"].tolist()
    all_pairs = list(combinations(ids, 2))
    rng = random.Random(seed)
    rng.shuffle(all_pairs)
    return all_pairs[:n_pairs]


# ─── Assignment Logic ─────────────────────────────────────────────────────────

def compute_assignment(annotator_id):
    group = ((annotator_id - 1) // GROUP_SIZE) + 1
    group = min(group, 3)  # cap at 3 groups
    ordering_idx = (annotator_id - 1) % len(BLOCK_ORDERINGS)
    block_order = BLOCK_ORDERINGS[ordering_idx]

    # For each method in block_order, find which set it maps to
    method_to_set = {v: k for k, v in LATIN_SQUARE[group].items()}

    blocks = []
    for method in block_order:
        blocks.append({
            "method": method,
            "set_number": method_to_set[method],
        })
    return group, blocks


# ─── Google Sheets Integration ────────────────────────────────────────────────

SHEET_COLUMNS = [
    "annotator_id", "education", "field", "group", "block_number", "method",
    "abstract_id", "abstract_id_2", "response", "harder_abstract_id",
    "justification", "abstract_title", "abstract_discipline",
    "block_position", "timestamp",
]

def save_to_gsheets(rows):
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open(st.secrets["sheet_name"]).sheet1

        # Ensure headers exist
        existing = sheet.row_values(1)
        if not existing:
            sheet.append_row(SHEET_COLUMNS, value_input_option="RAW")

        for row in rows:
            ordered = [str(row.get(col, "")) for col in SHEET_COLUMNS]
            sheet.append_row(ordered, value_input_option="RAW")
        return True
    except Exception:
        return False


def gsheets_configured():
    try:
        return "gcp_service_account" in st.secrets and "sheet_name" in st.secrets
    except Exception:
        return False


# ─── CSV Export ───────────────────────────────────────────────────────────────

def responses_to_csv(responses):
    if not responses:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=responses[0].keys())
    writer.writeheader()
    writer.writerows(responses)
    return output.getvalue()


# ─── Session State Init ──────────────────────────────────────────────────────

def init_state():
    defaults = {
        "page": "registration",  # registration | block_intro | annotation | block_done | complete
        "block_idx": 0,
        "item_idx": 0,
        "responses": [],
        "annotator": {},
        "group": 0,
        "blocks": [],
        "pairs": {},  # set_number -> list of (id_left, id_right)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─── UI: Registration ────────────────────────────────────────────────────────

def show_registration():
    st.markdown("# 📝 Jargon Level Annotation Study")
    st.markdown(
        "Welcome! You will evaluate scientific abstracts using **three different "
        "methods**. The entire session takes approximately **15–20 minutes** "
        "(prototype) or **45–60 minutes** (full study)."
    )
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        annotator_id = st.number_input(
            "Your Annotator ID (assigned to you)",
            min_value=1, max_value=30, value=1, step=1,
        )
        education = st.selectbox("Your education level", EDUCATION_OPTIONS)
    with col2:
        field = st.selectbox("Your primary field of study", FIELD_OPTIONS)
        st.markdown("")  # spacer
        st.markdown("")

    st.markdown("---")

    # Show assignment preview
    group, blocks = compute_assignment(annotator_id)
    st.markdown(f"**Your assignment:** Group {group}")
    preview_cols = st.columns(3)
    for i, block in enumerate(blocks):
        m = block["method"]
        info = METHOD_INFO[m]
        with preview_cols[i]:
            st.markdown(
                f"**Block {i+1}:** {info['icon']} {info['name']}  \n"
                f"Abstract Set {block['set_number']}"
            )

    st.markdown("")
    if st.button("✅  Start Annotation", type="primary", use_container_width=True):
        st.session_state.annotator = {
            "id": annotator_id,
            "education": education,
            "field": field,
        }
        st.session_state.group = group
        st.session_state.blocks = blocks

        # Pre-generate pairwise pairs for each set
        df = load_abstracts()
        for s in [1, 2, 3]:
            subset = get_abstracts_for_set(df, s)
            st.session_state.pairs[s] = generate_pairs(
                subset, N_PAIRWISE, seed=annotator_id * 100 + s
            )

        st.session_state.page = "block_intro"
        st.session_state.block_idx = 0
        st.rerun()


# ─── UI: Block Intro ─────────────────────────────────────────────────────────

def show_block_intro():
    idx = st.session_state.block_idx
    block = st.session_state.blocks[idx]
    method = block["method"]
    info = METHOD_INFO[method]

    # Count items in this block
    df = load_abstracts()
    subset = get_abstracts_for_set(df, block["set_number"])
    if method == "C":
        n_items = len(st.session_state.pairs[block["set_number"]])
    else:
        n_items = len(subset)

    st.markdown(f"# Block {idx + 1} of 3")
    st.markdown(
        f"### {info['icon']}  {info['name']}",
    )
    st.info(info["instruction"])
    st.markdown(f"**Items in this block:** {n_items}")
    st.markdown(f"**Abstract set:** Set {block['set_number']}")

    st.markdown("---")
    if st.button("▶️  Begin Block", type="primary", use_container_width=True):
        st.session_state.page = "annotation"
        st.session_state.item_idx = 0
        st.rerun()


# ─── UI: Annotation (Method A) ───────────────────────────────────────────────

def show_method_a(abstract_row, item_num, total_items):
    st.markdown(
        f"##### 🏷️ Classification — Item {item_num}/{total_items}"
    )
    st.progress(item_num / total_items)

    st.markdown(f"**{abstract_row['title']}**")
    st.caption(f"Discipline: {abstract_row['discipline']}")
    st.markdown(
        f"<div style='background:#f8f9fa; padding:16px; border-radius:8px; "
        f"border-left:4px solid #1565c0; margin:12px 0; line-height:1.6; color:#1a1a1a;'>"
        f"{abstract_row['text']}</div>",
        unsafe_allow_html=True,
    )

    # Use a unique key based on abstract id to avoid widget key conflicts
    key_prefix = f"a_{abstract_row['id']}"

    level = st.radio(
        "What is the **minimum academic level** needed to understand this abstract?",
        CLASSIFICATION_LEVELS,
        key=f"{key_prefix}_level",
        index=None,
    )

    justification = st.text_area(
        "Brief justification (optional)",
        key=f"{key_prefix}_just",
        height=68,
        placeholder="e.g., 'Uses terms like HSP70 and gene ontology that require biology training'",
    )

    return level, justification


# ─── UI: Annotation (Method B) ───────────────────────────────────────────────

def show_method_b(abstract_row, item_num, total_items):
    st.markdown(
        f"##### 📊 Scoring — Item {item_num}/{total_items}"
    )
    st.progress(item_num / total_items)

    st.markdown(f"**{abstract_row['title']}**")
    st.caption(f"Discipline: {abstract_row['discipline']}")
    st.markdown(
        f"<div style='background:#f8f9fa; padding:16px; border-radius:8px; "
        f"border-left:4px solid #e65100; margin:12px 0; line-height:1.6; color:#1a1a1a;'>"
        f"{abstract_row['text']}</div>",
        unsafe_allow_html=True,
    )

    key_prefix = f"b_{abstract_row['id']}"

    score = st.slider(
        "Rate difficulty (0 = trivial → 100 = incomprehensible)",
        min_value=0, max_value=100, value=50,
        key=f"{key_prefix}_score",
    )

    justification = st.text_area(
        "Brief justification (optional)",
        key=f"{key_prefix}_just",
        height=68,
        placeholder="e.g., 'Accessible language but assumes knowledge of clinical trial design'",
    )

    return score, justification


# ─── UI: Annotation (Method C) ───────────────────────────────────────────────

def show_method_c(left_row, right_row, item_num, total_items):
    st.markdown(
        f"##### ⚖️ Pairwise Comparison — Pair {item_num}/{total_items}"
    )
    st.progress(item_num / total_items)

    col_left, col_div, col_right = st.columns([5, 1, 5])

    with col_left:
        st.markdown("### Abstract A (Left)")
        st.markdown(f"**{left_row['title']}**")
        st.caption(f"Discipline: {left_row['discipline']}")
        st.markdown(
            f"<div style='background:#e3f2fd; padding:14px; border-radius:8px; "
            f"border-left:4px solid #1565c0; line-height:1.6; font-size:0.92em; color:#1a1a1a;'>"
            f"{left_row['text']}</div>",
            unsafe_allow_html=True,
        )

    with col_div:
        st.markdown(
            "<div style='display:flex; align-items:center; justify-content:center; "
            "height:300px; font-size:2em; color:#ccc;'>VS</div>",
            unsafe_allow_html=True,
        )

    with col_right:
        st.markdown("### Abstract B (Right)")
        st.markdown(f"**{right_row['title']}**")
        st.caption(f"Discipline: {right_row['discipline']}")
        st.markdown(
            f"<div style='background:#e8f5e9; padding:14px; border-radius:8px; "
            f"border-left:4px solid #2e7d32; line-height:1.6; font-size:0.92em; color:#1a1a1a;'>"
            f"{right_row['text']}</div>",
            unsafe_allow_html=True,
        )

    key_prefix = f"c_{left_row['id']}_{right_row['id']}"

    choice = st.radio(
        "Which abstract is **harder** to understand?",
        ["Left (A) is harder", "Right (B) is harder", "Tie — equally difficult"],
        key=f"{key_prefix}_choice",
        index=None,
    )

    justification = st.text_area(
        "Explain your reasoning (required)",
        key=f"{key_prefix}_just",
        height=80,
        placeholder="e.g., 'Left uses highly specialized physics terminology while right is more explanatory'",
    )

    return choice, justification


# ─── UI: Main Annotation Flow ────────────────────────────────────────────────

def show_annotation():
    idx = st.session_state.block_idx
    block = st.session_state.blocks[idx]
    method = block["method"]
    set_num = block["set_number"]
    item_idx = st.session_state.item_idx

    df = load_abstracts()
    subset = get_abstracts_for_set(df, set_num)

    if method == "C":
        pairs = st.session_state.pairs[set_num]
        total_items = len(pairs)
    else:
        total_items = len(subset)

    # ── Show the appropriate method UI ──
    response_value = None
    justification = ""

    if method == "A":
        row = subset.iloc[item_idx]
        response_value, justification = show_method_a(row, item_idx + 1, total_items)
    elif method == "B":
        row = subset.iloc[item_idx]
        response_value, justification = show_method_b(row, item_idx + 1, total_items)
    elif method == "C":
        pair = pairs[item_idx]
        left_row = df[df["id"] == pair[0]].iloc[0]
        right_row = df[df["id"] == pair[1]].iloc[0]
        response_value, justification = show_method_c(
            left_row, right_row, item_idx + 1, total_items
        )

    # ── Navigation ──
    st.markdown("---")
    nav_cols = st.columns([1, 1, 2])

    with nav_cols[0]:
        if item_idx > 0:
            if st.button("⬅️ Previous"):
                st.session_state.item_idx -= 1
                st.rerun()

    can_submit = response_value is not None
    if method == "C" and (not justification or not justification.strip()):
        can_submit = False

    with nav_cols[2]:
        is_last = item_idx >= total_items - 1
        btn_label = "Complete Block ✓" if is_last else "Next ➡️"

        if st.button(btn_label, type="primary", disabled=not can_submit):
            # Build response record
            record = {
                "annotator_id": st.session_state.annotator["id"],
                "education": st.session_state.annotator["education"],
                "field": st.session_state.annotator["field"],
                "group": st.session_state.group,
                "block_number": idx + 1,
                "method": method,
                "block_position": idx + 1,
                "timestamp": datetime.now().isoformat(),
            }

            if method in ("A", "B"):
                record["abstract_id"] = int(row["id"])
                record["abstract_title"] = row["title"]
                record["abstract_discipline"] = row["discipline"]
                record["abstract_id_2"] = ""
                record["response"] = response_value if response_value else ""
                record["justification"] = justification
            else:  # C
                left_id = int(pair[0])
                right_id = int(pair[1])
                record["abstract_id"] = left_id
                record["abstract_title"] = f"{left_row['title']} vs {right_row['title']}"
                record["abstract_discipline"] = f"{left_row['discipline']} / {right_row['discipline']}"
                record["abstract_id_2"] = right_id
                record["response"] = response_value if response_value else ""
                # Resolve which abstract was chosen as harder
                if response_value and "Left" in response_value:
                    record["harder_abstract_id"] = left_id
                elif response_value and "Right" in response_value:
                    record["harder_abstract_id"] = right_id
                else:
                    record["harder_abstract_id"] = "tie"
                record["justification"] = justification

            st.session_state.responses.append(record)

            if is_last:
                st.session_state.page = "block_done"
            else:
                st.session_state.item_idx += 1
            st.rerun()

    if not can_submit:
        if method == "C":
            st.caption("⬆️ Select a choice and provide justification to continue")
        else:
            st.caption("⬆️ Select a response to continue")


# ─── UI: Block Done ──────────────────────────────────────────────────────────

def show_block_done():
    idx = st.session_state.block_idx
    block = st.session_state.blocks[idx]
    info = METHOD_INFO[block["method"]]

    st.markdown(f"# ✅ Block {idx + 1} Complete!")
    st.success(f"{info['icon']} **{info['name']}** — all items answered.")

    if idx < 2:
        st.markdown(
            "Take a short break if you need one. When you're ready, "
            "continue to the next block."
        )
        st.markdown("---")
        if st.button(
            f"▶️  Start Block {idx + 2}", type="primary", use_container_width=True
        ):
            st.session_state.block_idx = idx + 1
            st.session_state.item_idx = 0
            st.session_state.page = "block_intro"
            st.rerun()
    else:
        st.markdown("You've completed all three blocks! 🎉")
        st.markdown("---")
        if st.button(
            "📋  View Results & Download", type="primary", use_container_width=True
        ):
            st.session_state.page = "complete"
            st.rerun()


# ─── UI: Complete ────────────────────────────────────────────────────────────

def show_complete():
    st.markdown("# 🎉 Thank You!")
    st.markdown(
        f"**Annotator {st.session_state.annotator['id']}** — you have completed "
        f"all 3 blocks with **{len(st.session_state.responses)} responses** recorded."
    )

    # Save to Google Sheets if configured
    if gsheets_configured():
        with st.spinner("Saving to Google Sheets..."):
            success = save_to_gsheets(st.session_state.responses)
        if success:
            st.success("✅ Responses saved to Google Sheets!")
        else:
            st.warning("⚠️ Could not save to Google Sheets. Please download CSV below.")
    else:
        st.info("💡 Google Sheets not configured. Download your responses as CSV below.")

    # CSV download
    csv_data = responses_to_csv(st.session_state.responses)
    st.download_button(
        label="📥 Download Responses (CSV)",
        data=csv_data,
        file_name=f"annotation_responses_annotator_{st.session_state.annotator['id']}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Preview
    st.markdown("---")
    st.markdown("### Response Preview")
    preview_df = pd.DataFrame(st.session_state.responses)
    display_cols = ["block_number", "method", "abstract_id", "response", "justification"]
    available = [c for c in display_cols if c in preview_df.columns]
    st.dataframe(preview_df[available], use_container_width=True)

    # Restart option
    st.markdown("---")
    if st.button("🔄 Start Over (new annotator)"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ─── Sidebar Progress ────────────────────────────────────────────────────────

def show_sidebar():
    if st.session_state.page == "registration":
        return

    with st.sidebar:
        st.markdown("### Progress")
        ann = st.session_state.annotator
        st.markdown(f"**Annotator:** {ann.get('id', '?')}")
        st.markdown(f"**Education:** {ann.get('education', '?')}")
        st.markdown(f"**Group:** {st.session_state.group}")
        st.markdown("---")

        for i, block in enumerate(st.session_state.blocks):
            info = METHOD_INFO[block["method"]]
            if i < st.session_state.block_idx:
                status = "✅"
            elif i == st.session_state.block_idx:
                status = "▶️"
            else:
                status = "⬜"
            st.markdown(f"{status} Block {i+1}: {info['icon']} {info['name']}")

        st.markdown("---")
        st.markdown(f"**Responses:** {len(st.session_state.responses)}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_state()
    show_sidebar()

    page = st.session_state.page
    if page == "registration":
        show_registration()
    elif page == "block_intro":
        show_block_intro()
    elif page == "annotation":
        show_annotation()
    elif page == "block_done":
        show_block_done()
    elif page == "complete":
        show_complete()


if __name__ == "__main__":
    main()
