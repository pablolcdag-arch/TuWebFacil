import os
import json
import random
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv
import google.generativeai as genai
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Instagram API configuration
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_BUSINESS_ID = os.getenv("INSTAGRAM_BUSINESS_ID")
INSTAGRAM_API_VERSION = "v19.0"
INSTAGRAM_API_BASE_URL = f"https://graph.facebook.com/{INSTAGRAM_API_VERSION}"

class MarketingBot:
    def __init__(self):
        """
        Initialize the Marketing Bot with necessary configurations.
        """
        # Detect available Gemini model
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            self.model_name = "models/gemini-2.5-flash" if "models/gemini-2.5-flash" in models else models[0]
            self.model = genai.GenerativeModel(self.model_name)
            print(f"Using Gemini model: {self.model_name}")
        except Exception as e:
            print(f"Error initializing Gemini model: {e}")
            raise
    
    def generate_daily_content(self, client_id: Optional[str] = None, content_type: str = "post") -> Dict[str, Any]:
        """
        Generate daily content for Instagram.
        
        Args:
            client_id: Optional client ID to generate content for a specific client
            content_type: Type of content to generate (post, story, reel)
            
        Returns:
            Dictionary with generated content
        """
        try:
            # Get business information
            business_info = self._get_business_info(client_id)
            
            # Get content themes and ideas based on business type
            themes = self._get_content_themes(business_info["business_type"])
            
            # Select a random theme
            theme = random.choice(themes)
            
            # Generate content based on theme and business info
            content = self._generate_content_with_ai(business_info, theme, content_type)
            
            # Store the generated content in Supabase
            content_id = self._store_content_in_db(client_id, content)
            
            # Return the generated content
            return {
                "id": content_id,
                "content": content,
                "business_info": business_info,
                "theme": theme
            }
        except Exception as e:
            print(f"Error generating daily content: {e}")
            raise
    
    def analyze_competitor(self, competitor_instagram: str, client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a competitor's Instagram account.
        
        Args:
            competitor_instagram: Competitor's Instagram handle
            client_id: Optional client ID to associate the analysis with
            
        Returns:
            Dictionary with competitor analysis
        """
        try:
            # Get competitor data from Instagram
            competitor_data = self._get_instagram_data(competitor_instagram)
            
            # Get business information for context
            business_info = self._get_business_info(client_id)
            
            # Analyze competitor data with AI
            analysis = self._analyze_competitor_with_ai(competitor_data, business_info)
            
            # Store the analysis in Supabase
            analysis_id = self._store_competitor_analysis_in_db(client_id, competitor_instagram, analysis)
            
            # Return the analysis
            return {
                "id": analysis_id,
                "competitor": competitor_instagram,
                "analysis": analysis
            }
        except Exception as e:
            print(f"Error analyzing competitor: {e}")
            raise
    
    def generate_content_from_competitor_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Generate content based on competitor analysis.
        
        Args:
            analysis_id: ID of the competitor analysis
            
        Returns:
            Dictionary with generated content
        """
        try:
            # Get the competitor analysis
            analysis = self._get_competitor_analysis(analysis_id)
            if not analysis:
                raise ValueError(f"Competitor analysis with ID {analysis_id} not found")
            
            # Get business information
            client_id = analysis.get("client_id")
            business_info = self._get_business_info(client_id)
            
            # Generate content based on competitor analysis
            content = self._generate_content_from_analysis_with_ai(analysis, business_info)
            
            # Store the generated content in Supabase
            content_id = self._store_content_in_db(client_id, content)
            
            # Return the generated content
            return {
                "id": content_id,
                "content": content,
                "based_on_analysis": analysis_id
            }
        except Exception as e:
            print(f"Error generating content from competitor analysis: {e}")
            raise
    
    def schedule_content(self, content_id: str, scheduled_date: str) -> bool:
        """
        Schedule content for publishing.
        
        Args:
            content_id: ID of the content to schedule
            scheduled_date: Date to publish the content (ISO format)
            
        Returns:
            True if scheduled successfully, False otherwise
        """
        try:
            # Update the content in Supabase
            supabase.table("marketing_content").update({
                "status": "scheduled",
                "scheduled_date": scheduled_date
            }).eq("id", content_id).execute()
            
            return True
        except Exception as e:
            print(f"Error scheduling content: {e}")
            return False
    
    def publish_content(self, content_id: str) -> Tuple[bool, Optional[str]]:
        """
        Publish content to Instagram.
        
        Args:
            content_id: ID of the content to publish
            
        Returns:
            Tuple of (success, instagram_post_id)
        """
        try:
            # Get the content from Supabase
            result = supabase.table("marketing_content").select("*").eq("id", content_id).execute()
            if not result.data or len(result.data) == 0:
                return False, None
            
            content = result.data[0]
            
            # Check if content is ready to publish
            if content.get("status") not in ["approved", "scheduled"]:
                print(f"Content is not approved or scheduled: {content.get('status')}")
                return False, None
            
            # Publish to Instagram
            instagram_post_id = self._publish_to_instagram(content)
            
            if not instagram_post_id:
                return False, None
            
            # Update the content in Supabase
            supabase.table("marketing_content").update({
                "status": "published",
                "published_date": datetime.utcnow().isoformat(),
                "instagram_post_id": instagram_post_id
            }).eq("id", content_id).execute()
            
            return True, instagram_post_id
        except Exception as e:
            print(f"Error publishing content: {e}")
            return False, None
    
    def _get_business_info(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get business information for content generation.
        
        Args:
            client_id: Optional client ID to get specific business info
            
        Returns:
            Dictionary with business information
        """
        if client_id:
            # Get client-specific information
            try:
                result = supabase.table("clients").select("*").eq("id", client_id).execute()
                if result.data and len(result.data) > 0:
                    client = result.data[0]
                    
                    # Get website content for additional context
                    websites_result = supabase.table("websites").select("id").eq("client_id", client_id).execute()
                    website_content = {}
                    
                    if websites_result.data and len(websites_result.data) > 0:
                        website_id = websites_result.data[0]["id"]
                        content_result = supabase.table("website_content").select("*").eq("website_id", website_id).eq("is_current", True).execute()
                        
                        if content_result.data and len(content_result.data) > 0:
                            website_content = json.loads(content_result.data[0].get("content", "{}"))
                    
                    return {
                        "business_name": website_content.get("header", {}).get("title", client.get("name", "Business")),
                        "business_type": client.get("business_type", "general"),
                        "tagline": website_content.get("header", {}).get("tagline", ""),
                        "about": website_content.get("sections", [{}])[0].get("content", "") if website_content.get("sections") else "",
                        "instagram_handle": client.get("instagram_handle", ""),
                        "is_client": True
                    }
            except Exception as e:
                print(f"Error getting client business info: {e}")
        
        # Return default TuWebFacil information
        return {
            "business_name": "TuWebFacil",
            "business_type": "web_development",
            "tagline": "Sitios web profesionales en minutos",
            "about": "TuWebFacil es una plataforma que crea, gestiona y vende sitios web automáticamente. Ofrecemos soluciones web rápidas y profesionales para todo tipo de negocios.",
            "instagram_handle": "tuwebfacil",
            "is_client": False
        }
    
    def _get_content_themes(self, business_type: str) -> List[str]:
        """
        Get content themes based on business type.
        
        Args:
            business_type: Type of business
            
        Returns:
            List of content themes
        """
        # General themes that work for any business
        general_themes = [
            "tips_and_tricks",
            "behind_the_scenes",
            "customer_testimonials",
            "frequently_asked_questions",
            "industry_news",
            "how_to_guides",
            "before_and_after",
            "day_in_the_life",
            "meet_the_team",
            "product_features",
            "seasonal_content"
        ]
        
        # Business-specific themes
        business_themes = {
            "web_development": [
                "web_design_trends",
                "coding_tips",
                "website_optimization",
                "responsive_design",
                "seo_tips",
                "website_security",
                "user_experience",
                "website_performance",
                "technology_stack",
                "client_success_stories"
            ],
            "restaurant": [
                "menu_highlights",
                "chef_specials",
                "cooking_techniques",
                "ingredient_spotlights",
                "food_plating",
                "restaurant_ambiance",
                "customer_favorites",
                "seasonal_menus",
                "food_and_drink_pairings",
                "kitchen_stories"
            ],
            "retail": [
                "new_arrivals",
                "styling_tips",
                "product_spotlights",
                "outfit_inspiration",
                "sale_announcements",
                "customer_favorites",
                "product_care_tips",
                "trend_alerts",
                "gift_guides",
                "lookbook_previews"
            ],
            "fitness": [
                "workout_routines",
                "exercise_demonstrations",
                "nutrition_tips",
                "client_transformations",
                "fitness_challenges",
                "recovery_techniques",
                "equipment_guides",
                "fitness_myths",
                "motivation_monday",
                "healthy_recipes"
            ],
            "beauty": [
                "product_tutorials",
                "skincare_routines",
                "beauty_tips",
                "before_and_after",
                "product_reviews",
                "seasonal_looks",
                "client_makeovers",
                "beauty_trends",
                "self_care_tips",
                "ingredient_spotlights"
            ]
        }
        
        # Get themes for the specific business type, or default to general themes
        specific_themes = business_themes.get(business_type, [])
        
        # Combine general and specific themes
        return general_themes + specific_themes
    
    def _generate_content_with_ai(self, business_info: Dict[str, Any], theme: str, content_type: str) -> Dict[str, Any]:
        """
        Generate content using Gemini AI.
        
        Args:
            business_info: Business information
            theme: Content theme
            content_type: Type of content (post, story, reel)
            
        Returns:
            Dictionary with generated content
        """
        try:
            # Prepare the prompt
            prompt = f"""
            Generate engaging Instagram {content_type} content for a {business_info['business_type']} business.
            
            Business Information:
            - Name: {business_info['business_name']}
            - Tagline: {business_info['tagline']}
            - About: {business_info['about']}
            - Instagram: @{business_info['instagram_handle']}
            
            Content Theme: {theme}
            
            Please generate:
            1. A catchy caption (with appropriate hashtags)
            2. A detailed description of the visual design for the {content_type}
            3. Key messages to highlight
            4. Call to action
            
            Format your response as a JSON object with the following structure:
            {{
                "caption": "The Instagram caption with hashtags",
                "design_description": {{
                    "post_type": "carousel/single/reel",
                    "slides": [
                        {{
                            "background_color": "#hexcolor",
                            "text_color": "#hexcolor",
                            "main_text": "Main text on the slide",
                            "secondary_text": "Secondary text if applicable",
                            "image_description": "Description of the image to use",
                            "layout": "text_over_image/split/text_only"
                        }}
                    ],
                    "style_guide": {{
                        "brand_colors": ["#hexcolor1", "#hexcolor2"],
                        "fonts": ["Primary font", "Secondary font"],
                        "visual_style": "minimalist/bold/elegant/etc"
                    }}
                }},
                "key_messages": ["Message 1", "Message 2", "Message 3"],
                "call_to_action": "The specific call to action"
            }}
            """
            
            # Generate content
            response = self.model.generate_content(prompt)
            
            # Parse the response
            content_json = json.loads(response.text)
            
            # Add metadata
            content_json["generated_at"] = datetime.utcnow().isoformat()
            content_json["theme"] = theme
            content_json["content_type"] = content_type
            content_json["business_type"] = business_info["business_type"]
            
            return content_json
        except Exception as e:
            print(f"Error generating content with AI: {e}")
            # Return a simple fallback content
            return {
                "caption": f"Check out our latest updates at {business_info['business_name']}! #webdesign #professional",
                "design_description": {
                    "post_type": "single",
                    "slides": [
                        {
                            "background_color": "#ffffff",
                            "text_color": "#000000",
                            "main_text": business_info['business_name'],
                            "secondary_text": business_info['tagline'],
                            "image_description": "Business logo on a clean background",
                            "layout": "text_over_image"
                        }
                    ],
                    "style_guide": {
                        "brand_colors": ["#4a90e2", "#ffffff"],
                        "fonts": ["Arial", "Helvetica"],
                        "visual_style": "minimalist"
                    }
                },
                "key_messages": ["Professional web design", "Quick and easy", "Affordable"],
                "call_to_action": "Visit our website to learn more",
                "generated_at": datetime.utcnow().isoformat(),
                "theme": theme,
                "content_type": content_type,
                "business_type": business_info["business_type"],
                "error": str(e)
            }
    
    def _get_instagram_data(self, instagram_handle: str) -> Dict[str, Any]:
        """
        Get data from Instagram for a specific account.
        
        Args:
            instagram_handle: Instagram handle to analyze
            
        Returns:
            Dictionary with Instagram data
        """
        # In a real implementation, this would use the Instagram Graph API
        # For now, we'll return mock data
        
        # Check if we have cached data in Supabase
        try:
            result = supabase.table("competitor_analysis").select("*").eq("competitor_instagram", instagram_handle).order("created_at", desc=True).limit(1).execute()
            
            if result.data and len(result.data) > 0 and (datetime.utcnow() - datetime.fromisoformat(result.data[0]["created_at"])).days < 7:
                # Use cached data if less than 7 days old
                return json.loads(result.data[0]["analysis_data"])
        except Exception as e:
            print(f"Error checking cached Instagram data: {e}")
        
        # Mock data for demonstration
        return {
            "username": instagram_handle,
            "follower_count": random.randint(1000, 50000),
            "following_count": random.randint(100, 2000),
            "post_count": random.randint(50, 500),
            "engagement_rate": round(random.uniform(1.0, 5.0), 2),
            "bio": "This is a mock bio for demonstration purposes.",
            "website": f"https://www.{instagram_handle}.com",
            "recent_posts": [
                {
                    "type": "image",
                    "caption": "Check out our latest project! #webdesign #ux #ui",
                    "likes": random.randint(50, 500),
                    "comments": random.randint(5, 50),
                    "posted_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat()
                },
                {
                    "type": "carousel",
                    "caption": "Before and after transformation of our client's website. Swipe to see the difference! #webdesign #transformation",
                    "likes": random.randint(50, 500),
                    "comments": random.randint(5, 50),
                    "posted_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat()
                },
                {
                    "type": "video",
                    "caption": "Quick tutorial on how to improve your website's loading speed. #webperformance #seo #tutorial",
                    "likes": random.randint(50, 500),
                    "comments": random.randint(5, 50),
                    "views": random.randint(500, 5000),
                    "posted_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat()
                }
            ],
            "content_themes": ["web design", "tutorials", "client showcases", "tips and tricks"],
            "posting_frequency": f"{random.randint(1, 7)} posts per week",
            "hashtags": ["#webdesign", "#ux", "#ui", "#webdevelopment", "#seo", "#digitalmarketing"]
        }
    
    def _analyze_competitor_with_ai(self, competitor_data: Dict[str, Any], business_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze competitor data using Gemini AI.
        
        Args:
            competitor_data: Competitor Instagram data
            business_info: Business information for context
            
        Returns:
            Dictionary with competitor analysis
        """
        try:
            # Prepare the prompt
            prompt = f"""
            Analyze this Instagram competitor data for a {business_info['business_type']} business.
            
            Our Business:
            - Name: {business_info['business_name']}
            - Type: {business_info['business_type']}
            - Instagram: @{business_info['instagram_handle']}
            
            Competitor Data:
            {json.dumps(competitor_data, indent=2)}
            
            Please provide a comprehensive analysis including:
            1. Overview of the competitor's Instagram presence
            2. Content analysis (what works well, what doesn't)
            3. Engagement analysis
            4. Visual style assessment
            5. SWOT analysis (Strengths, Weaknesses, Opportunities, Threats)
            6. Specific recommendations for how we can create better content
            
            Format your response as a JSON object with the following structure:
            {{
                "overview": {{
                    "name": "Competitor name",
                    "instagram": "Instagram handle",
                    "followers": number,
                    "engagement_rate": number,
                    "posting_frequency": "frequency"
                }},
                "content_analysis": {{
                    "top_performing_posts": [
                        {{
                            "type": "post type",
                            "topic": "topic",
                            "engagement": number
                        }}
                    ],
                    "content_themes": ["theme1", "theme2"],
                    "visual_style": "description",
                    "tone_of_voice": "description"
                }},
                "website_analysis": {{
                    "design_quality": number (1-10),
                    "mobile_responsiveness": number (1-10),
                    "key_features": ["feature1", "feature2"]
                }},
                "swot": {{
                    "strengths": ["strength1", "strength2"],
                    "weaknesses": ["weakness1", "weakness2"],
                    "opportunities": ["opportunity1", "opportunity2"],
                    "threats": ["threat1", "threat2"]
                }},
                "recommendations": [
                    "recommendation1",
                    "recommendation2"
                ]
            }}
            """
            
            # Generate analysis
            response = self.model.generate_content(prompt)
            
            # Parse the response
            analysis_json = json.loads(response.text)
            
            # Add metadata
            analysis_json["analyzed_at"] = datetime.utcnow().isoformat()
            analysis_json["competitor_handle"] = competitor_data["username"]
            
            return analysis_json
        except Exception as e:
            print(f"Error analyzing competitor with AI: {e}")
            # Return a simple fallback analysis
            return {
                "overview": {
                    "name": competitor_data["username"],
                    "instagram": f"@{competitor_data['username']}",
                    "followers": competitor_data["follower_count"],
                    "engagement_rate": competitor_data["engagement_rate"],
                    "posting_frequency": competitor_data["posting_frequency"]
                },
                "content_analysis": {
                    "top_performing_posts": [
                        {
                            "type": "image",
                            "topic": "web design",
                            "engagement": competitor_data["recent_posts"][0]["likes"] + competitor_data["recent_posts"][0]["comments"]
                        }
                    ],
                    "content_themes": competitor_data["content_themes"],
                    "visual_style": "Professional and clean",
                    "tone_of_voice": "Informative and professional"
                },
                "website_analysis": {
                    "design_quality": 7,
                    "mobile_responsiveness": 6,
                    "key_features": ["Portfolio", "Services", "Contact form"]
                },
                "swot": {
                    "strengths": ["Strong visual identity", "Consistent posting"],
                    "weaknesses": ["Limited engagement", "Generic content"],
                    "opportunities": ["More interactive content", "Educational tutorials"],
                    "threats": ["Similar competitors", "Changing algorithms"]
                },
                "recommendations": [
                    "Create more interactive content",
                    "Focus on educational tutorials",
                    "Improve visual consistency",
                    "Engage more with followers"
                ],
                "analyzed_at": datetime.utcnow().isoformat(),
                "competitor_handle": competitor_data["username"],
                "error": str(e)
            }
    
    def _generate_content_from_analysis_with_ai(self, analysis: Dict[str, Any], business_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate content based on competitor analysis using Gemini AI.
        
        Args:
            analysis: Competitor analysis
            business_info: Business information
            
        Returns:
            Dictionary with generated content
        """
        try:
            # Extract key information from analysis
            competitor = analysis.get("competitor_name", "Competitor")
            weaknesses = analysis.get("swot", {}).get("weaknesses", ["Generic content"])
            opportunities = analysis.get("swot", {}).get("opportunities", ["Educational content"])
            recommendations = analysis.get("recommendations", ["Create more engaging content"])
            
            # Prepare the prompt
            prompt = f"""
            Generate Instagram content for {business_info['business_name']} that addresses the weaknesses and opportunities identified in our competitor analysis.
            
            Business Information:
            - Name: {business_info['business_name']}
            - Type: {business_info['business_type']}
            - Tagline: {business_info['tagline']}
            
            Competitor Analysis:
            - Competitor: {competitor}
            - Weaknesses: {', '.join(weaknesses)}
            - Opportunities: {', '.join(opportunities)}
            - Recommendations: {', '.join(recommendations)}
            
            Please generate:
            1. A catchy caption (with appropriate hashtags)
            2. A detailed description of the visual design for an Instagram post
            3. Key messages to highlight
            4. Call to action
            
            The content should specifically address the competitor's weaknesses and capitalize on the identified opportunities.
            
            Format your response as a JSON object with the following structure:
            {{
                "caption": "The Instagram caption with hashtags",
                "design_description": {{
                    "post_type": "carousel/single/reel",
                    "slides": [
                        {{
                            "background_color": "#hexcolor",
                            "text_color": "#hexcolor",
                            "main_text": "Main text on the slide",
                            "secondary_text": "Secondary text if applicable",
                            "image_description": "Description of the image to use",
                            "layout": "text_over_image/split/text_only"
                        }}
                    ],
                    "style_guide": {{
                        "brand_colors": ["#hexcolor1", "#hexcolor2"],
                        "fonts": ["Primary font", "Secondary font"],
                        "visual_style": "minimalist/bold/elegant/etc"
                    }}
                }},
                "key_messages": ["Message 1", "Message 2", "Message 3"],
                "call_to_action": "The specific call to action",
                "competitive_advantage": "How this content addresses competitor weaknesses"
            }}
            """
            
            # Generate content
            response = self.model.generate_content(prompt)
            
            # Parse the response
            content_json = json.loads(response.text)
            
            # Add metadata
            content_json["generated_at"] = datetime.utcnow().isoformat()
            content_json["based_on_competitor"] = competitor
            content_json["content_type"] = "post"
            content_json["business_type"] = business_info["business_type"]
            
            return content_json
        except Exception as e:
            print(f"Error generating content from analysis with AI: {e}")
            # Return a simple fallback content
            return {
                "caption": f"At {business_info['business_name']}, we believe in providing exceptional value to our clients. Here's how we stand out from the competition! #webdesign #professional #valueproposition",
                "design_description": {
                    "post_type": "carousel",
                    "slides": [
                        {
                            "background_color": "#ffffff",
                            "text_color": "#000000",
                            "main_text": "What Sets Us Apart",
                            "secondary_text": business_info['tagline'],
                            "image_description": "Professional looking comparison chart",
                            "layout": "text_over_image"
                        },
                        {
                            "background_color": "#f5f5f5",
                            "text_color": "#000000",
                            "main_text": "Our Advantage",
                            "secondary_text": "We focus on what matters to you",
                            "image_description": "Happy client using website",
                            "layout": "split"
                        }
                    ],
                    "style_guide": {
                        "brand_colors": ["#4a90e2", "#ffffff"],
                        "fonts": ["Arial", "Helvetica"],
                        "visual_style": "professional"
                    }
                },
                "key_messages": ["We address the weaknesses of our competitors", "We provide more value", "We focus on your specific needs"],
                "call_to_action": "Visit our website to see the difference",
                "competitive_advantage": "This content directly addresses the competitor's weaknesses by highlighting our strengths",
                "generated_at": datetime.utcnow().isoformat(),
                "based_on_competitor": competitor,
                "content_type": "post",
                "business_type": business_info["business_type"],
                "error": str(e)
            }
    
    def _get_competitor_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get competitor analysis from Supabase.
        
        Args:
            analysis_id: ID of the analysis
            
        Returns:
            Dictionary with competitor analysis or None if not found
        """
        try:
            result = supabase.table("competitor_analysis").select("*").eq("id", analysis_id).execute()
            if result.data and len(result.data) > 0:
                analysis = result.data[0]
                analysis["analysis_data"] = json.loads(analysis["analysis_data"])
                return analysis
            return None
        except Exception as e:
            print(f"Error getting competitor analysis: {e}")
            return None
    
    def _store_content_in_db(self, client_id: Optional[str], content: Dict[str, Any]) -> str:
        """
        Store generated content in Supabase.
        
        Args:
            client_id: Optional client ID
            content: Generated content
            
        Returns:
            ID of the stored content
        """
        try:
            # Prepare the data
            content_data = {
                "client_id": client_id,
                "content_type": content.get("content_type", "post"),
                "copy_text": content.get("caption", ""),
                "design_description": json.dumps(content.get("design_description", {})),
                "status": "draft",
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Insert into Supabase
            result = supabase.table("marketing_content").insert(content_data).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            
            return "unknown"
        except Exception as e:
            print(f"Error storing content in DB: {e}")
            return "error"
    
    def _store_competitor_analysis_in_db(self, client_id: Optional[str], competitor_instagram: str, analysis: Dict[str, Any]) -> str:
        """
        Store competitor analysis in Supabase.
        
        Args:
            client_id: Optional client ID
            competitor_instagram: Competitor's Instagram handle
            analysis: Analysis data
            
        Returns:
            ID of the stored analysis
        """
        try:
            # Extract SWOT components
            strengths = analysis.get("swot", {}).get("strengths", [])
            weaknesses = analysis.get("swot", {}).get("weaknesses", [])
            opportunities = analysis.get("swot", {}).get("opportunities", [])
            
            # Prepare the data
            analysis_data = {
                "client_id": client_id,
                "competitor_name": analysis.get("overview", {}).get("name", competitor_instagram),
                "competitor_instagram": competitor_instagram,
                "competitor_website": analysis.get("overview", {}).get("website", ""),
                "analysis_data": json.dumps(analysis),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "opportunities": opportunities,
                "last_analyzed": datetime.utcnow().isoformat()
            }
            
            # Insert into Supabase
            result = supabase.table("competitor_analysis").insert(analysis_data).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            
            return "unknown"
        except Exception as e:
            print(f"Error storing competitor analysis in DB: {e}")
            return "error"
    
    def _publish_to_instagram(self, content: Dict[str, Any]) -> Optional[str]:
        """
        Publish content to Instagram.
        
        Args:
            content: Content to publish
            
        Returns:
            Instagram post ID if successful, None otherwise
        """
        # In a real implementation, this would use the Instagram Graph API
        # For now, we'll return a mock ID
        try:
            # Mock successful publishing
            return f"mock_post_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        except Exception as e:
            print(f"Error publishing to Instagram: {e}")
            return None


# Helper functions for scheduled tasks

def generate_daily_content_for_all_clients():
    """
    Generate daily content for all active clients.
    """
    try:
        # Get all active clients
        result = supabase.table("clients").select("id").eq("status", "active").execute()
        
        if not result.data:
            print("No active clients found")
            return
        
        # Generate content for each client
        bot = MarketingBot()
        for client in result.data:
            try:
                content = bot.generate_daily_content(client["id"])
                print(f"Generated content for client {client['id']}: {content['id']}")
            except Exception as e:
                print(f"Error generating content for client {client['id']}: {e}")
    except Exception as e:
        print(f"Error generating daily content: {e}")


def publish_scheduled_content():
    """
    Publish content that is scheduled for today.
    """
    try:
        # Get content scheduled for today
        today = datetime.utcnow().date().isoformat()
        result = supabase.table("marketing_content").select("id").eq("status", "scheduled").like("scheduled_date", f"{today}%").execute()
        
        if not result.data:
            print("No content scheduled for today")
            return
        
        # Publish each scheduled content
        bot = MarketingBot()
        for content in result.data:
            try:
                success, post_id = bot.publish_content(content["id"])
                if success:
                    print(f"Published content {content['id']}: {post_id}")
                else:
                    print(f"Failed to publish content {content['id']}")
            except Exception as e:
                print(f"Error publishing content {content['id']}: {e}")
    except Exception as e:
        print(f"Error publishing scheduled content: {e}")


# Example usage
if __name__ == "__main__":
    # This is just for testing purposes
    bot = MarketingBot()
    
    try:
        # Generate content for TuWebFacil
        content = bot.generate_daily_content()
        print(f"Generated content: {json.dumps(content, indent=2)}")
        
        # Analyze a competitor
        analysis = bot.analyze_competitor("competitorwebsite")
        print(f"Competitor analysis: {json.dumps(analysis, indent=2)}")
        
        # Generate content based on competitor analysis
        content_from_analysis = bot.generate_content_from_competitor_analysis(analysis["id"])
        print(f"Content from analysis: {json.dumps(content_from_analysis, indent=2)}")
    except Exception as e:
        print(f"Error in example: {e}")