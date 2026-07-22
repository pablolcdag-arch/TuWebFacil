import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv
from supabase import create_client, Client
from marketing_bot import MarketingBot

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class CompetitorAnalysis:
    def __init__(self):
        """
        Initialize the Competitor Analysis module.
        """
        self.marketing_bot = MarketingBot()
    
    def analyze_competitor(self, competitor_instagram: str, client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a competitor's Instagram account.
        
        Args:
            competitor_instagram: Competitor's Instagram handle
            client_id: Optional client ID to associate the analysis with
            
        Returns:
            Dictionary with competitor analysis
        """
        # Use the marketing bot to analyze the competitor
        return self.marketing_bot.analyze_competitor(competitor_instagram, client_id)
    
    def analyze_multiple_competitors(self, competitor_instagrams: List[str], client_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Analyze multiple competitors' Instagram accounts.
        
        Args:
            competitor_instagrams: List of competitor Instagram handles
            client_id: Optional client ID to associate the analyses with
            
        Returns:
            List of dictionaries with competitor analyses
        """
        analyses = []
        for competitor in competitor_instagrams:
            try:
                analysis = self.analyze_competitor(competitor, client_id)
                analyses.append(analysis)
            except Exception as e:
                print(f"Error analyzing competitor {competitor}: {e}")
        
        return analyses
    
    def generate_comparative_report(self, analysis_ids: List[str]) -> Dict[str, Any]:
        """
        Generate a comparative report from multiple competitor analyses.
        
        Args:
            analysis_ids: List of analysis IDs to compare
            
        Returns:
            Dictionary with comparative report
        """
        try:
            # Get all analyses
            analyses = []
            for analysis_id in analysis_ids:
                analysis = self._get_competitor_analysis(analysis_id)
                if analysis:
                    analyses.append(analysis)
            
            if not analyses:
                raise ValueError("No valid analyses found")
            
            # Generate comparative report
            report = self._generate_comparative_report_with_ai(analyses)
            
            # Store the report in Supabase
            report_id = self._store_comparative_report_in_db(analyses[0].get("client_id"), report)
            
            # Return the report
            return {
                "id": report_id,
                "report": report,
                "analyses": [a.get("id") for a in analyses]
            }
        except Exception as e:
            print(f"Error generating comparative report: {e}")
            raise
    
    def generate_content_strategy(self, analysis_id: str, num_ideas: int = 5) -> Dict[str, Any]:
        """
        Generate a content strategy based on competitor analysis.
        
        Args:
            analysis_id: ID of the competitor analysis
            num_ideas: Number of content ideas to generate
            
        Returns:
            Dictionary with content strategy
        """
        try:
            # Get the competitor analysis
            analysis = self._get_competitor_analysis(analysis_id)
            if not analysis:
                raise ValueError(f"Competitor analysis with ID {analysis_id} not found")
            
            # Generate content strategy
            strategy = self._generate_content_strategy_with_ai(analysis, num_ideas)
            
            # Store the strategy in Supabase
            strategy_id = self._store_content_strategy_in_db(analysis.get("client_id"), analysis_id, strategy)
            
            # Return the strategy
            return {
                "id": strategy_id,
                "strategy": strategy,
                "based_on_analysis": analysis_id
            }
        except Exception as e:
            print(f"Error generating content strategy: {e}")
            raise
    
    def generate_visual_report(self, analysis_id: str, output_path: str = "competitor_report.pdf") -> str:
        """
        Generate a visual report from competitor analysis.
        
        Args:
            analysis_id: ID of the competitor analysis
            output_path: Path to save the report
            
        Returns:
            Path to the generated report
        """
        try:
            # Get the competitor analysis
            analysis = self._get_competitor_analysis(analysis_id)
            if not analysis:
                raise ValueError(f"Competitor analysis with ID {analysis_id} not found")
            
            # Generate visual report
            report_path = self._generate_visual_report(analysis, output_path)
            
            return report_path
        except Exception as e:
            print(f"Error generating visual report: {e}")
            raise
    
    def track_competitor_growth(self, competitor_instagram: str, days: int = 30) -> Dict[str, Any]:
        """
        Track a competitor's growth over time.
        
        Args:
            competitor_instagram: Competitor's Instagram handle
            days: Number of days to track
            
        Returns:
            Dictionary with growth data
        """
        try:
            # Get historical analyses
            analyses = self._get_historical_analyses(competitor_instagram, days)
            
            # Calculate growth metrics
            growth_data = self._calculate_growth_metrics(analyses)
            
            return growth_data
        except Exception as e:
            print(f"Error tracking competitor growth: {e}")
            raise
    
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
    
    def _generate_comparative_report_with_ai(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a comparative report from multiple competitor analyses using AI.
        
        Args:
            analyses: List of competitor analyses
            
        Returns:
            Dictionary with comparative report
        """
        try:
            # Extract key information from analyses
            competitors = []
            for analysis in analyses:
                analysis_data = analysis.get("analysis_data", {})
                competitor = {
                    "name": analysis.get("competitor_name", "Unknown"),
                    "instagram": analysis.get("competitor_instagram", ""),
                    "followers": analysis_data.get("overview", {}).get("followers", 0),
                    "engagement_rate": analysis_data.get("overview", {}).get("engagement_rate", 0),
                    "posting_frequency": analysis_data.get("overview", {}).get("posting_frequency", ""),
                    "content_themes": analysis_data.get("content_analysis", {}).get("content_themes", []),
                    "strengths": analysis_data.get("swot", {}).get("strengths", []),
                    "weaknesses": analysis_data.get("swot", {}).get("weaknesses", [])
                }
                competitors.append(competitor)
            
            # Prepare the prompt
            prompt = f"""
            Generate a comparative analysis report for the following competitors:
            
            {json.dumps(competitors, indent=2)}
            
            Please provide:
            1. An executive summary comparing the competitors
            2. A detailed comparison of their Instagram strategies
            3. A comparison of their strengths and weaknesses
            4. Market positioning analysis
            5. Recommendations for how we can position ourselves against these competitors
            
            Format your response as a JSON object with the following structure:
            {{
                "executive_summary": "Summary text here",
                "instagram_strategy_comparison": {{
                    "posting_frequency": "Analysis of posting frequency differences",
                    "content_themes": "Analysis of content theme differences",
                    "engagement": "Analysis of engagement differences"
                }},
                "strength_weakness_comparison": [
                    {{
                        "competitor": "Competitor name",
                        "key_strengths": ["Strength 1", "Strength 2"],
                        "key_weaknesses": ["Weakness 1", "Weakness 2"]
                    }}
                ],
                "market_positioning": {{
                    "leader": "Competitor with strongest position",
                    "positioning_map": {{
                        "axes": ["Axis 1", "Axis 2"],
                        "positions": [
                            {{
                                "competitor": "Competitor name",
                                "position": [x, y]
                            }}
                        ]
                    }}
                }},
                "recommendations": [
                    "Recommendation 1",
                    "Recommendation 2"
                ]
            }}
            """
            
            # Generate report
            response = self.marketing_bot.model.generate_content(prompt)
            
            # Parse the response
            report_json = json.loads(response.text)
            
            # Add metadata
            report_json["generated_at"] = datetime.utcnow().isoformat()
            report_json["competitors"] = [a.get("competitor_instagram") for a in analyses]
            
            return report_json
        except Exception as e:
            print(f"Error generating comparative report with AI: {e}")
            # Return a simple fallback report
            return {
                "executive_summary": "Comparative analysis of competitors",
                "instagram_strategy_comparison": {
                    "posting_frequency": "Varies across competitors",
                    "content_themes": "Some overlap in themes",
                    "engagement": "Engagement rates vary"
                },
                "strength_weakness_comparison": [
                    {
                        "competitor": analyses[0].get("competitor_name", "Competitor"),
                        "key_strengths": ["Strong visual identity"],
                        "key_weaknesses": ["Limited engagement"]
                    }
                ],
                "market_positioning": {
                    "leader": analyses[0].get("competitor_name", "Competitor"),
                    "positioning_map": {
                        "axes": ["Content Quality", "Engagement"],
                        "positions": [
                            {
                                "competitor": analyses[0].get("competitor_name", "Competitor"),
                                "position": [7, 5]
                            }
                        ]
                    }
                },
                "recommendations": [
                    "Focus on areas where competitors are weak",
                    "Develop a unique content strategy"
                ],
                "generated_at": datetime.utcnow().isoformat(),
                "competitors": [a.get("competitor_instagram") for a in analyses],
                "error": str(e)
            }
    
    def _generate_content_strategy_with_ai(self, analysis: Dict[str, Any], num_ideas: int) -> Dict[str, Any]:
        """
        Generate a content strategy based on competitor analysis using AI.
        
        Args:
            analysis: Competitor analysis
            num_ideas: Number of content ideas to generate
            
        Returns:
            Dictionary with content strategy
        """
        try:
            # Extract key information from analysis
            analysis_data = analysis.get("analysis_data", {})
            competitor = analysis.get("competitor_name", "Competitor")
            weaknesses = analysis_data.get("swot", {}).get("weaknesses", ["Generic content"])
            opportunities = analysis_data.get("swot", {}).get("opportunities", ["Educational content"])
            recommendations = analysis_data.get("recommendations", ["Create more engaging content"])
            
            # Prepare the prompt
            prompt = f"""
            Generate a content strategy that capitalizes on the weaknesses and opportunities identified in our competitor analysis.
            
            Competitor: {competitor}
            Weaknesses: {', '.join(weaknesses)}
            Opportunities: {', '.join(opportunities)}
            Recommendations: {', '.join(recommendations)}
            
            Please generate:
            1. An overall content strategy
            2. Content pillars we should focus on
            3. {num_ideas} specific content ideas that address competitor weaknesses
            4. A content calendar for the next 4 weeks
            5. Key metrics to track
            
            Format your response as a JSON object with the following structure:
            {{
                "strategy_overview": "Overall strategy description",
                "content_pillars": [
                    {{
                        "name": "Pillar name",
                        "description": "Pillar description",
                        "frequency": "How often to post this type of content"
                    }}
                ],
                "content_ideas": [
                    {{
                        "title": "Content idea title",
                        "description": "Detailed description",
                        "format": "Post/Story/Reel/Carousel",
                        "addresses_weakness": "Which competitor weakness this addresses"
                    }}
                ],
                "content_calendar": [
                    {{
                        "week": 1,
                        "posts": [
                            {{
                                "day": "Monday",
                                "content_type": "Type of content",
                                "topic": "Topic description"
                            }}
                        ]
                    }}
                ],
                "key_metrics": [
                    {{
                        "metric": "Metric name",
                        "target": "Target value",
                        "measurement_frequency": "How often to measure"
                    }}
                ]
            }}
            """
            
            # Generate strategy
            response = self.marketing_bot.model.generate_content(prompt)
            
            # Parse the response
            strategy_json = json.loads(response.text)
            
            # Add metadata
            strategy_json["generated_at"] = datetime.utcnow().isoformat()
            strategy_json["based_on_competitor"] = competitor
            
            return strategy_json
        except Exception as e:
            print(f"Error generating content strategy with AI: {e}")
            # Return a simple fallback strategy
            return {
                "strategy_overview": "Focus on addressing competitor weaknesses and capitalizing on opportunities",
                "content_pillars": [
                    {
                        "name": "Educational Content",
                        "description": "Tutorials and how-to guides",
                        "frequency": "2 times per week"
                    },
                    {
                        "name": "Client Showcases",
                        "description": "Before and after transformations",
                        "frequency": "1 time per week"
                    }
                ],
                "content_ideas": [
                    {
                        "title": "5-Minute Website Speed Optimization",
                        "description": "Quick tutorial on improving website speed",
                        "format": "Carousel",
                        "addresses_weakness": "Limited educational content"
                    }
                ],
                "content_calendar": [
                    {
                        "week": 1,
                        "posts": [
                            {
                                "day": "Monday",
                                "content_type": "Educational",
                                "topic": "Website Speed Optimization"
                            },
                            {
                                "day": "Wednesday",
                                "content_type": "Client Showcase",
                                "topic": "Before/After Website Redesign"
                            },
                            {
                                "day": "Friday",
                                "content_type": "Educational",
                                "topic": "SEO Tips"
                            }
                        ]
                    }
                ],
                "key_metrics": [
                    {
                        "metric": "Engagement Rate",
                        "target": "5%",
                        "measurement_frequency": "Weekly"
                    },
                    {
                        "metric": "Follower Growth",
                        "target": "10% monthly",
                        "measurement_frequency": "Monthly"
                    }
                ],
                "generated_at": datetime.utcnow().isoformat(),
                "based_on_competitor": competitor,
                "error": str(e)
            }
    
    def _generate_visual_report(self, analysis: Dict[str, Any], output_path: str) -> str:
        """
        Generate a visual report from competitor analysis.
        
        Args:
            analysis: Competitor analysis
            output_path: Path to save the report
            
        Returns:
            Path to the generated report
        """
        try:
            # Extract key information from analysis
            analysis_data = analysis.get("analysis_data", {})
            
            # In a real implementation, this would generate a PDF report
            # For now, we'll generate some simple visualizations
            
            # Create a directory for the report if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
            
            # Generate a simple text report
            with open(output_path, "w") as f:
                f.write(f"# Competitor Analysis Report: {analysis.get('competitor_name')}\n\n")
                f.write(f"Generated: {datetime.utcnow().isoformat()}\n\n")
                
                f.write("## Overview\n\n")
                overview = analysis_data.get("overview", {})
                for key, value in overview.items():
                    f.write(f"- {key}: {value}\n")
                
                f.write("\n## Content Analysis\n\n")
                content_analysis = analysis_data.get("content_analysis", {})
                for key, value in content_analysis.items():
                    if isinstance(value, list):
                        f.write(f"### {key}\n")
                        for item in value:
                            if isinstance(item, dict):
                                for k, v in item.items():
                                    f.write(f"- {k}: {v}\n")
                            else:
                                f.write(f"- {item}\n")
                        f.write("\n")
                    else:
                        f.write(f"- {key}: {value}\n")
                
                f.write("\n## SWOT Analysis\n\n")
                swot = analysis_data.get("swot", {})
                for key, value in swot.items():
                    f.write(f"### {key.capitalize()}\n")
                    for item in value:
                        f.write(f"- {item}\n")
                    f.write("\n")
                
                f.write("\n## Recommendations\n\n")
                recommendations = analysis_data.get("recommendations", [])
                for rec in recommendations:
                    f.write(f"- {rec}\n")
            
            return output_path
        except Exception as e:
            print(f"Error generating visual report: {e}")
            raise
    
    def _get_historical_analyses(self, competitor_instagram: str, days: int) -> List[Dict[str, Any]]:
        """
        Get historical analyses for a competitor.
        
        Args:
            competitor_instagram: Competitor's Instagram handle
            days: Number of days to look back
            
        Returns:
            List of historical analyses
        """
        try:
            # Calculate the cutoff date
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            # Get analyses from Supabase
            result = supabase.table("competitor_analysis") \
                .select("*") \
                .eq("competitor_instagram", competitor_instagram) \
                .gte("created_at", cutoff_date) \
                .order("created_at") \
                .execute()
            
            analyses = []
            for item in result.data:
                item["analysis_data"] = json.loads(item["analysis_data"])
                analyses.append(item)
            
            return analyses
        except Exception as e:
            print(f"Error getting historical analyses: {e}")
            return []
    
    def _calculate_growth_metrics(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate growth metrics from historical analyses.
        
        Args:
            analyses: List of historical analyses
            
        Returns:
            Dictionary with growth metrics
        """
        try:
            if not analyses:
                return {
                    "error": "No historical data available",
                    "metrics": {}
                }
            
            # Extract follower counts and dates
            follower_data = []
            engagement_data = []
            dates = []
            
            for analysis in analyses:
                created_at = datetime.fromisoformat(analysis.get("created_at").replace("Z", "+00:00"))
                followers = analysis.get("analysis_data", {}).get("overview", {}).get("followers", 0)
                engagement = analysis.get("analysis_data", {}).get("overview", {}).get("engagement_rate", 0)
                
                follower_data.append(followers)
                engagement_data.append(engagement)
                dates.append(created_at)
            
            # Calculate growth metrics
            if len(follower_data) >= 2:
                follower_growth = follower_data[-1] - follower_data[0]
                follower_growth_percent = (follower_growth / follower_data[0]) * 100 if follower_data[0] > 0 else 0
                
                engagement_change = engagement_data[-1] - engagement_data[0]
                engagement_change_percent = (engagement_change / engagement_data[0]) * 100 if engagement_data[0] > 0 else 0
                
                days_elapsed = (dates[-1] - dates[0]).days or 1  # Avoid division by zero
                
                daily_follower_growth = follower_growth / days_elapsed
                monthly_follower_growth = daily_follower_growth * 30
                monthly_growth_percent = (monthly_follower_growth / follower_data[0]) * 100 if follower_data[0] > 0 else 0
            else:
                follower_growth = 0
                follower_growth_percent = 0
                engagement_change = 0
                engagement_change_percent = 0
                monthly_follower_growth = 0
                monthly_growth_percent = 0
            
            return {
                "competitor": analyses[0].get("competitor_name", "Unknown"),
                "instagram": analyses[0].get("competitor_instagram", ""),
                "period": {
                    "start_date": dates[0].isoformat() if dates else None,
                    "end_date": dates[-1].isoformat() if dates else None,
                    "days": (dates[-1] - dates[0]).days if len(dates) >= 2 else 0
                },
                "metrics": {
                    "followers": {
                        "start": follower_data[0] if follower_data else 0,
                        "end": follower_data[-1] if follower_data else 0,
                        "growth": follower_growth,
                        "growth_percent": follower_growth_percent,
                        "monthly_growth": monthly_follower_growth,
                        "monthly_growth_percent": monthly_growth_percent
                    },
                    "engagement": {
                        "start": engagement_data[0] if engagement_data else 0,
                        "end": engagement_data[-1] if engagement_data else 0,
                        "change": engagement_change,
                        "change_percent": engagement_change_percent
                    }
                },
                "data_points": len(analyses)
            }
        except Exception as e:
            print(f"Error calculating growth metrics: {e}")
            return {
                "error": str(e),
                "metrics": {}
            }
    
    def _store_comparative_report_in_db(self, client_id: Optional[str], report: Dict[str, Any]) -> str:
        """
        Store a comparative report in Supabase.
        
        Args:
            client_id: Optional client ID
            report: Comparative report
            
        Returns:
            ID of the stored report
        """
        try:
            # Prepare the data
            report_data = {
                "client_id": client_id,
                "report_type": "comparative",
                "report_data": json.dumps(report),
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Insert into Supabase
            result = supabase.table("competitor_reports").insert(report_data).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            
            return "unknown"
        except Exception as e:
            print(f"Error storing comparative report in DB: {e}")
            return "error"
    
    def _store_content_strategy_in_db(self, client_id: Optional[str], analysis_id: str, strategy: Dict[str, Any]) -> str:
        """
        Store a content strategy in Supabase.
        
        Args:
            client_id: Optional client ID
            analysis_id: ID of the competitor analysis
            strategy: Content strategy
            
        Returns:
            ID of the stored strategy
        """
        try:
            # Prepare the data
            strategy_data = {
                "client_id": client_id,
                "analysis_id": analysis_id,
                "strategy_data": json.dumps(strategy),
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Insert into Supabase
            result = supabase.table("content_strategies").insert(strategy_data).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            
            return "unknown"
        except Exception as e:
            print(f"Error storing content strategy in DB: {e}")
            return "error"


# Helper functions

def analyze_industry_competitors(industry: str, client_id: Optional[str] = None, count: int = 3) -> Dict[str, Any]:
    """
    Analyze top competitors in a specific industry.
    
    Args:
        industry: Industry to analyze
        client_id: Optional client ID
        count: Number of competitors to analyze
        
    Returns:
        Dictionary with analyses and comparative report
    """
    try:
        # In a real implementation, this would use an API to find top competitors
        # For now, we'll use mock data
        mock_competitors = {
            "web_development": ["webflow", "wix", "squarespace"],
            "restaurant": ["chipotle", "sweetgreen", "shakeshack"],
            "retail": ["zara", "hm", "uniqlo"],
            "fitness": ["peloton", "nike", "underarmour"],
            "beauty": ["glossier", "sephora", "fentybeauty"]
        }
        
        competitors = mock_competitors.get(industry, ["competitor1", "competitor2", "competitor3"])[:count]
        
        # Analyze competitors
        analyzer = CompetitorAnalysis()
        analyses = analyzer.analyze_multiple_competitors(competitors, client_id)
        
        # Generate comparative report
        analysis_ids = [a.get("id") for a in analyses]
        report = analyzer.generate_comparative_report(analysis_ids)
        
        return {
            "industry": industry,
            "competitors": competitors,
            "analyses": analyses,
            "comparative_report": report
        }
    except Exception as e:
        print(f"Error analyzing industry competitors: {e}")
        return {
            "error": str(e),
            "industry": industry
        }


def generate_industry_content_strategy(industry: str, client_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate a content strategy for a specific industry based on competitor analysis.
    
    Args:
        industry: Industry to analyze
        client_id: Optional client ID
        
    Returns:
        Dictionary with content strategy
    """
    try:
        # Analyze industry competitors
        industry_analysis = analyze_industry_competitors(industry, client_id, count=1)
        
        if "error" in industry_analysis:
            raise ValueError(industry_analysis["error"])
        
        # Generate content strategy based on the first analysis
        if industry_analysis["analyses"]:
            analyzer = CompetitorAnalysis()
            strategy = analyzer.generate_content_strategy(industry_analysis["analyses"][0]["id"])
            
            return {
                "industry": industry,
                "strategy": strategy,
                "based_on_analysis": industry_analysis["analyses"][0]["id"]
            }
        else:
            raise ValueError("No competitor analyses available")
    except Exception as e:
        print(f"Error generating industry content strategy: {e}")
        return {
            "error": str(e),
            "industry": industry
        }


# Example usage
if __name__ == "__main__":
    # This is just for testing purposes
    analyzer = CompetitorAnalysis()
    
    try:
        # Analyze a competitor
        analysis = analyzer.analyze_competitor("competitorwebsite")
        print(f"Competitor analysis ID: {analysis['id']}")
        
        # Generate a content strategy
        strategy = analyzer.generate_content_strategy(analysis["id"])
        print(f"Content strategy ID: {strategy['id']}")
        
        # Generate a visual report
        report_path = analyzer.generate_visual_report(analysis["id"], "competitor_report.md")
        print(f"Visual report generated: {report_path}")
        
        # Analyze industry competitors
        industry_analysis = analyze_industry_competitors("web_development")
        print(f"Industry analysis complete: {len(industry_analysis['analyses'])} competitors analyzed")
        
        # Generate industry content strategy
        industry_strategy = generate_industry_content_strategy("web_development")
        print(f"Industry strategy generated: {industry_strategy['strategy']['id']}")
    except Exception as e:
        print(f"Error in example: {e}")