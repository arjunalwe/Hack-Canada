"""Gemini-powered content generation — emails, pitches, and executive summaries."""

from typing import Any, Dict

from backboard import BackboardClient
from config import settings

client = BackboardClient(api_key=settings.BACKBOARD_API_KEY)


async def generate_cold_email(data: Dict[str, Any]) -> str:
    """Generate a personalised cold-outreach email from a startup to a VC."""
    prompt = f"""You are an expert fundraising advisor. Write a compelling cold outreach email
from a startup founder to a venture capitalist.

STARTUP:
- Name: {data.get('startup_name')}
- Sector: {data.get('startup_sector')}
- Description: {data.get('startup_description')}

TARGET VC:
- Fund: {data.get('vc_name')}
- Investment Mandate: {data.get('vc_mandate')}
- Contact: {data.get('vc_contact', 'Partner')}

TONE: {data.get('tone', 'professional')}

Rules:
- Keep it under 200 words.
- Lead with a specific hook referencing the VC's mandate or portfolio.
- Clearly state the ask (meeting, not money).
- Include one impressive metric or technical differentiator.
- End with a clear call to action.
- Do NOT use generic filler like "I hope this finds you well."
Return ONLY the email text (subject line + body), no commentary.
"""
    assistant = await client.create_assistant(name="Cold Email Assistant", system_prompt="You write cold emails.")
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False
    )
    return response.content.strip()


async def generate_elevator_pitch(data: Dict[str, Any]) -> str:
    """Generate a 60-second elevator pitch script."""
    prompt = f"""You are an expert pitch coach. Write a 60-second elevator pitch script
for the following startup.

STARTUP:
- Name: {data.get('startup_name')}
- Sector: {data.get('startup_sector')}
- Description: {data.get('startup_description')}
- Tech Stack: {data.get('tech_stack', 'N/A')}
- Target Market: {data.get('target_market', 'N/A')}
- Funding Ask: {data.get('funding_ask', 'N/A')}

Rules:
- Structure: Problem → Solution → Market → Traction → Ask
- Under 150 words (about 60 seconds spoken).
- Be specific, not generic. Use concrete numbers.
- Make the opening line memorable and punchy.
Return ONLY the pitch script, no commentary.
"""
    assistant = await client.create_assistant(name="Pitch Generator", system_prompt="You write elevator pitches.")
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False
    )
    return response.content.strip()


async def generate_exec_summary(data: Dict[str, Any]) -> str:
    """Generate a one-page executive summary."""
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

Sections:
1. **Company Overview** (2-3 sentences)
2. **Problem** (2-3 sentences)
3. **Solution** (2-3 sentences)
4. **Market Opportunity** (2-3 sentences with TAM/SAM/SOM estimates)
5. **Business Model** (2-3 sentences)
6. **Traction & Milestones** (bullet points)
7. **Team** (brief bios)
8. **The Ask** (what they need and what they'll do with it)

Rules:
- Use markdown formatting.
- Be concise but compelling.
Return ONLY the executive summary, no commentary.
"""
    assistant = await client.create_assistant(name="Summary Generator", system_prompt="You write executive summaries.")
    thread = await client.create_thread(assistant.assistant_id)
    response = await client.add_message(
        thread_id=thread.thread_id,
        content=prompt,
        stream=False
    )
    return response.content.strip()
