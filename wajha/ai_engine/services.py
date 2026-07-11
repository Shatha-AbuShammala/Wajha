import json
import google.generativeai as genai
from django.conf import settings
from .models import AIMatch
from grants.models import GrantOpportunity

class AIService:
    @staticmethod
    def _get_client():
        genai.configure(api_key=settings.GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-flash-lite-latest')

    @staticmethod
    def generate_matches_for_student(student):
        """
        Calculates match scores ONLY for new grants that don't have a record yet.
        Existing matches are preserved unchanged to prevent scores from fluctuating.
        """
        model = AIService._get_client()
        eligible_grants = list(GrantOpportunity.objects.filter(status='published'))

        if not eligible_grants:
            return []

        existing_grant_ids = set(
            AIMatch.objects.filter(student=student).values_list('grant_id', flat=True)
        )

        new_grants = [g for g in eligible_grants if g.id not in existing_grant_ids]

        if new_grants:
            degree_level = student.get_degree_level_display() if hasattr(student, 'get_degree_level_display') else getattr(student, 'degree_level', "Master's")
            field_of_study = getattr(student, 'field_of_study', '')
            gpa = str(getattr(student, 'gpa', ''))
            bio = getattr(student, 'bio', '')
            languages = getattr(student, 'languages', '')
            has_cv = "Yes" if getattr(student, 'cv_file', None) else "No"

            grants_text = ""
            for i, grant in enumerate(new_grants):
                grants_text += f"""
  Grant #{i + 1} (ID: {grant.id}):
    - Title: {grant.title}
    - Description: {grant.description[:400]}
    - Eligibility: {grant.eligibility_text[:400]}
"""

            prompt = f"""
You are the Core Matching Engine for Wajha (a scholarship platform).
Analyze this student's profile against EACH of the grants listed below and return a batch result.

Student Profile:
- Degree Level: {degree_level}
- Field of Study: {field_of_study}
- GPA: {gpa} (out of 4.0)
- Bio/Experience: {bio}
- Languages: {languages}
- Has CV Uploaded: {has_cv}

Grants to analyze:
{grants_text}

Tasks for EACH grant:
1. Calculate a strict Match Score (float, 0.00–100.00). Be realistic.
2. Write a concise 1–2 sentence explanation in the style of "Why it fits", e.g.:
   "Your CS background + 3.6 GPA clear the bar, and DAAD funds Palestinian Masters students."

Output MUST be a valid JSON array (one object per grant, in the same order):
[
  {{"grant_id": <id>, "match_score": 87.50, "explanation": "..."}},
  ...
]
Return ONLY the JSON array. No markdown, no extra text.
"""

            try:
                response = model.generate_content(prompt)
                response_text = response.text.strip()

                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                elif response_text.startswith('```'):
                    response_text = response_text[3:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

                results = json.loads(response_text)
                results_by_id = {r['grant_id']: r for r in results}

                for grant in new_grants:
                    result = results_by_id.get(grant.id)
                    if not result:
                        continue
                    AIMatch.objects.create(
                        student=student,
                        grant=grant,
                        match_score=result.get('match_score', 0.00),
                        explanation=result.get('explanation', '')
                    )

            except Exception as e:
                print(f"Batch match error for new grants: {str(e)}")

        return list(AIMatch.objects.filter(student=student).select_related('grant').order_by('-match_score'))


    @staticmethod
    def generate_eligibility_summary(grant):
        """
        Generates a structured JSON eligibility snapshot — short bullet points
        per category — instead of a long prose block.
        """
        model = AIService._get_client()

        prompt = f"""
You are an AI assistant for Wajha, a scholarship platform.
Your job is to extract the KEY eligibility requirements from the scholarship text below
and return them as a clean, scannable JSON object.

Scholarship: {grant.title}
Eligibility text:
{grant.eligibility_text}

Return ONLY a valid JSON object with these exact keys (omit a key if not mentioned):
{{
  "academic_level": "e.g. Bachelor's / Master's / PhD",
  "gpa": "e.g. Minimum 3.0 / 4.0 or Not specified",
  "nationality": "e.g. Open to all / Palestinian students / Non-Canadian international students",
  "language": "e.g. English proficiency required (IELTS/TOEFL) / Not stated",
  "deadline_note": "e.g. Must apply before Oct 2026 / Rolling basis",
  "funding": "e.g. Fully funded / Partial / Stipend only",
  "key_requirements": ["short bullet 1", "short bullet 2", "short bullet 3"]
}}

Rules:
- Each value must be SHORT (max 12 words).
- key_requirements: max 4 bullets, each max 10 words, the most critical rules only.
- Return ONLY the JSON object. No markdown, no extra text.
"""

        try:
            response = model.generate_content(prompt)
            summary_text = response.text.strip()

            if summary_text.startswith('```json'):
                summary_text = summary_text[7:]
            elif summary_text.startswith('```'):
                summary_text = summary_text[3:]
            if summary_text.endswith('```'):
                summary_text = summary_text[:-3]
            summary_text = summary_text.strip()

            json.loads(summary_text)

            grant.eligibility_summary = summary_text
            grant.save(update_fields=['eligibility_summary'])
            return summary_text
        except Exception as e:
            print(f"Error generating eligibility summary for grant {grant.id}: {str(e)}")

        return grant.eligibility_summary

    @staticmethod
    def generate_personalized_eligibility(grant, student):
        """
        Generates 5-6 key eligibility points tailored to the student's profile.
        Returns a JSON array of dicts with 'requirement', 'user_status', and 'is_met'.
        """
        model = AIService._get_client()

        degree_level = student.get_degree_level_display() if hasattr(student, 'get_degree_level_display') else getattr(student, 'degree_level', 'Not specified')
        field_of_study = getattr(student, 'field_of_study', 'Not specified')
        gpa = str(getattr(student, 'gpa', 'Not specified'))
        bio = getattr(student, 'bio', '')
        languages = getattr(student, 'languages', 'Not specified')

        prompt = f"""
You are an AI assistant for Wajha, a scholarship platform.
Analyze the scholarship requirements against the user's profile and provide 5-6 key eligibility points.
For each point, determine if the user meets the requirement based on their profile.

Scholarship: {grant.title}
Eligibility text:
{grant.eligibility_text}

User Profile:
- Academic level: {degree_level}
- Field of study: {field_of_study}
- GPA: {gpa} / 4.00
- Languages: {languages}
- Bio/Experience: {bio}

Return ONLY a valid JSON array of objects, with no markdown formatting.
Each object must have:
- "requirement": Short summary of the requirement (e.g. "Minimum GPA of 3.0").
- "user_status": A short text relating to the user (e.g. "Yours is 3.6", "You hold a Bachelor's", "Not specified in profile").
- "is_met": true if user meets it, false if they don't, null if unknown or not specified.

Example:
[
  {{"requirement": "Must hold a Bachelor's degree", "user_status": "You hold a Bachelor's", "is_met": true}},
  {{"requirement": "Minimum GPA 3.0", "user_status": "Yours is 3.6", "is_met": true}},
  {{"requirement": "English proficiency (IELTS/TOEFL)", "user_status": "Not specified in profile", "is_met": null}},
  {{"requirement": "Open to Computer Science", "user_status": "Your field is Computer Science", "is_met": true}}
]

Generate 5 to 6 points. Return ONLY the JSON array.
"""
        try:
            response = model.generate_content(prompt)
            summary_text = response.text.strip()

            if summary_text.startswith('```json'):
                summary_text = summary_text[7:]
            elif summary_text.startswith('```'):
                summary_text = summary_text[3:]
            if summary_text.endswith('```'):
                summary_text = summary_text[:-3]
            
            return json.loads(summary_text.strip())
        except Exception as e:
            print(f"Error generating personalized eligibility for grant {grant.id}: {str(e)}")
            return []

    @staticmethod
    def draft_motivation_letter(student, grant, tone='formal', custom_focus=''):
        """
        Drafts a tailored motivation letter for the student and the target grant.
        """
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-flash-lite-latest')

        full_name = getattr(student, 'full_name', '') or student.username
        email = getattr(student, 'email', '')
        country = getattr(student, 'country', '')
        
        degree_level = student.get_degree_level_display() if hasattr(student, 'get_degree_level_display') else getattr(student, 'degree_level', 'Master\'s')
        field_of_study = getattr(student, 'field_of_study', '')
        gpa = str(getattr(student, 'gpa', ''))
        bio = getattr(student, 'bio', '')
        languages = getattr(student, 'languages', '')

        cv_instruction = ""
        cv_file_obj = None
        if getattr(student, 'cv_file', None) and student.cv_file.name.endswith('.pdf'):
            try:
                import os
                if os.path.exists(student.cv_file.path):
                    cv_file_obj = genai.upload_file(student.cv_file.path)
                    cv_instruction = "CRITICAL: The student's CV is attached to this prompt. You MUST extract their specific technical skills, projects, and work experiences from the CV and seamlessly weave them into the letter to prove they are a strong fit for this specific grant."
            except Exception as e:
                print(f"Failed to upload CV to Gemini: {e}")

        prompt = f"""
        You are an elite academic advisor and expert grant writer. Your task is to write a highly persuasive, customized motivation letter for a student applying for a scholarship. 
        You MUST deeply analyze the student's profile, their attached CV (if provided), and the specific grant requirements, then synthesize this into a compelling narrative.

        Student Profile:
        - Full Name: {full_name}
        - Email: {email}
        - Country: {country}
        - Degree level: {degree_level}
        - Field of study: {field_of_study}
        - GPA: {gpa} / 4.00
        - Bio & Specific Skills: {bio}
        - Languages: {languages}

        Grant Details to Target:
        - Title: {grant.title}
        - Organization: {grant.organization}
        - Description: {grant.description}
        - Eligibility Requirements: {grant.eligibility_text}

        Writing Directives & Constraints:
        1. Tone of the letter: {tone} (Ensure it aligns with the requested tone: Formal, Personal, or Concise).
        2. Custom focus requested by student: {custom_focus} (Make sure this theme is prominent in the letter if provided).
        3. Structure: 
           - Compelling Hook: Start strong by mentioning the specific Grant Title and Organization, and concisely state the student's core academic mission.
           - Evidence-Based Body: Extract specific projects, skills, and experiences from the student's profile and CV. Map them directly to the Grant's goals and eligibility criteria. Show, don't just tell.
           - Impact & Future Goals: Explain how this specific grant will help the student achieve their long-term vision.
           - Strong Conclusion.
        4. {cv_instruction}
        5. CRITICAL: Do NOT write a generic template. The letter MUST uniquely reflect THIS student applying to THIS grant. Avoid clichés.
        6. CRITICAL SIGN-OFF: You must conclude the letter with the student's actual Full Name ({full_name}) and Email ({email}). 
        7. Do NOT use placeholder brackets anywhere in the letter (e.g. no [Your Name], no [Your Phone Number], no [Insert Skill]). Generate a complete, ready-to-submit draft.
        """

        try:
            if cv_file_obj:
                response = model.generate_content([prompt, cv_file_obj])
            else:
                response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error drafting letter: {str(e)}"

    @staticmethod
    def review_cv(student, grant):
        """
        Reviews a student's profile gaps relative to the grant criteria, and suggests improvements.
        """
        if not getattr(student, 'cv_file', None):
            return [
                "⚠️ CV Missing: Please upload your CV (PDF) in your profile to unlock this feature.",
                "The AI needs your detailed academic and professional history to accurately identify gaps and provide tailored recommendations for this grant."
            ]

        model = AIService._get_client()

        degree_level = student.get_degree_level_display() if hasattr(student, 'get_degree_level_display') else getattr(student, 'degree_level', 'Master\'s')
        field_of_study = getattr(student, 'field_of_study', '')
        gpa = str(getattr(student, 'gpa', ''))
        bio = getattr(student, 'bio', '')
        languages = getattr(student, 'languages', '')
        has_cv = "Yes" if getattr(student, 'cv_file', None) else "No"

        prompt = f"""
        You are an AI academic advisor for Wajha.
        Review this student's profile against the grant requirements, find what is missing (gaps),
        and provide a list of specific, actionable advice/improvements to help them stand a better chance.

        Student Profile:
        - Academic level: {degree_level}
        - Field of study: {field_of_study}
        - GPA: {gpa} / 4.00
        - Bio / Experience details: {bio}
        - Languages: {languages}
        - CV Uploaded: {has_cv}

        Grant Requirements:
        - Title: {grant.title}
        - Organization: {grant.organization}
        - Description: {grant.description}
        - Eligibility: {grant.eligibility_text}

        Tasks:
        Generate a list of 3-5 concrete profile improvements or gap notifications.
        Example output format:
        [
          "Upload your CV (PDF) to unlock personalized motivation letter drafting.",
          "Add an English certificate (IELTS/TOEFL) as this grant is for English-taught programs.",
          "Obtain 1-2 recommendation letters from professors in Computer Science.",
          "Provide portfolio links to showcase your web applications and project work."
        ]

        Generate a JSON array of strings only.
        """

        try:
            response = model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            gaps = []
            if not student.cv_file:
                gaps.append("Upload your CV (PDF) to unlock application drafting.")
            if not student.languages:
                gaps.append("Add at least one language you're fluent in.")
            if not student.bio:
                gaps.append("Add a short bio/portfolio link to personalize matches.")
            if not gaps:
                gaps.append("Keep your academic records updated.")
            return gaps