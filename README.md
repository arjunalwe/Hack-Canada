An end-to-end, autonomous fundraising co-pilot and adversarial VC simulator. We built a multi-agent AI system that translates dense technical IP into an institutional investment thesis, matches founders with local Canadian capital, and ruthlessly simulates the boardroom pitch.

## ⚠️ The Problem: Ecosystem Friction & Brain Drain
The corridor spanning Waterloo to Toronto produces some of the highest-caliber engineering talent and technical IP in the world. However, the translation layer between student builders and institutional capital is fundamentally broken. Founders speak in GitHub commits and theoretical breakthroughs; VCs speak in term sheets and market fit. Because of this friction, incredible local startups bleed out to US acquirers simply because navigating the Canadian funding landscape is too opaque. 

## 💡 The Solution
RAGs to Riches bridges this gap. We didn't build a CRM or a generic cold-email generator. We built a literal **simulation engine** and **autonomous broker**.

### Core Features
1. **Deep IP Ingestion:** Extracts the core commercial utility from dense, unstructured intellectual property (academic papers, technical documentation).
2. **Agentic Sourcing:** Bypasses static databases by actively scraping and structuring live directories of venture funds into a clean knowledge graph.
3. **Multi-Agent Matchmaking:** Mathematically matches the startup's IP against the inferred, unspoken mandates of institutional investors using a multi-turn AI debate.
4. **The Adversarial Simulator:** Drops the founder into a high-stakes audio gauntlet. An AI persona of the matched VC dynamically pushes back, interrupts, and grills the founder on their weak points in real-time.

---

## 🏗️ System Architecture & Tech Stack

* **Frontend:** Built with React (scaffolded via **Google Antigravity**) to create a Collaborative Generation Studio for founders.
* **Backend:** Highly concurrent **FastAPI (Python)** server, exposing RESTful endpoints.
* **AI & Orchestration:** **Backboard.io** for deep document RAG, persistent multi-session memory, and tool-calling capabilities. 
* **LLM Engine:** **Google Gemini API** handles unstructured data parsing ("Dumb Scraper") and powers the hyper-critical VC persona generation.
* **Audio Synthesis:** **ElevenLabs API** streams low-latency, hyper-realistic synthetic audio for the simulator.
* **Security & Networking:** Backend logic is tunneled securely using **Tailscale**, with **Auth0** handling enterprise-grade user authentication.

---

## 🧠 The Matchmaking Logic (Agentic Debate)

To bypass the standard "keyword matching" of traditional platforms, our matching engine relies on a multi-agent debate orchestrated via Backboard.io.

1. **Agent A (Thesis Analyst):** Infers the VC's actual investment thesis beyond their stated website mandate.
2. **Agent B (The Debate):** A multi-turn debate where a Startup Advocate agent uses the uploaded IP to defend the startup against a VC Critic agent.
3. **Agent C (The Arbiter):** Evaluates the debate transcript using explicit tool-calling to generate a definitive match score.

The final compatibility score is calculated using the following vector-penalty formula:

$$\mathcal{M}(S, V) = \alpha \cdot \text{sim}(\vec{v}_S, \vec{v}_V) - \beta \cdot \Delta_{\text{stage}} - \gamma \cdot \mathcal{P}_{\text{debate}}$$

*(Where $\text{sim}(\vec{v}_S, \vec{v}_V)$ represents the cosine similarity of the extracted mandate embeddings, $\Delta_{\text{stage}}$ is the investment stage mismatch penalty, and $\mathcal{P}_{\text{debate}}$ is the algorithmic penalty accrued if the Startup Advocate fails to defend its premise).*

---

## 🚀 Getting Started (Local Dev)

**1. Clone the repository**
```bash
git clone [https://github.com/arjunalwe/Hack-Canada]
cd Hack-Canada

cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

Create a .env file in the backend directory and add your API keys:
GEMINI_API_KEY=your_gemini_key
ELEVENLABS_API_KEY=your_elevenlabs_key
BACKBOARD_API_KEY=your_backboard_key

uvicorn main:app --reload



