# build_vector_index.py
import os
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from utils.census_api import get_variables_json
from tqdm.auto import tqdm


# 1) Load ACS subject variables
vars_df = get_variables_json()

# 2) Create text field for embeddings
texts = vars_df["concept"].fillna("").unique().tolist()  # unique concepts to reduce duplicates

metadatas = []
ids = [str(i) for i in range(len(texts))]  # simple string IDs
for i, text in enumerate(texts):
    metadatas.append({
        "idx": i,  # simple index
        "concept": text,
    })

# 3) Embedding model (same family as before)
emb_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# 4) Create a persistent Chroma DB
persist_dir = "./census_var_concepts"
os.makedirs(persist_dir, exist_ok=True)

db = Chroma(
    embedding_function=emb_model,
    persist_directory=persist_dir,
)

# 4) Add in batches to avoid OOM
batch_size = 64  # adjust down if you still see memory issues

for start in tqdm(range(0, len(texts), batch_size), desc="Indexing"):
    end = start + batch_size
    batch_texts = texts[start:end]
    batch_ids = ids[start:end]
    batch_metas = metadatas[start:end]

    db.add_texts(
        texts=batch_texts,
        metadatas=batch_metas,
        ids=batch_ids,
    )

db.persist()
print("Built and saved vector index with", len(ids), "variables.")