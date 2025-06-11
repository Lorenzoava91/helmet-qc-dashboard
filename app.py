import streamlit as st
import pandas as pd
import openai
import plotly.express as px

# ───────────────────────────────────────────────────────
#  1. OPENAI KEY (hard-coded)
# ───────────────────────────────────────────────────────
openai.api_key = (
    "sk-proj-Jst_pmT3QYRMbNhu-0L_QtZR0aYKhWCqReMasP1JzyRmvE2VKPoJi8yg2ZYk8wc8u"
    "M8jrWg7eQT3BlbkFJRC4V8UeD-nQXkY5pGz3Zm0G9iINICl4p5w7tgRUS2KE6bqWnf6kBjFK9g"
    "X4anmkBJfDWvrJBwA"
)
client = openai.OpenAI(api_key=openai.api_key)

# ───────────────────────────────────────────────────────
#  2. PAGE TITLE
# ───────────────────────────────────────────────────────
st.title("Helmet Quality AI Dashboard (EN1078)")

# ───────────────────────────────────────────────────────
#  3. FILE UPLOAD
# ───────────────────────────────────────────────────────
st.header("Upload Excel files")
test_file   = st.file_uploader("Helmet Test Data (.xlsx)",   type="xlsx")
weight_file = st.file_uploader("Weight Limits (.xlsx)",      type="xlsx")

if not test_file or not weight_file:
    st.info("Upload *both* Excel files to continue.")
    st.stop()

# ───────────────────────────────────────────────────────
#  4. READ & CLEAN DATA
# ───────────────────────────────────────────────────────
test_df   = pd.read_excel(test_file)
weight_df = pd.read_excel(weight_file)

# strip spaces in headers
test_df.columns   = test_df.columns.str.strip()
weight_df.columns = weight_df.columns.str.strip()

# fix comma-decimal numbers in weight file
for col in ["Expected weight", "Weight Tollerance", "Max weight", "Min weight"]:
    if col in weight_df.columns:
        weight_df[col] = (
            weight_df[col].astype(str).str.replace(",", ".").str.replace(" ", "")
        ).replace("", pd.NA).astype(float)

# merge
df = test_df.merge(weight_df, on=["Model Code", "size"], how="left")
min_col, max_col = "Min weight_y", "Max weight_y"

# ───────────────────────────────────────────────────────
# 5. METRICS SNAPSHOT
# ───────────────────────────────────────────────────────
st.subheader("Automated Quality Snapshot")

total          = len(df)
n_en_fail      = (df["Peak G"] > 250).sum()
n_212_250      = ((df["Peak G"] > 212.5) & (df["Peak G"] <= 250)).sum()
checked_weight = df[min_col].notna().sum()
n_weight_oos   = ((df["weight"] < df[min_col]) | (df["weight"] > df[max_col])).sum()

st.markdown(
    f"""
* **EN1078 compliance:** {(100*(1-n_en_fail/total)):.2f}%  
* **Samples > 250 g:** {n_en_fail}  
* **Samples 212.5 – 250 g:** {n_212_250}  
* **Weight out of spec:** {n_weight_oos}/{checked_weight} ({(100*n_weight_oos/checked_weight if checked_weight else 0):.2f} %)  
"""
)

if n_en_fail:
    st.error(f"⚠️  EN1078 violations: {n_en_fail}")
if n_weight_oos:
    st.warning(f"⚠️  Weight out of spec: {n_weight_oos} samples")

# ───────────────────────────────────────────────────────
# 6. TOP-5 TABLES REQUESTED
# ───────────────────────────────────────────────────────
st.subheader("Top 5 – Highest single Peak G")
top_peak = (
    df.groupby(["Model Code", "size"])["Peak G"]
      .max()
      .reset_index()
      .sort_values("Peak G", ascending=False)
      .head(5)
)
st.dataframe(top_peak, hide_index=True)

st.subheader("Top 5 – Highest % out-of-spec weight")
w_stats = (
    df[df[min_col].notna()]
      .assign(oos=(df["weight"] < df[min_col]) | (df["weight"] > df[max_col]))
      .groupby(["Model Code", "size"])
      .agg(n=("weight","count"), bad=("oos","sum"))
      .assign(percent=lambda x: 100*x.bad/x.n)
      .sort_values("percent", ascending=False)
      .head(5)
      .reset_index()
)
st.dataframe(
    w_stats[["Model Code", "size", "percent", "bad", "n"]],
    hide_index=True,
    column_config={"percent": st.column_config.NumberColumn("Percent OOS (%)", format="%.1f")},
)

# ───────────────────────────────────────────────────────
# 7. QUICK CHART
# ───────────────────────────────────────────────────────
if "size" in df.columns:
    st.plotly_chart(
        px.box(df, x="Model Code", y="Peak G", color="size",
               points="outliers", title="Peak G distribution"),
        use_container_width=True,
    )

# ───────────────────────────────────────────────────────
# 8. AI ASSISTANT
# ───────────────────────────────────────────────────────
st.header("AI Assistant – ask anything about the dataset")

question = st.text_area("Your question")
if question:
    # tiny summary, to stay within token budget
    summary = (
        f"Columns: {list(df.columns)}\n"
        f"Rows: {len(df)}\n"
        f"Unique models: {df['Model Code'].nunique()}"
    )
    with st.spinner("AI is working…"):
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role":"system",
                    "content":"You are a quality-control expert for EN1078 helmets. "
                              "Answer based on the user's question and the pandas DataFrame summary."
                },
                {"role":"user", "content": f"{summary}\n\nQuestion:\n{question}"}
            ],
            temperature=0.2,
            max_tokens=500,
        )
    st.success(resp.choices[0].message.content)
