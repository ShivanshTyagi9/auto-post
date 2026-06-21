"""
AI caption generation via the OpenAI API.

Used both standalone (auto-caption a manual publish/schedule call) and by the growth
agent's autopilot flow. When an image URL is available, the caption is grounded in
what's actually in the image via vision; otherwise it falls back to a text-only prompt
built from the account's niche/tone/goal/location.
"""

from __future__ import annotations

import os
from typing import Optional

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set — cannot generate AI captions.")
        _client = OpenAI(api_key=api_key)
    return _client


def _build_prompt(
    niche: Optional[str],
    tone: Optional[str],
    goal: Optional[str],
    location: Optional[str],
    caption_hint: Optional[str],
    hashtag_count: int,
) -> str:
    parts = ["Write a single Instagram caption for this post."]
    if caption_hint:
        parts.append(f"What the post is about: {caption_hint}.")
    if niche:
        parts.append(f"Account niche: {niche}.")
    if tone:
        parts.append(f"Tone/voice: {tone}.")
    if goal:
        parts.append(f"Primary goal: {goal} (write the caption to help achieve this, e.g. a clear call to action for leads).")
    if location:
        parts.append(f"Target audience location: {location} — make it feel locally relevant where natural.")
    parts.append(
        f"Keep it concise (2-4 short lines), no markdown, end with {hashtag_count} relevant hashtags. "
        "Return ONLY the caption text, nothing else."
    )
    return " ".join(parts)


async def generate_caption(
    *,
    image_url: Optional[str] = None,
    niche: Optional[str] = None,
    tone: Optional[str] = None,
    goal: Optional[str] = None,
    location: Optional[str] = None,
    caption_hint: Optional[str] = None,
    hashtag_count: int = 8,
) -> str:
    """Generate an Instagram caption, grounded in the image when one is provided."""
    import asyncio

    client = _get_client()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _build_prompt(niche, tone, goal, location, caption_hint, hashtag_count)

    if image_url:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
    else:
        content = prompt

    def _call() -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=300,
        )
        return (response.choices[0].message.content or "").strip()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)
