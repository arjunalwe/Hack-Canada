"""RAG-enhanced content generation — emails, pitches, summaries, and custom content.

Uses Backboard.io with persistent memories enabled so each generation call
benefits from accumulated context about the startup from brain analysis,
matching, and prior generations.

RAG depth levels:
  - brief (1):  ~200 word high-level overview
  - standard (2): ~400 word detailed briefing with metrics
  - deep (3):  ~800 word exhaustive analysis with all data points
"""

from typing import Any, Dict

from backboard import BackboardClient
from config import settings

client = BackboardClient(api_key=settings.BACKBOARD_API_KEY, timeout=120)

# ── RAG depth prompts ───────────────────────────────────────
_DEPTH_PROMPTS = {
    1: """Based on ALL uploaded documents, give me a high-level startup briefing.
Include: core innovation, value proposition, target market, and stage.
Be concise — 200 words max.""",

    2: """Based on ALL uploaded documents, give me a detailed startup briefing
for writing investor communications. Include:
- Core technical innovation and how it works
- Specific metrics, data points, or results from the documents
- Competitive advantages and defensible moats
- Target market specifics and customer pain points
- Business model details
- Team qualifications if mentioned
- Any traction, partnerships, or validation
Be specific and cite details from the documents. 400 words max.""",

    3: """Based on ALL uploaded documents, give me an EXHAUSTIVE startup briefing.
I need EVERY relevant detail for writing deeply informed investor materials. Include:
- Complete technical architecture and how the innovation works end-to-end
- ALL specific metrics, data points, percentages, benchmarks, and results
- Every competitive advantage, IP, patent, or defensible moat mentioned
- Full market analysis — TAM/SAM/SOM, customer segments, pain points, pricing
- Detailed business model, revenue streams, unit economics
- All team members, their backgrounds, qualifications, and relevant experience
- Every piece of traction — users, revenue, partnerships, pilots, LOIs, press
- Risk factors and how they're being mitigated
- Funding history and current ask details
- Any technical validation, peer reviews, or third-party endorsements
Leave NOTHING out. Quote exact numbers and specifics. 800 words max.""",
}


async def _get_brain_context(depth: int = 2) -> str:
    """Pull context from the brain's RAG-indexed documents.
    
    Args:
        depth: 1 (brief), 2 (standard), 3 (deep/exhaustive)
    """
    depth = max(1, min(3, depth))
    try:
        from brain.document_analyzer import analyzer as brain
        docs = brain.get_uploaded_documents()
        if not docs:
            return ""
        
        thread_id = await brain._ensure_thread()
        prompt = _DEPTH_PROMPTS.get(depth, _DEPTH_PROMPTS[2])
        response = await brain.client.add_message(
            thread_id=thread_id,
            content=prompt,
            stream=False,
            memory="Auto",
        )
        return response.content.strip()
    except Exception as e:
        print(f"[gen] Brain context pull failed: {e}")
        return ""


async def generate_cold_email(data: Dict[str, Any]) -> str:
    """Generate a personalised cold-outreach email from a startup to a VC."""
    depth = data.get('depth', 2)
    brain_context = await _get_brain_context(depth)
    brain_section = f"\n\nDEEP CONTEXT FROM UPLOADED DOCUMENTS:\n{brain_context}" if brain_context else ""
    
    prompt = f"""You are an expert fundraising advisor. Write a compelling cold outreach email
from a startup founder to a venture capitalist.

STARTUP:
- Name: {data.get('startup_name')}
- Sector: {data.get('startup_sector')}
- Description: {data.get('startup_description')}
{brain_section}

TARGET VC:
- Fund: {data.get('vc_name')}
- Investment Mandate: {data.get('vc_mandate')}
- Contact: {data.get('vc_contact', 'Partner')}

TONE: {data.get('tone', 'professional')}

Rules:
- Keep it under 200 words.
- Lead with a specific hook referencing the VC's mandate or portfolio.
- USE SPECIFIC DETAILS from the documents — real metrics, tech specifics, validation.
- Clearly state the ask (meeting, not money).
- Include one impressive metric or technical differentiator from the actual documents.
- End with a clear call to action.
- Do NOT use generic filler like "I hope this finds you well."
- Do NOT be vague — be precise, cite actual data from the startup.
Return ONLY the email text (subject line + body), no commentary.
"""
    assistant = await client.create_assistant(
        name="Cold Email Writer",
        system_prompt="You write personalized, data-driven cold emails for startups. You always reference specific details rather than generic claims."
    )
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False,
        memory="Auto",
    )
    return response.content.strip()


async def generate_elevator_pitch(data: Dict[str, Any]) -> str:
    """Generate a 60-second elevator pitch script."""
    depth = data.get('depth', 2)
    brain_context = await _get_brain_context(depth)
    brain_section = f"\n\nDEEP CONTEXT FROM UPLOADED DOCUMENTS:\n{brain_context}" if brain_context else ""
    
    prompt = f"""You are an expert pitch coach. Write a 60-second elevator pitch script
for the following startup.

STARTUP:
- Name: {data.get('startup_name')}
- Sector: {data.get('startup_sector')}
- Description: {data.get('startup_description')}
- Tech Stack: {data.get('tech_stack', 'N/A')}
- Target Market: {data.get('target_market', 'N/A')}
- Funding Ask: {data.get('funding_ask', 'N/A')}
{brain_section}

Rules:
- Structure: Problem → Solution → Market → Traction → Ask
- Under 150 words (about 60 seconds spoken).
- USE SPECIFIC DETAILS from the documents — actual numbers, tech specifics.
- Reference real results, metrics, or validation from the uploaded materials.
- Make the opening line memorable and punchy.
- Do NOT use generic filler — every sentence should contain specific info.
Return ONLY the pitch script, no commentary.
"""
    assistant = await client.create_assistant(
        name="Pitch Coach",
        system_prompt="You write data-driven, specific elevator pitches grounded in real startup data. Never generic."
    )
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False,
        memory="Auto",
    )
    return response.content.strip()


async def generate_exec_summary(data: Dict[str, Any]) -> str:
    """Generate a one-page executive summary."""
    depth = data.get('depth', 2)
    brain_context = await _get_brain_context(depth)
    brain_section = f"\n\nDEEP CONTEXT FROM UPLOADED DOCUMENTS:\n{brain_context}" if brain_context else ""
    
    prompt = f"""You are a startup strategy consultant. Write a one-page executive summary
for the following startup, formatted in clean sections.

STARTUP:
- Name: {data.get('startup_name')}
- Sector: {data.get('startup_sector')}
- Description: {data.get('startup_description')}
- Tech Stack: {data.get('tech_stack', 'N/A')}
- Target Market: {data.get('target_market', 'N/A')}
- Traction: {data.get('traction', 'N/A')}
- Team: {data.get('team', 'N/A')}
{brain_section}

Sections:
1. **Company Overview** (2-3 sentences)
2. **Problem** (2-3 sentences with market data)
3. **Solution** (2-3 sentences with technical specifics)
4. **Market Opportunity** (2-3 sentences with TAM/SAM/SOM estimates)
5. **Business Model** (2-3 sentences)
6. **Traction & Milestones** (bullet points — use actual data from documents)
7. **Team** (brief bios from documents, or note if not available)
8. **The Ask** (what they need and what they'll do with it)

Rules:
- Use markdown formatting.
- BE SPECIFIC — cite actual data, metrics, and technical details from the documents.
- Do NOT make up numbers. Use "TBD" if a specific metric isn't available.
Return ONLY the executive summary, no commentary.
"""
    assistant = await client.create_assistant(
        name="Summary Writer",
        system_prompt="You write detailed, data-driven executive summaries grounded in real documents. Never fabricate metrics."
    )
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False,
        memory="Auto",
    )
    return response.content.strip()


async def generate_custom(data: Dict[str, Any]) -> str:
    """Generate custom content based on user's free-form prompt.
    
    This is the most flexible endpoint — users can ask for anything:
    investor updates, board decks, FAQ sheets, competitive analyses,
    market research summaries, or edit/refine previous outputs.
    """
    depth = data.get('depth', 2)
    user_prompt = data.get('prompt', '')
    previous_content = data.get('previous_content', '')
    
    brain_context = await _get_brain_context(depth)
    brain_section = f"\n\nDEEP CONTEXT FROM UPLOADED DOCUMENTS:\n{brain_context}" if brain_context else ""
    
    edit_section = ""
    if previous_content:
        edit_section = f"\n\nPREVIOUS CONTENT TO EDIT/REFINE:\n{previous_content}\n"
    
    prompt = f"""You are an expert startup communications advisor with deep knowledge of 
fundraising, investor relations, and startup storytelling.

STARTUP CONTEXT:
- Name: {data.get('startup_name', 'N/A')}
- Sector: {data.get('startup_sector', 'N/A')}
- Description: {data.get('startup_description', 'N/A')}
{brain_section}
{edit_section}

USER'S REQUEST:
{user_prompt}

Rules:
- USE SPECIFIC DETAILS from the uploaded documents — never be generic.
- Ground everything in real data, metrics, and technical specifics.
- If editing previous content, preserve the user's intent and improve quality.
- Format appropriately (markdown for documents, plain text for messages).
- Be thorough and professional.

Return ONLY the requested content, no commentary or explanations.
"""
    assistant = await client.create_assistant(
        name="Custom Generator",
        system_prompt="You are a versatile startup content creator. You always use specific, real data from documents and never write generic filler."
    )
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False,
        memory="Auto",
    )
    return response.content.strip()
