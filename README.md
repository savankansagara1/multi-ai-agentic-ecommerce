# Multi-AI Agentic E-Commerce System

> Autonomous, production-grade e-commerce platform orchestrating specialized AI domain agents with **LangGraph**, **FastAPI**, **PostgreSQL**, and **Ollama**. Features stateful multi-turn sessions, a strict Human-in-the-Loop confirmation barrier for transactional safety, database-grounded policy RAG, and cross-user data isolation.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2-FF6F00?logo=langchain&logoColor=white)](https://www.langchain.com/langgraph)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-1.20-blue)](https://alembic.sqlalchemy.org/)
[![Ollama](https://img.shields.io/badge/LLM-gpt--oss:120b--cloud-black?logo=ollama&logoColor=white)](https://ollama.com/)

---

## Overview

Traditional e-commerce chatbots are often fragile: rule-based bots fail on natural language ambiguity, while unrestricted LLMs suffer from hallucinations, synthesize non-existent catalog items, invent fake discounts, or prematurely trigger irreversible state mutations like accidental orders and cart purges.

The **Multi-AI Agentic E-Commerce System** solves these challenges by implementing an **autonomous multi-agent architecture** built on top of [LangGraph](https://github.com/langchain-ai/langgraph). Rather than routing queries to a monolithic prompt with direct database tool bindings, the system decouples responsibilities across specialized domain graphs: **Product Discovery**, **Cart & Shopping Operations**, **Order Lifecycle Management**, and **Customer Support & Policy RAG**.

Every mutating action—adding to cart, updating quantities, clearing carts, placing orders, cancellations, and return requests—is governed by a deterministic **Human-in-the-Loop (HITL) confirmation barrier**. State-changing operations are intercepted, staged as pending actions, preserved across conversation turns via LangGraph checkpointing (`MemorySaver`), and executed only upon explicit user confirmation.

The system is deployed with a high-performance **FastAPI** backend, backed by **PostgreSQL** with declarative **Alembic** migrations and connection pooling, and paired with a responsive **React + Vite** shopping workspace. The frontend brings AI chat, the live cart, order tracking, product discovery, and grounded support articles into one polished interface.

## Frontend Preview

The React interface is built for desktop and mobile, with a conversational shopping assistant alongside account, cart, order, catalog, and help panels.

![Forma React shopping workspace](frontend-preview.png)

---

## Key Features

### Autonomous Multi-Agent Orchestration
- **Hybrid Intent Classification**: Low-latency regex pattern recognition handles explicit operations instantly; ambiguous queries fall back to an LLM-backed classifier.
- **Compound Multi-Intent Decomposition**: Queries spanning multiple domains (e.g., *"Show my cart and what is your return policy?"*) are decomposed, dispatched concurrently to respective subgraphs, and unified into a structured multi-section markdown response with child state preservation.
- **Second-Level Security & Unknown Handler**: Defends against prompt injections, SQL exfiltration attempts, and unauthorized record access without granting database or tool access to untrusted queries.

### Zero-Hallucination Guardrails
- **Authoritative Database Grounding**: The LLM never synthesizes products, prices, or inventory counts. Results are retrieved directly from PostgreSQL catalog tables and appended as authoritative verified records.
- **Fault-Tolerant Product Discovery**: Fuzzy matching with token normalization and typo tolerance (`difflib.get_close_matches`), regex-based budget constraint parsing (e.g., *"under 80k"*), and catalog category filtering.

### Transactional Safety & Human-in-the-Loop (HITL)
- **Pending Action Pattern**: Mutating operations do not alter database records immediately. They stage a `pending_action` in state, prompt the user with explicit parameters, and await unambiguous confirmation (`"yes"` vs. `"no"`).
- **Variant Disambiguation**: When multiple variants match a query (e.g., differing RAM or storage options), the agent presents numbered choices and holds the selection in state before staging cart additions.
- **Atomic Checkout**: Checkout verifies real-time inventory, calculates 18% GST and free shipping, decrements product variant stock atomically, records payment and shipment tracking records, clears the cart, and generates immutable audit log entries within a single ACID transaction.

### Customer Support & Grounded Policy RAG
- **Database-Backed RAG Retrieval**: Policy manuals, warranty rules, shipping guidelines, and troubleshooting instructions are stored as structured `DocumentChunk` records in PostgreSQL. Token scoring and phrase matching provide relevant context blocks to the model.
- **Human Escalation Pipeline**: Escalates unresolved complaints, damaged goods disputes, or explicit human representative requests by issuing unique support tickets (e.g., `TICKET-2026-XXXX`) and persisting audit trails.

### React Shopping Workspace
- **Conversational Shopping**: Chat with the multi-agent assistant, use suggested prompts, and review intent labels and confirmation requests in context.
- **Live Account Panels**: View and update cart quantities, follow recent orders, browse and search the product catalog, and expand store policy answers.
- **Responsive Layout**: A calm, accessible interface adapts from a two-panel desktop workspace to a compact mobile view.
- **Integrated Development Flow**: Vite proxies `/api` requests to FastAPI during frontend development; production builds are served by FastAPI from `/`.

### Enterprise Backend & Security
- **Strict User Tenancy**: Order details, shipment tracking, cart mutations, and returns are strictly scoped to the authenticated `user_id`. Queries targeting foreign order numbers return `404 Not Found` without information leakage.
- **Comprehensive Audit Logging**: All mutations (`ADD_TO_CART`, `UPDATE_CART_QUANTITY`, `REMOVE_FROM_CART`, `CHECKOUT`, `CANCEL_ORDER`, `REQUEST_RETURN`, `ESCALATE_TO_HUMAN`) write snapshots of old and new states to the `audit_logs` table.
- **Observability**: Native LangSmith integration (`LANGCHAIN_TRACING_V2=true`) for tracing token latency, agent transitions, and tool execution graphs.

---

## System Architecture

```mermaid
flowchart TD
    User([User / React Frontend / API Client]) -->|HTTP / JSON| FastAPI[FastAPI Application]
    FastAPI --> ChatRoute[/api/chat/]
    FastAPI --> RestRoutes["REST Endpoints (/api/products, /cart, /orders, /support)"]
    
    ChatRoute --> Orchestrator[LangGraph Orchestrator Graph]
    
    subgraph MultiAgentCore["Multi-AI Agent Core (LangGraph)"]
        RouterNode{Router Node}
        UnknownHandler[Unknown & Security Handler]
        MultiIntentNode[Multi-Intent Splitter & Aggregator]
        
        RouterNode -->|Single Domain: product| ProductGraph[Product Discovery Graph]
        RouterNode -->|Single Domain: shopping| ShoppingGraph[Shopping & Cart Graph]
        RouterNode -->|Single Domain: order| OrderGraph[Order Lifecycle Graph]
        RouterNode -->|Single Domain: support| SupportGraph[Support & Policy RAG Graph]
        RouterNode -->|Multi Domain: compound| MultiIntentNode
        RouterNode -->|Uncertain / Sensitive| UnknownHandler
        
        UnknownHandler -.->|Safe Semantic Handoff| RouterNode
        MultiIntentNode --> ProductGraph
        MultiIntentNode --> ShoppingGraph
        MultiIntentNode --> OrderGraph
        MultiIntentNode --> SupportGraph
    end
    
    subgraph ToolingAndServices["Domain Tools & Services"]
        ProductGraph --> ProductTools[Product Tools / ProductService]
        ShoppingGraph --> ShoppingTools[Shopping Tools / CartService]
        OrderGraph --> OrderTools[Order Tools / OrderService]
        SupportGraph --> SupportTools[Support Tools / SupportService]
    end
    
    subgraph PersistenceLayer["Database & Checkpointing (PostgreSQL & MemorySaver)"]
        Checkpointer[(LangGraph MemorySaver Checkpointer)]
        Checkpointer -.->|Thread Session State| MultiAgentCore
        
        ProductTools --> PostgreSQL[(PostgreSQL Database)]
        ShoppingTools --> PostgreSQL
        OrderTools --> PostgreSQL
        SupportTools --> PostgreSQL
        RestRoutes --> PostgreSQL
    end
    
    subgraph LLMRuntime["Inference & Observability"]
        Ollama[Local / Remote Ollama: gpt-oss:120b-cloud]
        LangSmith[LangSmith Tracing & Telemetry]
        
        MultiAgentCore --> Ollama
        FastAPI -.-> LangSmith
    end
```

---

## AI & Agent Architecture

The application implements a hierarchical graph design managed through [LangGraph](https://github.com/langchain-ai/langgraph). The graph state is formalized using `AgentState`:

```python
class AgentState(TypedDict, total=False):
    user_id: int
    message: str
    intent: str
    intents: list[str] | None
    redirect_intent: str | None
    cart_items: list[dict[str, Any]] | None
    messages: list[Any]
    response: Any
    pending_action: dict[str, Any] | None
    awaiting_confirmation: bool
    pending_domain: str | None
    active_options: list[dict[str, Any]] | None
    pending_quantity: int | None
    action_to_execute: dict[str, Any] | None
```

### Agent Domain Breakdown

| Agent / Subgraph | State & Node Pattern | Primary Responsibilities | Bound Tools / Services |
| :--- | :--- | :--- | :--- |
| **Orchestrator** | `StateGraph(AgentState)`<br>Nodes: `router`, `product`, `shopping`, `order`, `support`, `multi_intent`, `unknown` | Evaluates inputs, checks for ongoing confirmation loops, routes requests, aggregates compound answers. | `detect_intents()`, `resolve_unknown_request()` |
| **Product Graph** | `StateGraph(ProductAgentState)`<br>Nodes: `agent` | Catalog browsing, fuzzy model matching, price-range filtering, variant specs, product comparisons. | `ProductService.search_catalog()`, `ProductService.list_catalog()` |
| **Shopping Graph** | `StateGraph(AgentState)`<br>Cycle: `agent` ⇄ `tools` | Cart item additions, variant disambiguation, quantity updates, cart clears, 2-turn confirmation, checkout execution. | `view_cart`, `find_product_variants`, `add_to_cart`, `update_cart_quantity`, `remove_from_cart`, `clear_cart`, `checkout` |
| **Order Graph** | `StateGraph(AgentState)`<br>Cycle: `agent` ⇄ `tools` | Order history listing, order item breakdown, shipment tracking, cancellation (pre-dispatch), return & refund processing. | `get_user_orders`, `get_order_details`, `get_order_status`, `get_shipment_status`, `cancel_order`, `request_return` |
| **Support Graph** | `StateGraph(AgentState)`<br>Cycle: `agent` ⇄ `tools` | Grounded policy QA (returns, shipping, warranties), device troubleshooting, human support ticket generation. | `search_knowledge_base`, `escalate_to_human` |
| **Unknown & Security Handler** | Stateless evaluator (isolated prompt) | Intercepts small talk, prompt injection, SQL keywords, and secret exfiltration. Safely routes valid requests to domain graphs. | Isolated LLM prompt; zero tool and DB permissions |

---

## Important Workflows

### 1. Human-in-the-Loop (HITL) Mutation Flow

All mutating operations pass through a two-turn confirmation lifecycle to prevent accidental state modifications.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Router as Orchestrator Router
    participant Shopping as Shopping Graph
    participant State as MemorySaver (Session State)
    participant Tools as CartService / Database

    User->>Router: "Add ThinkBook Pro 8GB to my cart"
    Router->>Shopping: Route to shopping domain
    Shopping->>Tools: Lookup active variants (find_product_variants)
    Tools-->>Shopping: Single variant found (TBP-8-512, Stock: 10)
    Shopping->>State: Store pending_action & awaiting_confirmation=True
    Shopping-->>User: "I found ThinkBook Pro (8GB RAM / 512GB SSD) at ₹74,999.00. Would you like me to add 1 item(s) to your cart?"
    
    Note over User, Router: Next turn - User responds to confirmation
    User->>Router: "yes"
    Router->>Router: Detect awaiting_confirmation=True -> Bypass router to 'pending_domain'
    Router->>Shopping: Forward "yes" with preserved state
    Shopping->>Tools: Invoke add_to_cart(variant_id, qty)
    Tools->>Tools: Insert CartItem & write AuditLog (Commit)
    Tools-->>Shopping: Success payload
    Shopping->>State: Reset pending_action=None, awaiting_confirmation=False
    Shopping-->>User: "Added 1 unit(s) of ThinkBook Pro (8GB RAM / 512GB SSD) to your cart successfully."
```

### 2. Disambiguation Flow (Variant Selection)

When a shopper requests a product that has multiple active specifications, the agent resolves ambiguity before staging the mutation.

```mermaid
flowchart TD
    A[Shopper: 'Add ThinkBook Pro to my cart'] --> B[Shopping Agent: Queries Catalog]
    B --> C{Variant Count > 1?}
    C -->|Yes| D[Store active_options in State<br>1: 8GB / 512GB SSD @ ₹74,999<br>2: 16GB / 1TB SSD @ ₹89,999]
    D --> E[Assistant prompts shopper to select option by number or name]
    E --> F[Shopper: '1']
    F --> G[Orchestrator detects active_options -> Routes to shopping]
    G --> H[Extracts Variant #1 -> Stages pending_action]
    H --> I[Assistant asks for final confirmation: 'Reply yes to confirm']
    I --> J[Shopper: 'yes']
    J --> K[Tools Node: Executes add_to_cart -> Database Updated]
```

### 3. Atomic Checkout & Inventory Decrement

```mermaid
flowchart TD
    A[User Confirms: 'yes' to Checkout] --> B[CartService.checkout]
    subgraph ACID_Transaction["Atomic PostgreSQL Transaction"]
        B --> C[Validate Cart items exist]
        C --> D[Validate Variant active status & stock availability]
        D -->|Insufficient Stock| E[Raise ValueError & Rollback]
        D -->|Sufficient Stock| F[Calculate Subtotal, 18% GST, Free Shipping]
        F --> G[Create Order Record]
        G --> H[Create OrderItem Snapshots]
        H --> I[Decrement ProductVariant.stock_quantity]
        I --> J[Delete Items from Cart]
        J --> K[Create Completed Payment UPI Record]
        K --> L[Create Manifested Shipment Record]
        L --> M[Write AuditLog Record]
        M --> N[DB Session Commit]
    end
    N --> O[Return Order Number, Tracking ID, Delivery ETA]
```

### 4. Multi-Intent Decomposition Workflow

```mermaid
flowchart LR
    A["User: 'Show my cart and what is your return policy?'"] --> B[detect_intents]
    B -->|Matches 'shopping' + 'support'| C[multi_intent Node]
    
    subgraph ParallelExecution["Sub-Graph Execution"]
        C --> D[Shopping Graph: Retrieves Cart Items & Total]
        C --> E[Support Graph: RAG Search on Policy Chunks]
    end
    
    D --> F[Format '🛒 Shopping Cart' Markdown Section]
    E --> G[Format 'ℹ️ Customer Support & Policies' Markdown Section]
    F --> H[Merge into unified markdown response]
    G --> H
    H --> I[Return compound answer to User]
```

---

## Safety & Confirmation Architecture

The system enforces a strict separation between **read-only operations** and **mutating operations**:

```
Read Operations (Catalog search, View Cart, Order status, Policy search)
└── Execute immediately via tools → Render formatted response

Mutating Operations (Add to cart, Update quantity, Remove item, Clear cart, Checkout, Cancel order, Request return)
├── 1. Validation: Verify target existence and business constraints (e.g., stock > requested, order is delivered).
├── 2. Staging: Construct a structured pending_action dictionary with all required tool parameters.
├── 3. User Interruption: Set awaiting_confirmation = True and return an explicit prompt.
├── 4. Routing Bypass: On next turn, if awaiting_confirmation is true, skip domain classification and forward directly to the staging agent.
├── 5. Evaluation:
│    ├── Affirmative ("yes", "confirm", "proceed"): Hand off to tools node, execute database mutation, clear pending action.
│    ├── Negative ("no", "cancel", "abort"): Discard pending action, reset state, notify user that state remains unchanged.
│    └── Ambiguous: Re-prompt the user without executing any mutation.
└── 6. Traceability: Emit an AuditLog record containing user_id, action, entity, and state delta.
```

### Injection & Exfiltration Defense

`unknown_handler.py` provides defense against prompt injection, privilege escalation, and schema extraction attacks:
- **Heuristic Pattern Shield**: Intercepts requests containing keywords like `database`, `credentials`, `passwords`, `secrets`, `api keys`, `system prompts`, or SQL tokens (`SELECT`, `INSERT`, `UPDATE`, `DELETE`).
- **Zero-Access Sandbox**: The unknown handler operates with an isolated prompt and zero database sessions or tool bindings.
- **Audited Verification**: Verified via automated test cases in `tests/test_unknown_intent.py` and visualized in `image.png`.

---

## Authentication & Authorization

### Multi-User Isolation
The system enforces resource-level tenancy in all database operations:
- Every cart, order, payment, and return operation requires a validated `user_id`.
- `OrderService._find_user_order()` strictly applies `where(Order.user_id == user_id, ...)` using parameterized SQLAlchemy criteria.
- **Cross-Account Protection**: Attempting to query or manipulate an order belonging to another customer returns `None` / `404 Not Found`. It never confirms order existence or leaks customer details.
- Verified by automated regression test `test_21_cross_user_order_isolation_security`.

---

## Database Architecture

The PostgreSQL schema is managed via SQLAlchemy 2.0 ORM models and version-controlled with Alembic migrations.

### Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ ADDRESSES : "has"
    USERS ||--o{ CARTS : "owns"
    USERS ||--o{ WISHLISTS : "saves"
    USERS ||--o{ ORDERS : "places"
    USERS ||--o{ REVIEWS : "writes"
    USERS ||--o{ RETURNS : "requests"
    USERS ||--o{ AUDIT_LOGS : "triggers"

    CATEGORIES ||--o{ PRODUCTS : "classifies"
    PRODUCTS ||--o{ PRODUCT_VARIANTS : "has"
    PRODUCTS ||--o{ PRODUCT_DOCUMENTS : "documents"
    PRODUCT_DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "chunked into"

    CARTS ||--o{ CART_ITEMS : "contains"
    PRODUCT_VARIANTS ||--o{ CART_ITEMS : "referenced by"

    ORDERS ||--o{ ORDER_ITEMS : "contains"
    ORDERS ||--o{ PAYMENTS : "paid via"
    ORDERS ||--o{ SHIPMENTS : "fulfilled via"
    ORDERS ||--o{ RETURNS : "returned via"

    PRODUCT_VARIANTS ||--o{ ORDER_ITEMS : "snapshot of"
    SHIPMENTS ||--o{ SHIPMENT_ITEMS : "tracks"
    ORDER_ITEMS ||--o{ SHIPMENT_ITEMS : "linked to"

    RETURNS ||--o{ RETURN_ITEMS : "items"
    RETURNS ||--o{ REFUNDS : "triggers"
    ORDER_ITEMS ||--o{ RETURN_ITEMS : "returned"
```

### Key Schema Entities & Constraints

- **`categories`**: Product classifications with unique slugs (`name`, `slug`).
- **`products`**: Parent items with brands, ratings, and flexible `JSONB` specifications.
- **`product_variants`**: Purchasable SKUs with dedicated pricing, discounts, stock counts, and JSON specifications (`CASCADE` on product delete).
- **`carts` & `cart_items`**: Active user carts with item quantities and timestamps.
- **`orders` & `order_items`**: Finalized purchases preserving immutable historical pricing, discounts, and JSON snapshots of the shipping address.
- **`payments` & `shipments`**: Transaction reference codes, statuses, tracking numbers, carriers (e.g., Delhivery, BlueDart), and delivery milestones.
- **`returns`, `return_items`, `refunds`**: Governed by a 7-day post-delivery eligibility window, tracking reasons and refund statuses.
- **`product_documents` & `document_chunks`**: Knowledge base repository for RAG containing document types, chunk indices, SHA-256 content hashes, and metadata.
- **`audit_logs`**: Immutable ledger recording `user_id`, `action`, `entity_type`, `old_value` (`JSONB`), `new_value` (`JSONB`), and timestamp.

---

## Tech Stack

| Layer | Technology | Version | Purpose in Repository |
| :--- | :--- | :--- | :--- |
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) | 0.141.1 | High-performance asynchronous REST API framework serving chat & e-commerce endpoints. |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) | 0.53.0 | Production ASGI web server running FastAPI. |
| **Agent Framework** | [LangGraph](https://www.langchain.com/langgraph) | 1.2.12 | Stateful graph orchestration for routing, agent nodes, cycles, and multi-turn loops. |
| **LLM Orchestration** | [LangChain](https://www.langchain.com/) | 1.4.2 | Agent tool abstractions (`@tool`), structured output parsing, and prompts. |
| **LLM Runtime** | [Ollama (ChatOllama)](https://github.com/ollama/ollama) / `gpt-oss:120b-cloud` | 1.1.0 | Local/remote LLM provider for zero-temperature intent routing and grounded responses. |
| **Database** | [PostgreSQL](https://www.postgresql.org/) | 16 | Relational database holding catalog, users, carts, orders, shipments, and RAG chunks. |
| **ORM** | [SQLAlchemy](https://www.sqlalchemy.org/) | 2.0.54 | Python SQL toolkit and Object Relational Mapper using mapped attributes & connection pooling. |
| **DB Driver** | [psycopg](https://www.psycopg.org/) | 3.3.6 | Modern PostgreSQL database adapter for Python. |
| **Database Migrations**| [Alembic](https://alembic.sqlalchemy.org/) | 1.20.0 | Declarative database migration versioning. |
| **Data Validation** | [Pydantic](https://docs.pydantic.dev/) | 2.13.5 | Strict schema validation for request payloads and structured LLM extractors. |
| **Frontend UI** | React / Vite | - | Responsive shopping workspace with AI chat, cart, orders, product discovery, and support. |
| **Markdown Rendering** | [React Markdown](https://github.com/remarkjs/react-markdown) | - | Renders structured assistant responses in the React chat. |
| **Observability** | [LangSmith](https://smith.langchain.com/) | 0.14.0 | Real-time agent execution tracing, latency monitoring, and tool invocation graphs. |
| **Testing** | [unittest](https://docs.python.org/3/library/unittest.html) & TestClient | 3.12 | Automated test suite verifying offline unit mocks and end-to-end integration flows. |

---

## Project Structure

```text
multi-ai-agentic-ecommerce/
├── alembic/                          # Alembic database migration environment
│   ├── env.py                        # Migration runner connecting SQLAlchemy metadata
│   └── versions/                     # Versioned migration revision scripts
│       ├── be52286c20d4_create_product_catalog_tables.py
│       └── 29213096efec_add_ecommerce_domain_tables.py
├── app/                              # Core application source code
│   ├── api/                          # REST API routing layer
│   │   └── routes/
│   │       ├── cart.py               # Cart inspection, item management, and checkout
│   │       ├── chat.py               # Conversational agent endpoint (/api/chat/)
│   │       ├── orders.py             # Order history, detail inspection, cancel, returns
│   │       ├── products.py           # Product catalog lookup and search
│   │       └── support.py            # RAG policy search, FAQ retrieval, human escalation
│   ├── agents/                       # LangGraph multi-agent implementation
│   │   ├── state.py                  # TypedDict AgentState definition
│   │   ├── router.py                 # Hybrid regex + LLM intent classifier
│   │   ├── orchestrator.py           # Top-level orchestrator StateGraph builder
│   │   ├── main_graph.py             # LangGraph Studio entry point (graph instance)
│   │   ├── unknown_handler.py        # Safety handler, prompt injection defense & fallback
│   │   ├── product_graph.py          # Product discovery graph & catalog formatter
│   │   ├── product_agent.py          # Product LLM setup & tool binding
│   │   ├── shopping_graph.py         # Shopping cart graph with confirmation cycles
│   │   ├── shopping_agent.py         # Shopping agent structured output extractors
│   │   ├── order_graph.py            # Order management graph with return/cancel flows
│   │   ├── order_agent.py            # Order agent structured query extractors
│   │   ├── support_graph.py          # Customer support RAG & escalation graph
│   │   └── support_agent.py          # Support LLM agent definition
│   ├── db/                           # Database configurations & models
│   │   ├── database.py               # Engine, SessionLocal, and get_db dependency
│   │   ├── seed.py                   # Catalog, order, and knowledge base seed script
│   │   ├── create_test_user.py       # Helper script to provision baseline test user
│   │   └── models/                   # SQLAlchemy ORM declarative models
│   │       ├── base.py               # Base class declarative metadata
│   │       ├── user.py               # User account entity
│   │       ├── product.py            # Category, Product, ProductVariant
│   │       ├── shopping.py           # Address, Cart, CartItem, Wishlist
│   │       ├── order.py              # Order, OrderItem, Payment, Shipment, ShipmentItem
│   │       └── support.py            # Return, ReturnItem, Refund, Review, ProductDocument, DocumentChunk, AuditLog
│   ├── schemas/                      # Pydantic validation schemas
│   │   ├── agent.py                  # Structured extraction & intent classification models
│   │   └── product.py                # Product and variant API response schemas
│   ├── services/                     # Database-backed business logic services
│   │   ├── cart_service.py           # Cart operations, atomic checkout, audit logging
│   │   ├── order_service.py          # Scoped order retrieval, cancellations, returns
│   │   ├── product_service.py        # Tokenizer, fuzzy search, price filters, catalog
│   │   └── support_service.py        # RAG scoring over document chunks, ticket creation
│   ├── tools/                        # LangChain tool bindings wrapping services
│   │   ├── product_tools.py          # search_products tool
│   │   ├── shopping_tools.py         # Cart management & checkout tools
│   │   ├── order_tools.py            # Order lookup, tracking, cancellation, return tools
│   │   └── support_tools.py          # RAG search & human escalation tools
│   └── main.py                       # FastAPI entry point, routers, health checks, React build mount
├── frontend/                         # React + Vite web application
│   ├── src/App.jsx                   # Chat, cart, orders, catalog, and support workspace
│   ├── src/styles.css                # Responsive application styling
│   ├── src/main.jsx                  # React application entry point
│   ├── index.html                    # Vite HTML entry point
│   └── vite.config.js                # Development API proxy and build config
├── frontend-preview.png              # Screenshot of the React shopping workspace
├── examples/                         # Developer demos & diagnostic test scripts
│   ├── agent_demos/                  # Independent runnable agent demos
│   ├── diagnostics/                  # Smoke tests for routing & graph compilation
│   ├── graphs/                       # Minimal LangGraph reference implementations
│   └── tool_demos/                   # Direct tool execution demonstrations
├── tests/                            # Automated test suite
│   ├── test_unknown_intent.py        # Unit tests for security handler & routing
│   ├── test_product_responses.py     # Unit tests for catalog grounding & comparisons
│   ├── test_shopping_and_orders.py   # Integration tests for cart, orders, and HITL
│   └── test_support_and_api.py       # Integration tests for RAG, checkout, and REST APIs
├── alembic.ini                       # Alembic configuration
├── langgraph.json                    # LangGraph Studio service configuration
├── .env.example                      # Environment template
└── README.md                         # Project documentation
```

---

## API Documentation

All routes are mounted under `/api` (with `/products` duplicated at root for backward compatibility).

### Agent Chat Endpoint

| Method | Endpoint | Description | Request Body |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/chat/` | Invokes the multi-agent graph with thread-level session memory and HITL state. | `{"message": str, "user_id": int = 1, "thread_id": str = "session_default"}` |

### Shopping Cart Endpoints

| Method | Endpoint | Description | Query / Body Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/cart/` | Retrieve current shopping cart and line totals for a user. | `user_id: int = 1` |
| `POST` | `/api/cart/items` | Add a product variant to the cart after stock validation. | `{"variant_id": int, "quantity": int = 1, "user_id": int = 1}` |
| `PUT` | `/api/cart/items/{variant_id}` | Update quantity of a variant already in the cart. | `{"quantity": int, "user_id": int = 1}` |
| `DELETE` | `/api/cart/items/{variant_id}` | Remove a variant completely from the cart. | `user_id: int = 1` |
| `DELETE` | `/api/cart/` | Clear all items from the user's cart. | `user_id: int = 1` |
| `POST` | `/api/cart/checkout` | Execute atomic checkout: deducts stock, creates order & payment, and clears cart. | `{"user_id": int = 1, "shipping_address": dict \| null}` |

### Orders & Tracking Endpoints

| Method | Endpoint | Description | Query / Body Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/orders/` | Retrieve recent order history strictly scoped to user. | `user_id: int = 1, limit: int = 10` |
| `GET` | `/api/orders/{order_identifier}` | Retrieve detailed order breakdown (items, payments, shipments). | `user_id: int = 1` |
| `GET` | `/api/orders/{order_identifier}/tracking` | Retrieve live shipment milestones, carrier, and tracking ID. | `user_id: int = 1` |
| `POST` | `/api/orders/{order_identifier}/cancel` | Cancel an eligible pre-dispatch order. | `{"user_id": int = 1, "reason": str}` |
| `POST` | `/api/orders/{order_identifier}/return` | Request return and refund for an eligible delivered order (7-day window). | `{"user_id": int = 1, "reason": str}` |

### Product Catalog Endpoints

| Method | Endpoint | Description | Query / Body Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/products/` | Search catalog items by keyword or retrieve full list. | `q: str \| null, limit: int = 10` |
| `GET` | `/api/products/{product_id}` | Retrieve complete details and active variants for a product. | Path: `product_id: int` |

### Customer Support & RAG Endpoints

| Method | Endpoint | Description | Query / Body Params |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/support/faqs` | Retrieve knowledge base articles formatted as self-service FAQs. | None |
| `GET` | `/api/support/search` | Search knowledge base chunks using token-scored relevance. | `q: str, limit: int = 4` |
| `POST` | `/api/support/escalate` | Escalate an unresolved issue to a human support specialist ticket. | `{"user_id": int = 1, "issue_description": str, "reason": str}` |

### System Health Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the production React frontend build. |
| `GET` | `/health` | Reports overall service status, version, and active agents. |
| `GET` | `/health/db` | Executes `SELECT 1` to verify live PostgreSQL database connectivity. |

---

## Example Usage

### 1. Conversational Product Comparison
```bash
curl -X POST "http://localhost:8000/api/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Compare ThinkBook Pro and Galaxy Pro",
    "user_id": 1,
    "thread_id": "session_demo_01"
  }'
```
**Response:**
```json
{
  "response": "The ThinkBook Pro is a productivity laptop featuring an Intel Core i7 processor and up to 1TB SSD storage, whereas the Galaxy Pro is an Android smartphone equipped with a 6.7-inch AMOLED display and a 50MP camera.\n\n- Galaxy Pro — 128GB; ₹54,999.00; 20 in stock; SKU SGP-128\n- ThinkBook Pro — 8GB RAM / 512GB SSD; ₹74,999.00; 10 in stock; SKU TBP-8-512",
  "intent": "product",
  "awaiting_confirmation": false,
  "pending_action": null,
  "thread_id": "session_demo_01"
}
```

### 2. Multi-Turn HITL Cart Addition
**Turn 1: Requesting an action**
```bash
curl -X POST "http://localhost:8000/api/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Add ThinkBook Pro 8GB to my cart",
    "user_id": 1,
    "thread_id": "session_demo_02"
  }'
```
**Response (Awaiting Confirmation):**
```json
{
  "response": "I found ThinkBook Pro (8GB RAM / 512GB SSD) at ₹74,999.00. Would you like me to add 1 item(s) to your cart?",
  "intent": "shopping",
  "awaiting_confirmation": true,
  "pending_action": {
    "tool": "add_to_cart",
    "args": {
      "user_id": 1,
      "product_variant_id": 1,
      "quantity": 1
    },
    "summary": "adding 1 unit(s) of ThinkBook Pro (8GB RAM / 512GB SSD)",
    "product_name": "ThinkBook Pro",
    "variant_name": "8GB RAM / 512GB SSD"
  },
  "thread_id": "session_demo_02"
}
```

**Turn 2: Confirming the transaction**
```bash
curl -X POST "http://localhost:8000/api/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "yes",
    "user_id": 1,
    "thread_id": "session_demo_02"
  }'
```
**Response (Mutation Executed):**
```json
{
  "response": "Added 1 unit(s) of ThinkBook Pro (8GB RAM / 512GB SSD) to your cart successfully.",
  "intent": "shopping",
  "awaiting_confirmation": false,
  "pending_action": null,
  "thread_id": "session_demo_02"
}
```

### 3. Compound Multi-Intent Query
```bash
curl -X POST "http://localhost:8000/api/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show my cart and what is your return policy?",
    "user_id": 1,
    "thread_id": "session_demo_03"
  }'
```
**Response (Decomposed & Merged):**
```json
{
  "response": "### 🛒 Shopping Cart\nYour shopping cart:\n1. ThinkBook Pro (8GB RAM / 512GB SSD) - 1 × ₹74,999.00 = ₹74,999.00\n\nTotal: ₹74,999.00 (1 item(s))\n\n---\n\n### ℹ️ Customer Support & Policies\nEligible items can be returned or replaced within 7 calendar days of delivery in their original packaging. Refunds are credited to the original payment method within 5 to 7 business days.",
  "intent": "multi_intent",
  "awaiting_confirmation": false,
  "pending_action": null,
  "thread_id": "session_demo_03"
}
```

---

## Installation & Setup

### Prerequisites
- **Python 3.12+**
- **PostgreSQL 14+** (running on port 5432)
- **Ollama** installed with model `gpt-oss:120b-cloud` pulled (or configure your own local Ollama model in `app/agents/`)

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/savankansagara1/multi-ai-agentic-ecommerce.git
cd multi-ai-agentic-ecommerce

# Create virtual environment using Python 3.12 or uv
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r <(python -c "
import importlib.metadata
") 2>/dev/null || pip install fastapi uvicorn langgraph langchain langchain-ollama sqlalchemy psycopg[binary] alembic pydantic python-dotenv langsmith httpx
```
*(If you use `uv`, you can run `uv sync` or `uv pip install -e .`)*

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```
Update `.env`:
```env
DATABASE_URL=postgresql+psycopg://ecommerce_app:YOUR_PASSWORD@localhost:5432/ecommerce_db

# Optional: LangSmith Telemetry & Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=multi-ai-agentic-ecommerce
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 4. Database Setup & Migrations
Create the PostgreSQL database user and database, then apply Alembic migrations:
```bash
# Run migrations up to the latest revision
alembic upgrade head
```

### 5. Seed Initial Data
Populate the database with sample products, categories, variants, historical orders, and support documents:
```bash
python -m app.db.seed
python -m app.db.create_test_user
```

### 6. Start Application
Build the React frontend once so FastAPI can serve it from `/`:
```bash
cd frontend
npm ci
npm run build
cd ..
```

For frontend development with hot reload, run `npm run dev` from `frontend/` in a separate terminal. Vite proxies `/api` requests to `http://localhost:8000`.

Then start the backend:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **Web UI**: Open `http://localhost:8000` in your browser.
- **Interactive OpenAPI Docs**: Navigate to `http://localhost:8000/docs`.

### 7. LangGraph Studio Setup (Optional)
This repository includes a native `langgraph.json` manifest. You can inspect and debug agent graphs visually:
```bash
langgraph dev
```

---

## Environment Variables

| Variable | Required | Default / Example | Purpose |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | **Yes** | `postgresql+psycopg://user:pass@localhost:5432/ecommerce_db` | Connection string for PostgreSQL via `psycopg` v3 driver. |
| `LANGCHAIN_TRACING_V2` | No | `true` | Enables distributed trace recording to LangSmith. |
| `LANGCHAIN_API_KEY` | No | `lsv2_pt_...` | API Key for LangSmith tracing platform. |
| `LANGCHAIN_PROJECT` | No | `multi-ai-agentic-ecommerce` | Target workspace project identifier in LangSmith. |
| `LANGCHAIN_ENDPOINT` | No | `https://api.smith.langchain.com` | LangSmith telemetry collection endpoint. |

---

## Testing

The project includes unit tests with mocked LLM providers and integration test suites that run against the PostgreSQL database.

```bash
# Run the entire test suite
python -m unittest discover -s tests -v
```

### Test Suite Organization

| Test File | Type | What is Verified |
| :--- | :--- | :--- |
| `tests/test_unknown_intent.py` | Unit (Offline Mocks) | Security boundaries, rejection of database credential dumps, prompt injection defenses, capability summaries, and safe intent handoffs. |
| `tests/test_product_responses.py` | Unit (Offline Mocks) | Catalog grounding, zero-hallucination comparison format, and empty-result handling. |
| `tests/test_shopping_and_orders.py` | Integration (DB-Backed) | 22 comprehensive test cases: cart view, pending action staging, stock limits, variant disambiguation, confirmation `"yes"`/`"no"`, session thread persistence, order tracking, and cross-user data isolation. |
| `tests/test_support_and_api.py` | Integration (DB & API) | 20 comprehensive test cases: RAG policy retrieval, human escalation tickets, atomic checkout inventory decrement, 7-day return policy window, compound multi-intent execution, and all FastAPI endpoints. |

To run the offline unit tests independently without a database:
```bash
python -m unittest tests/test_unknown_intent.py tests/test_product_responses.py -v
```

---

## Engineering Highlights

1. **Stateful Graph Orchestration over Fragile Chains**: Replaces unpredictable single-prompt LLM agents with explicit StateGraphs in LangGraph. State transitions, tool dispatching, and error fallbacks follow deterministic graph edges.
2. **Deterministic Human-in-the-Loop Barrier**: State-modifying operations (cart adjustments, purchases, order cancellations, return claims) cannot execute in a single prompt turn. They require explicit two-turn user confirmation, eliminating accidental actions.
3. **Multi-Turn Thread Persistence via MemorySaver**: Checkpointing preserves ongoing confirmation requests, pending actions, and active variant options across turns using a client-provided `thread_id`.
4. **Zero-Hallucination Database Grounding**: The LLM is restricted to crafting natural language explanations from verified PostgreSQL records. It never invents products, specs, stock figures, or pricing.
5. **ACID-Compliant Atomic Checkout**: Checkout verifies stock, decrements inventory, creates payment and shipment records, clears the shopping cart, and writes an audit log in a single transaction, preventing overselling and race conditions.
6. **Strict Multi-User Isolation**: Resource access is strictly scoped to the authenticated `user_id`. Queries for foreign order numbers return `404 Not Found` without information leakage.
7. **Hybrid Intent Routing**: Combines regex parsing for zero-latency deterministic routing with LLM-backed classification for conversational flexibility.

---

## Technical Challenges & Solutions

### 1. Eliminating Inventory & Pricing Hallucinations
- **Challenge**: Generative LLMs routinely invent plausible-sounding specifications, fabricate non-existent products, or misquote prices when summarizing large product sets.
- **Solution**: The LLM is stripped of raw database write access. `ProductService` queries PostgreSQL directly using fuzzy token normalization (`difflib.get_close_matches`) and regex-based budget parsing. Only verified database rows are passed to the model, and authoritative catalog lines are automatically appended to the response.
- **Result**: Zero invented SKUs, zero price discrepancies, and verified inventory counts.

### 2. Preventing Accidental State Changes
- **Challenge**: Standard tool-calling agents immediately execute functions upon detecting an intent. A casual user phrase like *"I want to buy ThinkBook"* could immediately place an order or drain a balance.
- **Solution**: Engineered a two-stage **Pending Action Pattern**. Mutating nodes stage a dictionary containing the tool name, arguments, and human-readable summary in `AgentState`, set `awaiting_confirmation=True`, and interrupt execution. On the next turn, affirmative words (`yes`, `confirm`, `proceed`) trigger the tools node, while negative words (`no`, `cancel`) purge the pending state.
- **Result**: Complete prevention of accidental purchases, cart overwrites, or order cancellations.

### 3. Compound Query Disambiguation & Aggregation
- **Challenge**: Shoppers often combine distinct domain questions in a single turn (e.g., *"Show my cart and what is your return policy?"*). Single-agent systems misclassify these queries or drop one of the tasks.
- **Solution**: Built a compound intent detector that recognizes multi-domain patterns. The `multi_intent_node` dispatches sub-queries to domain subgraphs, stitches their outputs into clean markdown sections, and preserves child workflow state for subsequent turns.
- **Result**: Seamless compound query resolution without dropped context or routing failures.

---

## Design Decisions

- **Why LangGraph instead of LangChain AgentExecutor?** LangGraph provides first-class support for cyclical graphs, explicit conditional edges, granular state schemas (`AgentState`), and checkpointing (`MemorySaver`). This allows deterministic control over routing loops and human-in-the-loop interruptions that are difficult to manage with linear chains.
- **Why Separate the Agent and Tools into Distinct Nodes?** Isolating reasoning (`agent_node`) from execution (`tools_node`) enables state interception. The agent plans the mutation and formats the prompt, but the actual database write is guarded by a conditional edge (`should_call_tools`) that checks confirmation status.
- **Why Hybrid Regex + LLM Intent Routing?** Pure LLM routing introduces 400–1200ms of unnecessary latency for simple commands like *"view cart"* or *"cancel ORD-2026-1001"*. Regex handles clear operations in sub-millisecond time, preserving the LLM for ambiguous or natural language inquiries.
- **Why PostgreSQL-Backed RAG Chunks over an External Vector Store?** For standard store documentation, warranty policies, and troubleshooting guides, database-stored chunks with token scoring and phrase matching provide fast retrieval with zero external infrastructure dependencies or vector synchronization drift.

---

## Future Improvements

- [ ] **OAuth2 & JWT Authentication**: Replace user ID parameters with Bearer token authentication middleware and role-based access control (RBAC).
- [ ] **Hybrid Vector Search (pgvector)**: Integrate `pgvector` inside PostgreSQL to combine exact keyword matching with semantic vector embeddings for product search.
- [ ] **Distributed Redis Checkpointer**: Upgrade LangGraph memory persistence from in-memory `MemorySaver` to a distributed Redis or PostgreSQL checkpointer for multi-instance horizontal scaling.
- [ ] **Containerization**: Add multi-stage `Dockerfile` and `docker-compose.yml` configurations with PostgreSQL and Ollama services.
- [ ] **Asynchronous Webhooks**: Implement asynchronous background task workers (Celery / ARQ) for courier delivery webhooks and automated refund settlements.

---

## Author & Demo

- **Author**: Savan Kansagara ([important.savan@gmail.com](mailto:important.savan@gmail.com))
- **Repository**: [savankansagara1/multi-ai-agentic-ecommerce](https://github.com/savankansagara1/multi-ai-agentic-ecommerce)
- **Demo Video**: See [`Screencast from 30-09-26 11:54:26 AM IST.webm`](Screencast%20from%2030-09-26%2011:54:26%20AM%20IST.webm) for a walkthrough of the multi-agent system, real-time UI, and confirmation flows.
