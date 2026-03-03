import os
import json
import re
import time
from typing import List, Dict
from openai import OpenAI
from .models import CandidateProfile, CandidateAssessment, RoleFitScore

class HiringAgent:
    """
    The Brain of the AI Hiring Intelligence Agent.
    Handles quick filtering and deep assessment using Cerebras AI.
    """
    def __init__(self, api_key: str = None, model: str = "llama3.1-8b"):
        self.api_key = api_key or os.getenv("CEREBRAS_API_KEY")
        self.model = model
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.cerebras.ai/v1"
        ) if self.api_key else None
        
        if not self.client:
            print("⚠️  WARNING: Cerebras API Key not found. Agent cannot perform analysis.")

    def quick_filter(self, candidates: List[CandidateProfile], role: str, limit: int = 50, ideal_persona: str = None) -> List[tuple]:
        """
        Fast assessment of many candidates based on search snippets to identify top candidates for deep scraping.
        Returns a list of (score, candidate) tuples.
        """
        if not self.client:
            raise ValueError("❌ Cerebras API Key is missing. Cannot perform AI filtering.")
            
        if not candidates:
            return []
            
        print(f"🎯 AI Filtering {len(candidates)} candidates for best fit...")
        
        persona_context = f"\nIDEAL PERSONA REQUIREMENTS:\n{ideal_persona}" if ideal_persona else ""
        
        # We'll process candidates in batches to be efficient
        batch_size = 20
        scored_candidates = []
        
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i+batch_size]
            prompt = f"""
            You are a master recruiter specialized in technical hiring for "{role}".{persona_context}
            
            Score these {len(batch)} candidates from 0-100 based on their LinkedIn Headline.
            
            CRITERIA:
            1. Keywords: Direct match for technlogies mentioned.
            2. Seniority: Is the candidate a Lead, Senior, or specialized Expert?
            3. Persona Match: How well do they fit the specific 'Ideal Persona' requirements above?
            
            Return ONLY a raw JSON list of numbers in the same order.
            Example: [85, 40, 92]
            
            Candidates:
            {[f"{c.name}: {c.headline}" for c in batch]}
            """
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.choices[0].message.content
                # Parse scores
                scores = []
                try: 
                    match = re.search(r'\[.*\]', content, re.DOTALL)
                    scores = json.loads(match.group()) if match else []
                except:
                    scores = [int(s) for s in re.findall(r'\d+', content)]
                
                # Align scores with batch size
                if len(scores) < len(batch):
                    scores += [0] * (len(batch) - len(scores))
                
                for cand, raw_score in zip(batch, scores[:len(batch)]):
                    score = 0
                    if isinstance(raw_score, dict):
                        score = int(raw_score.get('score', 0))
                    elif isinstance(raw_score, (int, float)):
                        score = int(raw_score)
                    scored_candidates.append((score, cand))
            except Exception as e:
                print(f"⚠️ Filter error: {e}")
                for cand in batch: scored_candidates.append((0, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return scored_candidates[:limit]

    def assess_candidate(self, candidate: CandidateProfile, role_description: str, ideal_persona: str = None) -> CandidateAssessment:
        """
        Full deep analysis of a candidate against a role and persona.
        """
        if not self.client:
            raise ValueError(f"❌ Cerebras API Key is missing. Cannot assess {candidate.name}.")

        persona_context = f"\nBOSS'S IDEAL CANDIDATE REQUIREMENTS:\n{ideal_persona}" if ideal_persona else ""
        
        prompt = f"""
        You are an expert technical recruiter. Analyze this candidate for the role: {role_description}
        
        BOSS'S REQUIREMENTS (Must Have):
        {persona_context}
        
        CANDIDATE DATA:
        Name: {candidate.name}
        Headline: {candidate.headline}
        Experience: {candidate.experience_text}
        
        TASK:
        1. Compare Candidate Experience vs Boss's Requirements.
        2. Look for specific evidence (Years of XP, specific tech stacks, leadership roles).
        3. Be strict. If they lack a "Must Have", score them low.
        
            Provide a strict JSON response:
            {{
                "candidate_id": "{candidate.id}",
                "candidate_name": "{candidate.name}",
                "overall_score": 0-100,
                "tier": 1 (Perfect Match), 2 (Good Match), or 3 (Mismatch),
                "recommended_action": "Shortlist", "Review", "Hold", or "Reject",
                "role_fit_analysis": {{
                    "score": 0-100,
                    "strengths": ["List specific skills/experience found"],
                    "gaps": ["List missing requirements"],
                    "evidence": "MUST BE A STRING. Provide brief excerpts or specific items from their profile that justify the score.",
                    "explanation": "MUST BE A STRING. Explain why the candidate got this score based on the evidence."
                }},
                "reasoning_summary": "A 2-sentence summary for the hiring manager.",
                "risk_flags": ["Job hopping", "Career gap", "Junior role", "Irrelevant industry"]
            }}
            
            IMPORTANT: All text fields like "evidence", "explanation", "reasoning_summary" MUST be plain strings, NOT objects.
            """
            
        max_retries = 3
        retry_delay = 2 # Seconds
        
        for attempt in range(max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    timeout=45.0
                )
                content = resp.choices[0].message.content
                # Pre-clean the content just in case
                content = self._clean_json(content)
                data = json.loads(content)
                data['model_used'] = self.model
                # Ensure name is present even if AI missed it
                if 'candidate_name' not in data:
                    data['candidate_name'] = candidate.name
                return CandidateAssessment(**data)
            except Exception as e:
                # Check for 429 Too Many Requests
                error_msg = str(e).lower()
                if "429" in error_msg or "too many requests" in error_msg:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️ AI Busy (429). Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2 # Exponential backoff
                        continue
                
                print(f"   ❌ Assessment failed: {e}")
                # Fallback to prevent pipeline crash
            return CandidateAssessment(
                candidate_id=candidate.id,
                candidate_name=candidate.name,
                overall_score=0,
                tier=3,
                recommended_action="Review",
                role_fit_analysis=RoleFitScore(
                    score=0,
                    strengths=[],
                    gaps=["AI Analysis Failed"],
                    evidence=f"Error: {str(e)[:100]}",
                    explanation="Automated assessment encountered an error."
                ),
                reasoning_summary="AI Assessment failed due to technical error. Please review manually.",
                risk_flags=["AI Error"]
            )

    def _clean_json(self, text: str) -> str:
        # Remove markdown code blocks if present
        text = text.replace("```json", "").replace("```", "").strip()
        return text
