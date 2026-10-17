Browser
   │  POST /api/chat { session_id, question }
   ▼
app/main.py
   │  mounts static + routers
   ▼
app/api/routes_chat.py  ·  chat()
   │  get_or_create_session()
   │  runner = get_runner()
   ▼
app/graph/runner.py  ·  GraphRunner.invoke()
   │  _initial_state(session_id, question)
   │  graph.invoke(state)
   ▼
app/graph/builder.py  ·  LangGraph (ReAct Loop)
   │
   ├──► app/nodes/route.py  ·  route_node()
   │       │  classify(question)
   │       │       └─► app/routing/classifier.py
   │       │             ├─ FAST_RULES hit → no LLM
   │       │             └─ LLM classifier → intent
   │       │
   │       └─ if deterministic (greeting/identity):
   │             └─► app/routing/handlers.py
   │                   reply_for(intent)
   │                   → final_answer (skip LLM/tools entirely)
   │
   ├──► app/nodes/synthesize.py  ·  synthesize_node()  ◄───┐
   │       │  get_llm() → app/services/llm_factory.py      │
   │       │  (LLM is bound with tools from app/tools.py)  │
   │       │                                               │
   │       ├─ LLM decides to call a tool:                  │
   │       │     (Extracts metadata dynamically)           │
   │       │     returns { status: "needs_tool",           │
   │       │               messages: [AIMessage(tool_call)]} │
   │       │                                               │
   │       └─ LLM decides it has the answer:               │
   │             returns { draft_answer: "...",            │
   │                       status: "completed" }           │
   │                                                       │
   ├──► app/nodes/tool_node.py  ·  tool_node()             │
   │       │  Reads tool_call from state["messages"]       │
   │       │                                               │
   │       ├─ SLOT-FILLING ENFORCEMENT (Python Check):     │
   │       │  ├─ If search_documents called WITHOUT       │
   │       │  │  customer_name OR invoice_number:         │
   │       │  │    → Returns ToolMessage("Error: Ask user")│
   │       │  │    → Loops back to synthesize             │
   │       │  │                                            │
   │       │  └─ If metadata IS present:                  │
   │       │     Executes tool:                            │
   │       │                                               │
   │       └─ search_documents(query, name, invoice) ──────┼──► QDRANT VECTOR DB
   │       │                                               │    ├─ 1. Pre-filters by metadata
   │       │                                               │    │     (customer_name == 'Victoria')
   │       │                                               │    ├─ 2. Qwen Embedder (1024 dims)
   │       │                                               │    └─ 3. Cosine Similarity Search
   │       │                                               │
   │       └─ returns { messages: [ToolMessage(result)] } ─┘ (Loops back!)
   │
   ├──► app/nodes/validate.py  ·  validate_node()
   │       │  check non-empty, clean list blocks
   │       └─ if invalid → back to synthesize
   │
   └──► app/nodes/finalize.py  ·  finalize_node()
           │  record_run()
           │       └─► app/services/audit.py
           └─ END

   ▼
app/api/routes_chat.py
   │  append_turn(session_id, question, answer)
   │  return ChatResponse
   ▼
Browser  ·  static/js/app.js
   │  thinking.textContent = answer
   │  addSources(sources)
   ▼
Rendered answer



---------------------------------------Ingestion flow---------------------------------------------------------


Local Folder (1000+ PDFs)
   │
   ▼
build_qdrant_db.py
   │
   ├─ 1. Regex extracts metadata from filename:
   │       "invoice_Victoria Wilson_30489.pdf"
   │       → customer_name="Victoria Wilson"
   │       → invoice_number="30489"
   │
   ├─ 2. LlamaIndex SimpleDirectoryReader loads PDF text
   │
   ├─ 3. SentenceSplitter chunks text (chunk_size=512)
   │
   ├─ 4. Qwen Embedder converts chunks to 1024-dimensional vectors
   │
   └─ 5. Saves to QDRANT VECTOR DB (Docker)
           ├─ Vector (1024 floats)
           ├─ Text Chunk
           └─ Payload/Metadata (customer_name, invoice_number)